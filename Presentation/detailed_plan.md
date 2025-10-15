# 🎬 Real-Time Meeting Feedback System – Design Plan

This project is divided into four core analysis groups, each responsible for a specific modality. Together, they provide a comprehensive evaluation of user communication behavior from audio, text, image, and video.

---

## 🟢 Group 1: Audio-Only Analysis (Voice Feature Extraction)

### 🎯 Goal:
Extract core voice features for calculating **Active Engagement Score** and understanding vocal delivery.

### 🎧 Input:
- Raw audio stream (real-time or from uploaded `.mp4` or `.wav`)

### 🧠 Output:
- `pitch_variation` (per second)
- `volume_variation` (per second)
- `spectral_centroid_variation` (per second)
- `pauses` (0 or 1 per second)
- `active_engagement_score` (scaled 0–100 per second)

### 📐 Method:
- Use short-time window processing (e.g., 1 second)
- Analyze using voice signal metrics
- No dependency on textual content

### 📊 Metrics:
- Engagement time series
- Zones of low/high energy
- Silence percentage

---

## 🟡 Group 2: Speech-to-Text + Language-Based Audio Analysis

### 🎯 Goal:
Extract **textual features** and **temporal speech behavior** for linguistic and pacing analysis.

### 🔠 Input:
- Transcribed speech from audio
- Timestamps from STT model

### 🧠 Output:
- `filler_words` (uh, um, like, you know, etc.)
- `words_per_minute` + `pace_variation`
- `pace_feedback`: fast / slow / normal
- `textual_engagement_score`: based on sentiment, emotion, repetition, intent clarity
- `legitimate_pauses` vs. `awkward_pauses`

### 📐 Method:
- Use timestamps to compute pacing
- Detect silences >500ms → classify via surrounding context
- NLP techniques to evaluate sentence construction and tone

### 📊 Metrics:
- Filler word ratio (per 100 words)
- Average WPM, min/max variation
- Linguistic richness and energy
- Repetition and vagueness flags

---

## 🔵 Group 3: Image-Based Visual Analysis (Per Frame)

### 🎯 Goal:
Analyze speaker’s **face, gaze, posture** to assess expressiveness and attentiveness.

### 🖼️ Input:
- Frame-by-frame images extracted from video (every ~0.5–1s)

### 🧠 Output:
- `facial_expression_states`: emotion and animation (neutral, happy, focused, confused, etc.)
- `eye_contact_ratio`: % of time looking toward camera
- `head_pose`: nodding, tilting, looking down
- `gesture_detection`: hand/face interaction, open/closed posture

### 📐 Method:
- Use face landmarks, iris tracking, pose estimation
- Analyze consistency, emotion variation, and alignment with speech

### 📊 Metrics:
- % time making eye contact
- Expressiveness score
- Posture confidence score

---

## 🟣 Group 4: Video Synthesis and Cross-Modality Checks

### 🎯 Goal:
Fill gaps missed by previous groups using holistic video patterns and redundancy checks.

### 🎥 Input:
- Full video stream
- Outputs from Group 1–3

### 🧠 Output:
- Final summary timeline of communication effectiveness
- Detect mismatch between audio & visual delivery
- Highlight missing or conflicting cues (e.g., confident voice but slouched posture)

### 📐 Method:
- Combine outputs to detect contradictions
- Time-synced aggregation and anomaly detection
- Frame review around flagged segments

### 📊 Metrics:
- Coverage of data by modality
- Confidence score (based on agreement across groups)
- Final feedback quality score

---

## 🧩 Modular Design Considerations

| Component         | Inputs           | Outputs                          | Depends On         |
|------------------|------------------|----------------------------------|--------------------|
| Audio Features    | Audio stream     | Voice variation + pauses         | -                  |
| STT + Pace        | Audio stream     | Transcript + WPM + Filler Words  | Audio / STT        |
| Visual Analysis   | Frames           | Eye contact, pose, expressions   | Video frames       |
| Video Synthesis   | All groups       | Final report + anomaly detection | Group 1–3 outputs  |

---

## 🔄 Processing Flow

```plaintext
[Audio Stream] ─► Group 1 ─┬────────┐
                          └─► Group 2 ─►
[Video Frames] ─► Group 3 ─┘         ┐
                                    ▼
                           ◉ Group 4 (final integrator)
