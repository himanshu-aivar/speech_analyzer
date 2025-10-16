from bson import ObjectId
from datetime import datetime
import numpy as np
from typing import Dict, Any
import requests
import time
from urllib.parse import urlparse
import json
from db import text_analysis_collection, videos_collection
from core.logger import logger
from core.s3_client import s3_client
from settings import settings
import torch

class TextProcessor:
    def get_transcript(self, s3_url: str) -> Dict:
        """Fetch transcript from AssemblyAI using pre-signed S3 URL."""
        parsed = urlparse(s3_url)
        bucket = parsed.netloc.split('.')[0]
        key = parsed.path.lstrip('/')
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=3600,
        )

        headers = {"authorization": settings.ASSEMBLYAI_API_KEY}
        response = requests.post(
            f"{settings.ASSEMBLYAI_API_URL}/transcript",
            json={"audio_url": presigned_url, "speaker_labels": False},
            headers=headers,
        )
        if response.status_code != 200:
            raise Exception(f"AssemblyAI error: {response.json().get('error')}")

        transcript_id = response.json()["id"]

        while True:
            status_response = requests.get(
                f"{settings.ASSEMBLYAI_API_URL}/transcript/{transcript_id}",
                headers=headers,
            )
            status_data = status_response.json()
            if status_data["status"] == "completed":
                return status_data
            elif status_data["status"] == "error":
                raise Exception(f"Transcription failed: {status_data.get('error')}")
            time.sleep(5)

    def analyze_speech_quality(self, full_text: str, description: str) -> Dict[str, Any]:
        """Send transcript text to OpenAI for advanced communication analysis."""

        safe_text = full_text.replace("{", "{{").replace("}", "}}")

        prompt = f"""
        You are an elite communication analyst. Analyze this spoken transcript about: "{description}".

        Return ONLY a valid JSON object with these exact keys:

        1. "clarity": integer 0–100
        2. "confidence_level": one of "low", "medium", "high"
        3. "emotional_tone": one of "positive", "neutral", "negative", "mixed"
        4. "repetition_score": integer 0–100
        5. "choice_of_words": {{
            "appreciated": [string],
            "avoided": [{{"word": string, "alternative": string}}]
        }}
        6. "swot_feedback": {{
            "strengths": [string],
            "weaknesses": [string],
            "opportunities": [string],
            "threats": [string]
        }}
        7. "strategic_way_forward": {{
            "short_term": [string],
            "long_term": [string]
        }}

        Transcript:
        \"\"\"
        {safe_text}
        \"\"\"

        DO NOT explain. DO NOT add notes. DO NOT use markdown. Return ONLY valid JSON.
        """

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "You are a precise communication analyst. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 600,
                "response_format": {"type": "json_object"},
            },
            timeout=15,
        )

        if response.status_code != 200:
            raise Exception(f"OpenAI API Error: {response.status_code} - {response.text}")

        gpt_response = response.json()["choices"][0]["message"]["content"]

        try:
            gpt_dict = json.loads(gpt_response)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse GPT response as JSON: {e}\nRaw response: {gpt_response}")

        return gpt_dict

    # def analyze_transcript(self, transcript: Dict, description: str) -> Dict:
    #     """Main analysis pipeline — AssemblyAI + GPT-4o + Silero VAD pause detection."""
    #     words_info = transcript.get("words", [])
    #     full_text = transcript.get("text", "") or ""

    #     if not words_info:
    #         return self._get_empty_analysis()

    #     audio_duration = float(transcript.get("audio_duration", 0))
    #     if audio_duration == 0 and words_info:
    #         audio_duration = words_info[-1]["end"] / 1000.0

    #     # Download audio locally for Silero VAD
    #     parsed = urlparse(transcript.get("audio_url", "")) if transcript.get("audio_url") else None
    #     local_path = "/tmp/temp_audio.wav"
    #     if parsed:
    #         bucket = parsed.netloc.split('.')[0]
    #         key = parsed.path.lstrip('/')
    #         presigned_url = s3_client.generate_presigned_url(
    #             ClientMethod="get_object",
    #             Params={"Bucket": bucket, "Key": key},
    #             ExpiresIn=3600,
    #         )
    #         r = requests.get(presigned_url)
    #         with open(local_path, "wb") as f:
    #             f.write(r.content)

    #     # Load audio and ensure mono
    #     wav, sr = torchaudio.load(local_path)
    #     if wav.shape[0] > 1:
    #         wav = torch.mean(wav, dim=0, keepdim=True)
    #     if sr != 16000:
    #         wav = torchaudio.functional.resample(wav, sr, 16000)
    #         sr = 16000


    #     model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
    #     get_speech_timestamps = utils[0]  # first element is the function

    #     speech_timestamps = get_speech_timestamps(wav, model, sampling_rate=sr)

    #     # Detect pauses
    #     pauses = []
    #     prev_end = 0.0
    #     for seg in speech_timestamps:
    #         start, end = seg['start'], seg['end']
    #         start_sec = start / sr
    #         end_sec = end / sr
    #         if start_sec - prev_end > 0.3:  # pause >0.3s
    #             pauses.append({
    #                 "start_time": round(prev_end, 2),
    #                 "end_time": round(start_sec, 2),
    #                 "duration": round(start_sec - prev_end, 2)
    #             })
    #         prev_end = end_sec

    #     # Classify pauses: only awkward if very long
    #     long_pause_threshold = 2.0  # seconds
    #     for p in pauses:
    #         p["type"] = "awkward" if p["duration"] > long_pause_threshold else "legitimate"

    #     total_pause_time = sum(p["duration"] for p in pauses)
    #     speech_time = max(0.1, audio_duration - total_pause_time)

    #     # Filler word analysis
    #     filler_words_list = ["uh", "um", "like", "you know", "so", "basically", "actually"]
    #     filler_events = [
    #         {"word": w["text"].lower(), "start_time": w["start"] / 1000.0, "end_time": w["end"] / 1000.0}
    #         for w in words_info if w["text"].lower() in filler_words_list
    #     ]
    #     total_fillers = len(filler_events)
    #     total_words = len([w for w in words_info if w["text"].strip().isalpha()])

    #     wpm = (total_words / speech_time) * 60.0
    #     effective_wpm = (total_words / audio_duration) * 60.0

    #     # Pace analysis (keep original logic)
    #     chunk_duration = 5.0
    #     num_chunks = int(np.ceil(audio_duration / chunk_duration))
    #     pace_chunks = []
    #     chunk_wpms = []
    #     for i in range(num_chunks):
    #         start_time = i * chunk_duration
    #         end_time = min((i + 1) * chunk_duration, audio_duration)
    #         chunk_words = [w for w in words_info if start_time <= w["start"]/1000.0 < end_time]
    #         word_count = len([w for w in chunk_words if w["text"].strip().isalpha()])
    #         wpm_chunk = (word_count / chunk_duration) * 60.0
    #         pace_chunks.append({
    #             "start_time": round(start_time, 2),
    #             "end_time": round(end_time, 2),
    #             "words_spoken": word_count,
    #             "wpm": round(wpm_chunk, 2),
    #             "is_silent": word_count == 0
    #         })
    #         chunk_wpms.append(wpm_chunk)

    #     active_chunk_wpms = [w for c, w in zip(pace_chunks, chunk_wpms) if not c["is_silent"]]
    #     pace_variation = float(np.std(active_chunk_wpms)) if active_chunk_wpms else 0.0
    #     pace_feedback = "slow" if wpm < 100 else "fast" if wpm > 160 else "normal"

    #     # Pause metrics summary
    #     legitimate_pauses = len([p for p in pauses if p["type"] == "legitimate"])
    #     awkward_pauses = len([p for p in pauses if p["type"] == "awkward"])
    #     pause_percentage = (total_pause_time / audio_duration) * 100 if audio_duration > 0 else 0

    #     # GPT qualitative analysis
    #     gpt_insights = self.analyze_speech_quality(full_text, description)

    #     return {
    #         "wpm": round(wpm, 2),
    #         "effective_wpm": round(effective_wpm, 2),
    #         "total_words": total_words,
    #         "duration": round(audio_duration, 2),
    #         "filler_words": {
    #             "count": total_fillers,
    #             "events": filler_events,
    #             "rate_per_minute": round((total_fillers / speech_time) * 60, 2)
    #         },
    #         "pace_analysis": {
    #             "overall_wpm": round(wpm, 2),
    #             "variation": round(pace_variation, 2),
    #             "feedback": pace_feedback,
    #             "chunks": pace_chunks
    #         },
    #         "pauses": {
    #             "total": len(pauses),
    #             "legitimate": legitimate_pauses,
    #             "awkward": awkward_pauses,
    #             "total_duration": round(total_pause_time, 2),
    #             "percentage": round(pause_percentage, 2),
    #             "events": pauses
    #         },
    #         "clarity": gpt_insights["clarity"],
    #         "confidence_level": gpt_insights["confidence_level"],
    #         "emotional_tone": gpt_insights["emotional_tone"],
    #         "repetition_score": gpt_insights["repetition_score"],
    #         "choice_of_words": gpt_insights["choice_of_words"],
    #         "swot_feedback": gpt_insights["swot_feedback"],
    #         "strategic_way_forward": gpt_insights["strategic_way_forward"]
    #     }

    def analyze_transcript(self, transcript: Dict, description: str) -> Dict:
        """Main analysis pipeline — AssemblyAI + GPT-4o + Silero VAD pause detection."""
        words_info = transcript.get("words", [])
        full_text = transcript.get("text", "") or ""

        if not words_info:
            return self._get_empty_analysis()

        audio_duration = float(transcript.get("audio_duration", 0))
        if audio_duration == 0 and words_info:
            audio_duration = words_info[-1]["end"] / 1000.0

        # Detect pauses directly from transcript gaps to avoid media decode issues
        pauses = []
        prev_end = 0.0
        for w in words_info:
            start_sec = float(w.get("start", 0)) / 1000.0
            if start_sec - prev_end > 0.3:
                pauses.append({
                    "start_time": round(prev_end, 2),
                    "end_time": round(start_sec, 2),
                    "duration": round(start_sec - prev_end, 2)
                })
            prev_end = float(w.get("end", prev_end * 1000)) / 1000.0

        # Classify pauses
        long_pause_threshold = 2.0
        for p in pauses:
            p["type"] = "awkward" if p["duration"] > long_pause_threshold else "legitimate"

        total_pause_time = sum(p["duration"] for p in pauses)
        speech_time = max(0.1, audio_duration - total_pause_time)

        # Filler word analysis
        filler_words_list = ["uh", "um", "like", "you know", "so", "basically", "actually"]
        filler_events = [
            {"word": w["text"].lower(), "start_time": w["start"]/1000.0, "end_time": w["end"]/1000.0}
            for w in words_info if w["text"].lower() in filler_words_list
        ]
        total_fillers = len(filler_events)
        total_words = len([w for w in words_info if w["text"].strip().isalpha()])

        wpm = (total_words / speech_time) * 60.0
        effective_wpm = (total_words / audio_duration) * 60.0

        # Pace analysis
        chunk_duration = 5.0
        num_chunks = int(np.ceil(audio_duration / chunk_duration))
        pace_chunks = []
        chunk_wpms = []
        for i in range(num_chunks):
            start_time = i * chunk_duration
            end_time = min((i+1) * chunk_duration, audio_duration)
            chunk_words = [w for w in words_info if start_time <= w["start"]/1000.0 < end_time]
            word_count = len([w for w in chunk_words if w["text"].strip().isalpha()])
            wpm_chunk = (word_count / chunk_duration) * 60.0
            pace_chunks.append({
                "start_time": round(start_time, 2),
                "end_time": round(end_time, 2),
                "words_spoken": word_count,
                "wpm": round(wpm_chunk, 2),
                "is_silent": word_count == 0
            })
            chunk_wpms.append(wpm_chunk)

        active_chunk_wpms = [w for c,w in zip(pace_chunks, chunk_wpms) if not c["is_silent"]]
        pace_variation = float(np.std(active_chunk_wpms)) if active_chunk_wpms else 0.0
        pace_feedback = "slow" if wpm < 100 else "fast" if wpm > 160 else "normal"

        # Pause metrics
        legitimate_pauses = len([p for p in pauses if p["type"]=="legitimate"])
        awkward_pauses = len([p for p in pauses if p["type"]=="awkward"])
        pause_percentage = (total_pause_time / audio_duration) * 100 if audio_duration>0 else 0

        # GPT analysis
        gpt_insights = self.analyze_speech_quality(full_text, description)

        return {
            "wpm": round(wpm,2),
            "effective_wpm": round(effective_wpm,2),
            "total_words": total_words,
            "duration": round(audio_duration,2),
            "filler_words": {
                "count": total_fillers,
                "events": filler_events,
                "rate_per_minute": round((total_fillers / speech_time)*60, 2)
            },
            "pace_analysis": {
                "overall_wpm": round(wpm,2),
                "variation": round(pace_variation,2),
                "feedback": pace_feedback,
                "chunks": pace_chunks
            },
            "pauses": {
                "total": len(pauses),
                "legitimate": legitimate_pauses,
                "awkward": awkward_pauses,
                "total_duration": round(total_pause_time,2),
                "percentage": round(pause_percentage,2),
                "events": pauses
            },
            "clarity": gpt_insights["clarity"],
            "confidence_level": gpt_insights["confidence_level"],
            "emotional_tone": gpt_insights["emotional_tone"],
            "repetition_score": gpt_insights["repetition_score"],
            "choice_of_words": gpt_insights["choice_of_words"],
            "swot_feedback": gpt_insights["swot_feedback"],
            "strategic_way_forward": gpt_insights["strategic_way_forward"]
        }


    def _get_empty_analysis(self):
        return {
            "wpm": 0.0,
            "effective_wpm": 0.0,
            "total_words": 0,
            "duration": 0.0,
            "filler_words": {"count": 0, "events": [], "rate_per_minute": 0},
            "pace_analysis": {"overall_wpm": 0.0, "variation": 0.0, "feedback": "none", "chunks": []},
            "pauses": {
                "total": 0,
                "legitimate": 0,
                "awkward": 0,
                "total_duration": 0,
                "percentage": 0,
                "events": []
            }
        }


# Background task
async def process_video_text(video_id: str, s3_url: str, description: str):
    try:
        processor = TextProcessor()
        transcript = processor.get_transcript(s3_url)
        analysis_results = processor.analyze_transcript(transcript, description)

        text_analysis_collection.insert_one({
            'video_id': ObjectId(video_id),
            'analysis_results': analysis_results,
            'processed_at': datetime.utcnow(),
            'description_context': description
        })

        videos_collection.update_one({"_id": ObjectId(video_id)}, {"$set": {"status_text": "completed"}})

        logger.info(f"✨ Text processing completed with GPT-4o precision for video ID: {video_id}")

    except Exception as e:
        logger.error(f"Error processing text for video ID {video_id}: {str(e)}")
        text_analysis_collection.insert_one({
            'video_id': ObjectId(video_id),
            'error': str(e),
            'processed_at': datetime.utcnow(),
            'description_context': description
        })
