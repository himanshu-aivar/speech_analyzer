import os
from bson import ObjectId
from datetime import datetime
import numpy as np
import torch
import soundfile as sf
from moviepy.editor import VideoFileClip
import tempfile
import shutil
from silero_vad import load_silero_vad, get_speech_timestamps
from db import audio_analysis_collection, videos_collection
from core.logger import logger
from core.s3_client import s3_client
from scipy.ndimage import gaussian_filter1d
from scipy.signal import medfilt, find_peaks
from scipy.fft import fft, fftfreq
from typing import List, Dict, Any
import traceback


class AudioProcessor:
    def __init__(self):
        self.sr = 16000  # Standard for speech
        self.vad_model = load_silero_vad()
        self.get_speech_timestamps = get_speech_timestamps
        # Configurable parameters
        self.fmin = 60
        self.fmax = 300
        self.frame_length = 512
        self.hop_length = 256  # For pitch detection

    def convert_np(self, obj):
        """Convert numpy types to native Python types"""
        if isinstance(obj, dict):
            return {k: self.convert_np(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_np(i) for i in obj]
        elif isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        return obj

    def extract_audio(self, video_path):
        """Extract audio from video file"""
        audio_path = os.path.splitext(video_path)[0] + '.wav'
        try:
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, verbose=False, logger=None)
            video.close()
        except Exception as e:
            raise Exception(f"Failed to extract audio: {e}")
        return audio_path

    # ---------- ENHANCED LABEL HELPERS (5-level granularity with tips) ----------

    def get_energy_label(self, value: float) -> Dict[str, str]:
        if value < 15:
            return {"label": "Very Low — likely inaudible or disengaged", "tip": "Increase your enthusiasm and volume to engage listeners better."}
        elif value < 35:
            return {"label": "Low — may sound tired or unenthusiastic", "tip": "Add more energy through varied tone and pacing."}
        elif value < 65:
            return {"label": "Moderate — steady and clear delivery", "tip": "This is a good baseline; build on it for more impact."}
        elif value < 90:
            return {"label": "High — energetic and engaging", "tip": "Great job! Maintain this for compelling speech."}
        else:
            return {"label": "Very High — powerful presence (watch for shouting)", "tip": "Ensure it doesn't overwhelm; balance with pauses."}

    def get_pitch_label(self, value: float) -> Dict[str, str]:
        if value < 0.15:
            return {"label": "Extremely Monotone — risks losing audience attention", "tip": "Practice varying your pitch to add expression."}
        elif value < 0.35:
            return {"label": "Slightly Monotone — consider more vocal variety", "tip": "Emphasize key words with higher or lower tones."}
        elif value < 0.7:
            return {"label": "Good Variation — natural and expressive", "tip": "Solid foundation; refine for emphasis."}
        elif value < 1.2:
            return {"label": "High Variation — dynamic and compelling", "tip": "Excellent dynamics—keep it authentic."}
        else:
            return {"label": "Excessive Variation — may sound erratic or nervous", "tip": "Stabilize fluctuations for smoother delivery."}

    def get_volume_label(self, value: float) -> Dict[str, str]:
        if value < -50:
            return {"label": "Too Quiet — likely inaudible without amplification", "tip": "Speak louder or move closer to the mic."}
        elif value < -35:
            return {"label": "Quiet — may strain listeners in noisy environments", "tip": "Project your voice for clarity."}
        elif value < -20:
            return {"label": "Ideal Volume — clear and comfortable for most", "tip": "Perfect level—maintain consistency."}
        elif value < -10:
            return {"label": "Loud — strong presence, but risk of distortion", "tip": "Check for clipping; slightly reduce if needed."}
        else:
            return {"label": "Very Loud — potential clipping or shouting", "tip": "Lower volume to avoid overwhelming listeners."}

    def get_pitch_stability_label(self, stability: float) -> Dict[str, str]:
        if stability > 0.8:
            return {"label": "Very Stable — controlled, confident delivery", "tip": "Great control; use for emphasis in key moments."}
        elif stability > 0.6:
            return {"label": "Stable — good vocal control", "tip": "Build confidence with breathing exercises."}
        elif stability > 0.4:
            return {"label": "Moderate Stability — some fluctuation", "tip": "Practice steady tone to reduce wavers."}
        elif stability > 0.2:
            return {"label": "Unstable — pitch wavers noticeably", "tip": "Relax and focus on smooth transitions."}
        else:
            return {"label": "Highly Unstable — likely due to nervousness or poor technique", "tip": "Warm up your voice and speak slowly."}

    # ---------- ENHANCE TIMELINE ----------
    def enhance_timeline(self, timeline: List[Dict]) -> List[Dict]:
        if not timeline:
            return timeline

        total_seconds = len(timeline)
        speech_indices = [i for i, t in enumerate(timeline) if not t.get("pause", False)]

        enhanced = []

        if not speech_indices:
            return enhanced  # No speech, return empty

        # Smooth speech-only metrics
        energy = np.array([timeline[i]["vocal_energy"] for i in speech_indices])
        pitch = np.array([timeline[i]["pitch_variation_index"] for i in speech_indices])
        volume = np.array([timeline[i]["volume_db"] for i in speech_indices])

        # Adaptive sigma based on speech length
        sigma = max(1.0, len(speech_indices) / 20.0)
        energy_smooth = gaussian_filter1d(energy, sigma=sigma)
        pitch_smooth = gaussian_filter1d(pitch, sigma=sigma)
        volume_smooth = gaussian_filter1d(volume, sigma=sigma)

        # Reconstruct only speech parts
        speech_idx = 0
        for i, t in enumerate(timeline):
            if t.get("pause", False):
                continue

            entry = t.copy()

            e_s = round(float(energy_smooth[speech_idx]), 1)
            p_s = round(float(pitch_smooth[speech_idx]), 3)
            v_s = round(float(volume_smooth[speech_idx]), 1)
            stability = t.get("pitch_stability", 0.0)

            entry.update({
                "vocal_energy_smoothed": e_s,
                "pitch_variation_index_smoothed": p_s,
                "volume_db_smoothed": v_s,
                "pitch_stability": stability,
                "vocal_energy_label": self.get_energy_label(e_s),
                "pitch_variation_label": self.get_pitch_label(p_s),
                "volume_label": self.get_volume_label(v_s),
                "pitch_stability_label": self.get_pitch_stability_label(stability)
            })
            enhanced.append(entry)
            speech_idx += 1

        return enhanced

    # ---------- MAIN PROCESS ----------
    def process_audio(self, audio_path) -> List[Dict[str, Any]]:
        try:
            y, sr = sf.read(audio_path, dtype='float32')
            if sr != self.sr:
                # Simple resampling using scipy
                from scipy.signal import resample
                y = resample(y, int(len(y) * self.sr / sr))
            if y.ndim > 1:
                y = y.mean(axis=1)  # Convert to mono
        except Exception as e:
            raise Exception(f"Failed to load audio: {e}")

        if len(y) < self.sr:  # Handle very short audio
            y = np.pad(y, (0, self.sr - len(y)))

        # Mild denoising using scipy
        y = medfilt(y, kernel_size=3)  # Simple median filter for impulse noise

        wav_torch = torch.from_numpy(y).float()
        speech_ts = self.get_speech_timestamps(wav_torch, self.vad_model, sampling_rate=self.sr, min_speech_duration_ms=500)

        duration = len(y) / self.sr
        total_seconds = int(np.ceil(duration))
        speech_mask = [False] * total_seconds

        for seg in speech_ts:
            start_sec = seg['start'] // self.sr
            end_sec = (seg['end'] + self.sr - 1) // self.sr
            for s in range(start_sec, min(end_sec, total_seconds)):
                speech_mask[s] = True

        # Simple pitch detection using autocorrelation (no librosa)
        def simple_pitch_detection(signal, sr, fmin=60, fmax=300):
            # Autocorrelation-based pitch detection
            autocorr = np.correlate(signal, signal, mode='full')
            autocorr = autocorr[len(autocorr)//2:]
            
            # Find peaks in autocorrelation
            min_period = int(sr / fmax)
            max_period = int(sr / fmin)
            
            if len(autocorr) < max_period:
                return np.zeros(len(signal)), np.zeros(len(signal))
            
            peaks, _ = find_peaks(autocorr[min_period:max_period])
            if len(peaks) == 0:
                return np.zeros(len(signal)), np.zeros(len(signal))
            
            # Convert peak positions to frequencies
            fundamental_period = peaks[0] + min_period
            fundamental_freq = sr / fundamental_period
            
            # Create pitch contour
            pitch_contour = np.full(len(signal), fundamental_freq)
            voiced_probs = np.ones(len(signal)) * 0.8  # Assume mostly voiced
            
            return pitch_contour, voiced_probs

        # Compute pitch for the entire audio
        f0, voiced_probs = simple_pitch_detection(y, self.sr, self.fmin, self.fmax)

        timeline = []

        for i in range(total_seconds):
            start_sample = i * self.sr
            end_sample = min((i + 1) * self.sr, len(y))
            chunk = y[start_sample:end_sample]

            if not speech_mask[i] or len(chunk) < self.sr // 2:  # Skip short/non-speech
                timeline.append({
                    "second": i,
                    "pause": True,
                    "vocal_energy": 0.0,
                    "pitch_variation_index": 0.0,
                    "volume_db": -60.0,
                    "pitch_stability": 0.0
                })
                continue

            # --- Volume ---
            rms = np.sqrt(np.mean(chunk ** 2 + 1e-9))
            volume_db = 20 * np.log10(max(rms, 1e-8))
            volume_db = max(volume_db, -60.0)

            # --- Pitch & Stability (from precomputed) ---
            f0_chunk = f0[start_sample:end_sample]
            probs_chunk = voiced_probs[start_sample:end_sample]

            voiced = probs_chunk > 0.5  # Reliable threshold
            pitch_var = 0.0
            pitch_stability = 1.0

            if np.sum(voiced) >= 3:  # Lowered threshold for reliability
                f0_voiced = f0_chunk[voiced]
                pitch_std = np.std(f0_voiced)
                pitch_mean = np.mean(f0_voiced)
                if pitch_mean > 1e-6:
                    cv = pitch_std / pitch_mean
                    pitch_var = min(cv, 2.0)
                    pitch_stability = max(0.0, 1.0 - min(cv, 1.0))
            else:
                pitch_stability = 0.0

            # --- Vocal Energy ---
            norm_volume = (volume_db + 70) / 70  # Adjusted normalization to boost typical values
            norm_volume = np.clip(norm_volume, 0, 1)
            voiced_ratio = np.mean(voiced) if np.sum(voiced) > 0 else 0.0
            vocal_energy = (
                0.5 * norm_volume +
                0.3 * min(pitch_var, 1.0) +
                0.2 * voiced_ratio
            ) * 100
            vocal_energy = np.clip(vocal_energy, 0, 100)

            timeline.append({
                "second": i,
                "pause": False,
                "vocal_energy": round(float(vocal_energy), 1),
                "pitch_variation_index": round(float(pitch_var), 3),
                "volume_db": round(float(volume_db), 1),
                "pitch_stability": round(float(pitch_stability), 2)
            })

        enhanced_timeline = self.enhance_timeline(timeline)

        # Add aggregates for interpretability
        if speech_ts:
            aggregates = {
                "avg_vocal_energy": round(float(np.mean([t["vocal_energy_smoothed"] for t in enhanced_timeline])), 1),
                "avg_pitch_variation": round(float(np.mean([t["pitch_variation_index_smoothed"] for t in enhanced_timeline])), 3),
                "avg_volume_db": round(float(np.mean([t["volume_db_smoothed"] for t in enhanced_timeline])), 1),
                "avg_pitch_stability": round(float(np.mean([t["pitch_stability"] for t in enhanced_timeline])), 2),
                # Overall tips based on avgs (example)
                "overall_advice": "Focus on consistency if averages vary widely."
            }
        else:
            aggregates = {}

        return {"timeline": enhanced_timeline, "aggregates": aggregates}


# ---------- ASYNC HANDLER ----------
async def process_video_audio(video_id: str, s3_bucket: str, s3_key: str):
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        video_path = os.path.join(temp_dir, os.path.basename(s3_key))
        s3_client.download_file(s3_bucket, s3_key, video_path)

        processor = AudioProcessor()
        audio_path = processor.extract_audio(video_path)
        analysis_results = processor.process_audio(audio_path)
        analysis_results = processor.convert_np(analysis_results)  # 🔑 Critical fix

        audio_analysis_collection.insert_one({
            "video_id": ObjectId(video_id),
            "analysis_results": analysis_results,
            "processed_at": datetime.utcnow()
        })

        videos_collection.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {"status_audio": "completed"}}
        )

        logger.info(f"Audio processing completed for video ID: {video_id}")

    except Exception as e:
        logger.error(f"Error processing audio for video ID {video_id}: {e}")
        logger.error(traceback.format_exc())

        audio_analysis_collection.insert_one({
            "video_id": ObjectId(video_id),
            "error": str(e),
            "traceback": traceback.format_exc(),
            "processed_at": datetime.utcnow()
        })

        videos_collection.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {"status_audio": "failed"}}
        )

    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)