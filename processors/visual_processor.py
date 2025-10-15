from bson import ObjectId
import boto3
import os
import numpy as np
import tempfile
from settings import settings
import cv2
from collections import defaultdict
from db import image_analysis_collection
from core.logger import logger
from core.s3_client import s3_client
import json

class VisualAnalyzer:
    def __init__(self, frame_interval=1, max_frames=None, confidence_threshold=0.5,
                 frame_selection_mode="timestamps", specific_frames=None, timestamps=None):
        self.frame_interval = frame_interval
        self.max_frames = max_frames if isinstance(max_frames, int) and max_frames > 0 else None
        self.confidence_threshold = confidence_threshold
        self.frame_selection_mode = frame_selection_mode
        self.timestamps = timestamps or []
        self.specific_frames = specific_frames or []

        self.rekognition = boto3.client(
            "rekognition",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

        self.WINDOW_SIZE = 5
        self._eye_yaw_hist = []      #  for EyeDirection.Yaw
        self._eye_pitch_hist = []    #  for EyeDirection.Pitch
        self._head_yaw_hist = []     #  for Pose.Yaw
        self._head_pitch_hist = []   #  for Pose.Pitch
        self._head_roll_hist = []    #  for Pose.Roll
        self._conn_hist = []  

    def _get_default_response(self, expression="no_face"):
        return {
            "eye_contact_analysis": {
                "eye_contact_confidence": 0.0,
                "eye_contact_confidence_tip": "No face detected",
                "eye_stability": 0.0,
                "eye_stability_tip": "No data",
                "timestamp_sec": 0,
                "window_size_sec": 0,
                "raw_eye_yaw": 0.0,
                "raw_eye_pitch": 0.0
            },
            "posture_analysis": {
                "head_orientation": "unknown",
                "head_orientation_score": 0.0,  # Added numerical score
                "head_orientation_tip": "No face detected",
                "posture_stability": 0.0,
                "posture_stability_tip": "No data",
                "timestamp_sec": 0,
                "window_size_sec": 0,
                "raw_head_yaw": 0.0,
                "raw_head_pitch": 0.0,
                "raw_head_roll": 0.0
            },
            "facial_expressions": {
                "type": expression.upper(),
                "score": 0.0,
                "nervousness_score": 0.0,
                "expression_tip": f"{expression.replace('_', ' ').title()}",
                "nervousness_tip": "No nervousness data available",
                "timestamp_sec": 0,
                "window_size_sec": 0,
                "raw_emotions": []
            },
            "technical_quality": {
                "brightness": 0.0,
                "sharpness": 0.0,
                "occlusion": 0.0,
                "average_score": 0.0,
                "raw_brightness": 0,
                "raw_sharpness": 0,
                "raw_occlusion_ratio": 0.0
            }
        }

    def _analyze_emotions(self, face):
        emotions = face.get("Emotions", [])
        if not emotions:
            return {
                "type": "NEUTRAL",
                "score": 1.0,
                "nervousness_score": 0.0,
                "raw_emotions": []
            }

        # Build emotion map: { "HAPPY": 95.2, "FEAR": 12.1, ... }
        emotion_map = {e["Type"].upper(): e["Confidence"] for e in emotions}

        # Get dominant
        dominant = max(emotions, key=lambda e: e["Confidence"])
        dominant_type = dominant["Type"].upper()
        dominant_score = dominant["Confidence"] / 100.0

        # ===== IMPROVED NERVOUSNESS SCORE =====
        # Primary nervousness indicators (high weight)
        primary_nervous = {
            "FEAR": 1.0,
            "CONFUSED": 0.9,
        }
        
        # Secondary nervousness indicators (medium weight)
        secondary_nervous = {
            "SURPRISED": 0.6,
            "SAD": 0.5,
            "ANGRY": 0.4,  # Can indicate stress/tension
            "DISGUSTED": 0.3
        }
        
        # Calming emotions (negative weight - reduces nervousness)
        calming_emotions = {
            "CALM": -1.0,
            "HAPPY": -0.8,
        }

        nervousness = 0.0
        
        # Calculate weighted nervousness score
        for emotion, weight in primary_nervous.items():
            conf = emotion_map.get(emotion, 0.0)
            nervousness += (conf / 100.0) * weight
            
        for emotion, weight in secondary_nervous.items():
            conf = emotion_map.get(emotion, 0.0)
            nervousness += (conf / 100.0) * weight
            
        for emotion, weight in calming_emotions.items():
            conf = emotion_map.get(emotion, 0.0)
            nervousness += (conf / 100.0) * weight

        # Normalize and clamp between 0-1
        nervousness = min(1.0, max(0.0, nervousness))

        return {
            "type": dominant_type,
            "score": dominant_score,
            "nervousness_score": round(nervousness, 2),
            "raw_emotions": emotions
        }

    def _get_nervousness_tip(self, nervousness_score):
        """
        Dedicated tips for nervousness levels
        """
        if nervousness_score >= 0.8:
            return "🚨 High nervousness detected — Take deep breaths, pause, and ground yourself. Remember, your audience wants you to succeed!"
        elif nervousness_score >= 0.6:
            return "⚠️ Moderate nervousness — Channel this energy into passion! Smile, slow down your pace, and trust your preparation."
        elif nervousness_score >= 0.4:
            return "💛 Slight nervous energy — This is normal! Use it to stay alert and engaged. Focus on your message, not the anxiety."
        elif nervousness_score >= 0.2:
            return "✅ Minimal nervousness — Great balance! You're alert but composed. Keep this steady energy."
        else:
            return "🌟 Very calm and composed — Excellent! You're projecting confidence and control."

    def _get_expression_tip(self, expression, nervousness_score=None):
        tips = {
            "HAPPY": "Great! Smiling builds warmth and trust with your audience.",
            "CALM": "Excellent — calmness conveys confidence and control.",
            "CONFUSED": "Try to pause and collect your thoughts — clarity builds credibility.",
            "FEAR": "It's okay to feel nervous — focus on your message, not the fear.",
            "SAD": "Check your energy — smiling or standing tall can shift your mood.",
            "ANGRY": "Channel that energy into passion, not frustration.",
            "SURPRISED": "Use surprise intentionally — avoid looking startled.",
            "DISGUSTED": "Re-evaluate your delivery — ensure tone matches message.",
            "NEUTRAL": "Add subtle expressions to connect — even a small smile helps.",
            "UNKNOWN": "Expression unclear — ensure good lighting and frontal view."
        }

        return tips.get(expression, "Keep practicing — awareness leads to improvement.")

    def _compute_brightness(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        return float(np.mean(gray))

    def _compute_sharpness(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return float(laplacian_var)

    def _compute_face_occlusion(self, face_detail):
        landmarks = face_detail.get("Landmarks", [])
        landmark_count = len(landmarks)
        expected_landmarks = 12
        occlusion_ratio = max(0.0, 1.0 - (landmark_count / expected_landmarks))
        confidence = face_detail.get("Confidence", 100.0) / 100.0
        occlusion_ratio = max(occlusion_ratio, 1.0 - confidence)
        return round(occlusion_ratio, 2)

    # ======== METRIC HELPERS ========
    def _compute_eye_contact_confidence_from_eye_direction(self, eye_yaw, eye_pitch):
        # Simple threshold-based calculation
        yaw_deviation = abs(eye_yaw) / 25.0
        pitch_deviation = abs(eye_pitch) / 20.0
        total_deviation = max(yaw_deviation, pitch_deviation)
        return max(0.0, 1.0 - total_deviation)

    def _compute_eye_stability_from_eye_history(self, yaw_hist, pitch_hist):
        if len(yaw_hist) < 2:
            return 1.0
        yaw_std = np.std(yaw_hist)
        pitch_std = np.std(pitch_hist)
        avg_std = (yaw_std + pitch_std) / 2
        return max(0.0, 1.0 - avg_std / 15.0)

    def _compute_head_orientation_from_pose(self, yaw, pitch, roll):
        """
        Determine head orientation and return both categorical and numerical values
        """
        # Priority order: yaw > pitch > roll
        if abs(yaw) > 30:
            return "left" if yaw < 0 else "right"
        elif abs(pitch) > 25:
            return "up" if pitch > 0 else "down"
        elif abs(roll) > 20:
            return "tilt_left" if roll < 0 else "tilt_right"
        else:
            return "forward"

    def _map_orientation_to_score(self, orientation, yaw, pitch, roll):
        """
        Map head orientation to a numerical score for graphing (0.0 to 1.0)
        1.0 = Perfect forward facing
        0.0 = Completely off-axis
        """
        orientation_scores = {
            "forward": 1.0,
            "left": max(0.0, 1.0 - abs(yaw) / 90.0),
            "right": max(0.0, 1.0 - abs(yaw) / 90.0), 
            "up": max(0.0, 1.0 - abs(pitch) / 90.0),
            "down": max(0.0, 1.0 - abs(pitch) / 90.0),
            "tilt_left": max(0.0, 1.0 - abs(roll) / 90.0),
            "tilt_right": max(0.0, 1.0 - abs(roll) / 90.0),
            "unknown": 0.0
        }
        
        base_score = orientation_scores.get(orientation, 0.0)
        
        # Additional penalty for multiple axis deviation
        multi_axis_penalty = 0.0
        active_axes = sum([
            abs(yaw) > 15,
            abs(pitch) > 15, 
            abs(roll) > 15
        ])
        
        if active_axes > 1:
            multi_axis_penalty = 0.1 * (active_axes - 1)
            
        final_score = max(0.0, base_score - multi_axis_penalty)
        return round(final_score, 2)

    def _compute_connection_strength_from_pose(self, yaw, pitch, roll):
        """
        Calculate connection strength based on pose
        """
        if abs(yaw) <= 25 and abs(pitch) <= 20:
            return 1.0
        else:
            yaw_ratio = max(0.0, 1.0 - abs(yaw)/45.0)
            pitch_ratio = max(0.0, 1.0 - abs(pitch)/30.0)
            return (yaw_ratio + pitch_ratio) / 2

    def _compute_posture_stability(self, conn_hist):
        """
        Calculate posture stability from connection history
        """
        if len(conn_hist) == 0:
            return 1.0
        return sum(1 for c in conn_hist if c > 0.7) / len(conn_hist)

    def _get_eye_contact_confidence_tip(self, score):
        if score > 0.8: return "🌟 Excellent eye contact — you're fully engaging your audience!"
        elif score > 0.5: return "✅ Good — maintain this level, try to reduce glances away."
        else: return "⚠️ Low eye contact — practice looking at the camera to build connection."

    def _get_eye_stability_tip(self, score):
        if score > 0.7: return "🧘‍♂️ Steady gaze — projects calm and focus."
        elif score > 0.4: return "👀 Occasional darting — try to pause and anchor your gaze."
        else: return "⚠️ Restless eyes — may signal nervousness or distraction."

    def _get_head_orientation_tip(self, orientation):
        tips = {
            "forward": "🎯 Perfect — you're addressing your audience directly.",
            "left": "⬅️ Looking left — check if you're reading notes or avoiding camera.",
            "right": "➡️ Looking right — same as above, try to re-center.",
            "up": "⬆️ Looking up — may seem distracted or searching for words.",
            "down": "⬇️ Looking down — can signal hesitation or low confidence.",
            "tilt_left": "🫣 Head tilt — adds curiosity, but overuse may seem uncertain.",
            "tilt_right": "🫣 Head tilt — same as above.",
            "unknown": "❓ Orientation unclear — ensure proper camera positioning."
        }
        return tips.get(orientation, "Unknown orientation.")

    def _get_posture_stability_tip(self, score):
        if score > 0.8: return "🏆 Rock-solid presence — you own the space!"
        elif score > 0.5: return "📈 Generally aligned — minor shifts are natural."
        else: return "⚠️ Frequent posture shifts — may reduce perceived confidence."

    def _get_overall_tip(self, metric_name, value, dominant_emotion=None):
        if metric_name == "avg_eye_contact_confidence":
            if value > 0.8: return "🌟 Excellent eye contact — you're fully engaging your audience!"
            elif value > 0.5: return "✅ Good eye contact — maintain this level and reduce glances away."
            else: return "⚠️ Very low eye contact — practice looking directly into the camera to build connection."

        elif metric_name == "avg_eye_stability":
            if value > 0.7: return "🧘‍♂️ Good eye stability — your gaze was steady and confident."
            elif value > 0.4: return "👀 Moderate eye movement — try to anchor your gaze more consistently."
            else: return "⚠️ Restless eyes — frequent darting may signal distraction or anxiety."

        elif metric_name == "avg_posture_stability":
            if value > 0.8: return "🏆 Excellent posture stability — you held your presence strongly."
            elif value > 0.6: return "📈 Good posture — minor shifts are natural and acceptable."
            else: return "⚠️ Frequent posture shifts — work on grounding your stance for more confidence."

        elif metric_name == "avg_head_orientation_score":
            if value > 0.85: return "🎯 Near-perfect head alignment — you faced the camera directly."
            elif value > 0.6: return "↩️ Occasional off-angle looks — try to stay centered on the lens."
            else: return "⬅️➡️ Frequent head turning — this reduces perceived engagement."

        elif metric_name == "avg_emotional_score":
            if value > 0.8: return "😊 Strong emotional expressiveness — your face clearly conveyed your message."
            elif value > 0.5: return "🙂 Moderate expressiveness — add a bit more facial animation to connect."
            else: return "😐 Low expressiveness — your face appeared flat; practice matching tone with expression."

        elif metric_name == "avg_nervousness_score":
            if value >= 0.8: return "🚨 High nervousness — take deep breaths and pause to reset."
            elif value >= 0.6: return "⚠️ Noticeable nervous energy — channel it into passion and pace."
            elif value >= 0.3: return "💛 Mild nerves — totally normal! Use it to stay alert."
            elif value >= 0.1: return "✅ Very calm — great balance of energy and composure."
            else: return "🌟 Exceptionally calm — you projected total confidence."

        elif metric_name == "avg_technical_quality":
            if value > 0.8: return "✨ Excellent video quality — crisp, clear, and professional."
            elif value > 0.6: return "🔧 Good technical quality — minor improvements would help."
            elif value > 0.4: return "⚠️ Fair quality — consider better lighting, focus, or camera."
            else: return "❌ Poor video quality — technical issues may distract from your message."

        elif metric_name == "avg_brightness":
            if value > 0.8: return "💡 Excellent brightness — well-lit and easy to see."
            elif value > 0.5: return "🔆 Adequate lighting — could be slightly brighter or softer."
            else: return "🌑 Too dark or overexposed — adjust lighting for clarity."

        elif metric_name == "avg_sharpness":
            if value > 0.7: return "🔍 Crisp and sharp video — great focus!"
            elif value > 0.3: return "👀 Acceptable sharpness — minor blur is okay."
            else: return "⚠️ Very blurry — ensure your camera is focused and stable."

        elif metric_name == "avg_occlusion":
            if value > 0.85: return "✅ Face fully visible — no obstructions, perfect framing."
            elif value > 0.6: return "👁️ Mostly visible — minor occlusion (e.g., hand, hair) occurred."
            else: return "❌ Frequent face occlusion — keep your face clear and centered."

        return "Keep practicing — awareness leads to improvement."

    # ==================== MAIN ANALYSIS METHODS ====================

    def analyze_frame(self, frame_rgb):
        try:
            if frame_rgb is None or frame_rgb.size == 0:
                return self._get_default_response(expression="error")

            _, encoded = cv2.imencode(".jpg", cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if encoded is None:
                return self._get_default_response(expression="error")

            try:
                response = self.rekognition.detect_faces(
                    Image={"Bytes": encoded.tobytes()},
                    Attributes=["ALL"]
                )
            except Exception:
                return self._get_default_response(expression="error")

            if response.get("FaceDetails"):
                for face in response["FaceDetails"]:
                    if face.get("Confidence", 0.0) < self.confidence_threshold:
                        continue

                    # ---- Modularized analysis ----
                    expression_info = self._analyze_emotions(face)
                    expression = expression_info.get("type", "UNKNOWN")
                    emotional_score = expression_info.get("score", 0.0)
                    nervousness_score = expression_info.get("nervousness_score", 0.0)

                    # ==================== TECHNICAL QUALITY ====================
                    brightness_raw = self._compute_brightness(frame_rgb)
                    sharpness_raw = self._compute_sharpness(frame_rgb)
                    occlusion_ratio = self._compute_face_occlusion(face)

                    # Normalize
                    brightness_norm = max(0.0, min(1.0, (brightness_raw - 50) / 150))
                    sharpness_norm = max(0.0, min(1.0, sharpness_raw / 200))
                    occlusion_norm = 1.0 - occlusion_ratio  # invert: higher = better

                    technical_quality_avg = (brightness_norm + sharpness_norm + occlusion_norm) / 3.0

                    technical_quality = {
                        "brightness": round(brightness_norm, 2),
                        "sharpness": round(sharpness_norm, 2),
                        "occlusion": round(occlusion_norm, 2),
                        "average_score": round(technical_quality_avg, 2),
                        "raw_brightness": brightness_raw,
                        "raw_sharpness": sharpness_raw,
                        "raw_occlusion_ratio": occlusion_ratio
                    }

                    # ==================== FACIAL EXPRESSIONS WITH NERVOUSNESS ====================
                    facial_expressions = {
                        "type": expression,
                        "score": round(emotional_score, 2),
                        "nervousness_score": round(nervousness_score, 2),
                        "expression_tip": self._get_expression_tip(expression),
                        "nervousness_tip": self._get_nervousness_tip(nervousness_score),
                        "timestamp_sec": len(self._eye_yaw_hist),
                        "window_size_sec": self.WINDOW_SIZE,
                        "raw_emotions": face.get("Emotions", [])
                    }

                    # ==================== EYE & POSTURE METRICS ====================
                    eye_direction = face.get("EyeDirection", {})
                    eye_yaw = round(eye_direction.get("Yaw", 0.0), 2)
                    eye_pitch = round(eye_direction.get("Pitch", 0.0), 2)

                    pose = face.get("Pose", {})
                    head_yaw = round(pose.get("Yaw", 0.0), 2)
                    head_pitch = round(pose.get("Pitch", 0.0), 2)
                    head_roll = round(pose.get("Roll", 0.0), 2)

                    # Eye contact analysis
                    eye_contact_confidence = self._compute_eye_contact_confidence_from_eye_direction(eye_yaw, eye_pitch)
                    self._eye_yaw_hist.append(eye_yaw)
                    self._eye_pitch_hist.append(eye_pitch)

                    # Head posture analysis
                    head_orientation = self._compute_head_orientation_from_pose(head_yaw, head_pitch, head_roll)
                    head_orientation_score = self._map_orientation_to_score(head_orientation, head_yaw, head_pitch, head_roll)
                    connection_strength = self._compute_connection_strength_from_pose(head_yaw, head_pitch, head_roll)
                    
                    self._head_yaw_hist.append(head_yaw)
                    self._head_pitch_hist.append(head_pitch)
                    self._head_roll_hist.append(head_roll)
                    self._conn_hist.append(connection_strength)

                    # Trim histories to maintain window size
                    for hist in [
                        self._eye_yaw_hist, self._eye_pitch_hist,
                        self._head_yaw_hist, self._head_pitch_hist, self._head_roll_hist,
                        self._conn_hist
                    ]:
                        if len(hist) > self.WINDOW_SIZE:
                            hist.pop(0)

                    eye_stability = self._compute_eye_stability_from_eye_history(self._eye_yaw_hist, self._eye_pitch_hist)
                    posture_stability = self._compute_posture_stability(self._conn_hist)

                    eye_contact_analysis = {
                        "eye_contact_confidence": round(eye_contact_confidence, 2),
                        "eye_contact_confidence_tip": self._get_eye_contact_confidence_tip(eye_contact_confidence),
                        "eye_stability": round(eye_stability, 2),
                        "eye_stability_tip": self._get_eye_stability_tip(eye_stability),
                        "timestamp_sec": len(self._eye_yaw_hist),
                        "window_size_sec": self.WINDOW_SIZE,
                        "raw_eye_yaw": eye_yaw,
                        "raw_eye_pitch": eye_pitch
                    }

                    posture_analysis = {
                        "head_orientation": head_orientation,
                        "head_orientation_score": head_orientation_score,  # Added for graphing
                        "head_orientation_tip": self._get_head_orientation_tip(head_orientation),
                        "posture_stability": round(posture_stability, 2),
                        "posture_stability_tip": self._get_posture_stability_tip(posture_stability),
                        "timestamp_sec": len(self._eye_yaw_hist),
                        "window_size_sec": self.WINDOW_SIZE,
                        "raw_head_yaw": head_yaw,
                        "raw_head_pitch": head_pitch,
                        "raw_head_roll": head_roll
                    }

                    return {
                        "eye_contact_analysis": eye_contact_analysis,
                        "posture_analysis": posture_analysis,
                        "facial_expressions": facial_expressions,
                        "technical_quality": technical_quality
                    }

            return self._get_default_response(expression="no_face")

        except Exception as e:
            logger.error("Frame analysis error: %s", str(e))
            return self._get_default_response(expression="error")

    def process_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video file: %s", video_path)
            raise ValueError(f"Cannot open video file: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps == 0:
            logger.error("FPS could not be determined for video: %s", video_path)
            raise ValueError("FPS could not be determined")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = total_frames / fps if fps > 0 else 0

        if self.max_frames is None:
            self.max_frames = max(1, int(video_duration))
            logger.debug("Auto-set max_frames to %d (video duration: %.2f sec)", self.max_frames, video_duration)

        if self.frame_selection_mode == "specific_frames" and self.specific_frames:
            target_frames = sorted(self.specific_frames)[:self.max_frames]
        elif self.frame_selection_mode == "sequential":
            target_frames = list(range(0, total_frames, int(fps)))[:self.max_frames]
        else:
            target_frames = [int(t * fps) for t in self.timestamps][:self.max_frames]

        results = {
            "eye_contact_analysis": [],
            "posture_analysis": [],
            "facial_expressions": [],
            "technical_quality": []
        }

        frame_id = processed_frames = 0

        while cap.isOpened() and processed_frames < self.max_frames:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_id in target_frames:
                timestamp = frame_id / fps
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_rgb = cv2.resize(frame_rgb, (1920, 1080))
                    frame_rgb = cv2.convertScaleAbs(frame_rgb, alpha=1.5, beta=70)
                    frame_rgb = cv2.GaussianBlur(frame_rgb, (5, 5), 0)

                    analysis = self.analyze_frame(frame_rgb)

                    # STORE EYE CONTACT ANALYSIS
                    eye_analysis = analysis.get("eye_contact_analysis", self._get_default_response()["eye_contact_analysis"])
                    results["eye_contact_analysis"].append({
                        "time": timestamp,
                        "analysis": eye_analysis
                    })

                    # STORE POSTURE ANALYSIS
                    posture_analysis = analysis.get("posture_analysis", self._get_default_response()["posture_analysis"])
                    results["posture_analysis"].append({
                        "time": timestamp,
                        "analysis": posture_analysis
                    })

                    # STORE FACIAL EXPRESSIONS
                    facial_expressions = analysis.get("facial_expressions", self._get_default_response()["facial_expressions"])
                    results["facial_expressions"].append({
                        "time": timestamp,
                        "analysis": facial_expressions
                    })

                    # STORE TECHNICAL QUALITY
                    technical_quality = analysis.get("technical_quality", self._get_default_response()["technical_quality"])
                    results["technical_quality"].append({
                        "time": timestamp,
                        "analysis": technical_quality
                    })

                except Exception as e:
                    logger.error("Failed processing frame %d: %s", frame_id, str(e))
                    default = self._get_default_response(expression="error")

                    results["eye_contact_analysis"].append({
                        "time": timestamp,
                        "analysis": default["eye_contact_analysis"]
                    })

                    results["posture_analysis"].append({
                        "time": timestamp,
                        "analysis": default["posture_analysis"]
                    })

                    results["facial_expressions"].append({
                        "time": timestamp,
                        "analysis": default["facial_expressions"]
                    })

                    results["technical_quality"].append({
                        "time": timestamp,
                        "analysis": default["technical_quality"]
                    })

                processed_frames += 1
                target_frames.remove(frame_id)

            frame_id += 1

        cap.release()
        logger.info("Video processing completed for %s", video_path)

        # ===== COMPUTE OVERALL AVERAGES =====
        def compute_overall_averages(r):
            metrics = {
                "avg_eye_contact_confidence": 0.0,
                "avg_eye_stability": 0.0,
                "avg_posture_stability": 0.0,
                "avg_head_orientation_score": 0.0,
                "avg_emotional_score": 0.0,  # Added
                "avg_dominant_emotion": "NEUTRAL",  # Added
                "avg_nervousness_score": 0.0,
                "avg_technical_quality": 0.0,
                "avg_brightness": 0.0,  # Added individual technical metrics
                "avg_sharpness": 0.0,   # Added
                "avg_occlusion": 0.0    # Added (lower is better - less occlusion)
            }

            if r["eye_contact_analysis"]:
                metrics["avg_eye_contact_confidence"] = np.mean([
                    f["analysis"]["eye_contact_confidence"] for f in r["eye_contact_analysis"]
                ])
                metrics["avg_eye_stability"] = np.mean([
                    f["analysis"]["eye_stability"] for f in r["eye_contact_analysis"]
                ])

            if r["posture_analysis"]:
                metrics["avg_posture_stability"] = np.mean([
                    f["analysis"]["posture_stability"] for f in r["posture_analysis"]
                ])
                metrics["avg_head_orientation_score"] = np.mean([
                    f["analysis"]["head_orientation_score"] for f in r["posture_analysis"]
                ])

            if r["facial_expressions"]:
                # Calculate average emotional score
                emotional_scores = [f["analysis"]["score"] for f in r["facial_expressions"]]
                metrics["avg_emotional_score"] = np.mean(emotional_scores)
                
                # Find most common emotion (mode)
                emotions = [f["analysis"]["type"] for f in r["facial_expressions"]]
                if emotions:
                    from collections import Counter
                    emotion_counts = Counter(emotions)
                    metrics["avg_dominant_emotion"] = emotion_counts.most_common(1)[0][0]
                
                metrics["avg_nervousness_score"] = np.mean([
                    f["analysis"]["nervousness_score"] for f in r["facial_expressions"]
                ])

            if r["technical_quality"]:
                metrics["avg_technical_quality"] = np.mean([
                    f["analysis"]["average_score"] for f in r["technical_quality"]
                ])
                
                # Individual technical quality metrics
                metrics["avg_brightness"] = np.mean([
                    f["analysis"]["brightness"] for f in r["technical_quality"]
                ])
                
                metrics["avg_sharpness"] = np.mean([
                    f["analysis"]["sharpness"] for f in r["technical_quality"]
                ])
                
                metrics["avg_occlusion"] = np.mean([
                    f["analysis"]["occlusion"] for f in r["technical_quality"]
                ])

            return {k: round(v, 2) if isinstance(v, (int, float)) else v for k, v in metrics.items()}

        results["overall_averages"] = compute_overall_averages(results)


        # ===== GENERATE TOOLTIPS FOR OVERALL AVERAGES =====
        oa = results["overall_averages"]
        tip_fields = [
            "avg_eye_contact_confidence",
            "avg_eye_stability",
            "avg_posture_stability",
            "avg_head_orientation_score",
            "avg_emotional_score",
            "avg_nervousness_score",
            "avg_technical_quality",
            "avg_brightness",
            "avg_sharpness",
            "avg_occlusion"
        ]

        for field in tip_fields:
            tip_key = field + "_tip"
            oa[tip_key] = self._get_overall_tip(field, oa[field])

        return results
    
# Background task for image processing
async def process_visual_analysis(video_id: str, s3_url: str, description: str, frame_selection_mode: str = "sequential", specific_frames: list = None, timestamps: list = None, max_frames: int = None, frame_interval: float = 1):
    logger.info(f"[INFO] Starting visual analysis for video ID {video_id}")

    bucket = s3_url.split("/")[2].split(".")[0]
    key = "/".join(s3_url.split("/")[3:])

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
        try:
            logger.debug("[DEBUG] Downloading video from s3://%s/%s", bucket, key)
            s3_client.download_file(bucket, key, temp_video.name)
            logger.debug("[DEBUG] Downloaded video to %s", temp_video.name)
        except s3_client.exceptions.ClientError as e:
            logger.error(f"[ERROR] Failed to download from S3: {e}")
            raise

        local_video_path = temp_video.name

        try:
            analyzer = VisualAnalyzer(
                frame_interval=frame_interval,
                max_frames=max_frames,  # Allow None for dynamic calculation
                confidence_threshold=0.5,
                frame_selection_mode=frame_selection_mode,
                specific_frames=specific_frames,
                timestamps=timestamps
            )
            analysis_results = analyzer.process_video(local_video_path)

            image_analysis_collection.insert_one({
                "video_id": ObjectId(video_id),
                "s3_url": s3_url,
                "description": description,
                "visual_insights": analysis_results
            })
            from db import videos_collection
            videos_collection.update_one(
                {"_id": ObjectId(video_id)},
                {"$set": {"status_image": "completed"}}
            )

            logger.info(f"[INFO] Visual analysis data stored for video ID {video_id}")

        except Exception as e:
            logger.error(f"[ERROR] Visual analysis failed for video ID {video_id}: {str(e)}")
            raise

        finally:
            try:
                os.remove(local_video_path)
                logger.info(f"[INFO] Temporary file deleted: {local_video_path}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to delete temporary file: {e}")

