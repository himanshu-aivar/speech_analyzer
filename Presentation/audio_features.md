

# 🎙️ Voice Feature Breakdown

This system analyzes a speaker’s voice **second by second** from a video to detect 4 key features:

---

## 1. 🎵 **Pitch**

### ✅ What is it?

Pitch refers to **how high or low** someone’s voice sounds. It’s the **frequency** of the voice — for example, a deeper voice has lower pitch, and a high-pitched voice sounds sharper.

### 🧠 Why it matters:

Pitch changes show **emotional variation**. A flat, monotone pitch can sound robotic or disengaged, while natural pitch variation suggests liveliness and interest.

### 🛠 How we detect it:

We use a scientific method called `YIN` from `librosa` which estimates the **average pitch in Hertz (Hz)** for each 1-second chunk of audio.

### 📏 Output example:

```json
"pitch": 185.23  // measured in Hz
```

---

## 2. 🔊 **Volume**

### ✅ What is it?

Volume measures **how loud the speaker is**. Technically, it’s the **energy or amplitude** of the audio signal.

### 🧠 Why it matters:

Speaking too softly might mean lack of confidence, while shouting could feel aggressive. Balanced loudness helps with **clarity and engagement**.

### 🛠 How we detect it:

We calculate the **Root Mean Square (RMS)** of the audio, which gives us the average loudness, and then **normalize** it so it's comparable across different audio clips.

### 📏 Output example:

```json
"volume": 0.0452  // normalized (between 0 and 1 typically)
```

---

## 3. 🛑 **Pause (Silence Detection)**

### ✅ What is it?

This checks whether the person was **actually speaking** during that second or if it was silent.

### 🧠 Why it matters:

Too many or long pauses can signal nervousness or lack of clarity. Moderate pauses are natural and can enhance delivery.

### 🛠 How we detect it:

We use an **AI model called Silero VAD** (Voice Activity Detection), which checks:

* Was there speech in this 1-second chunk?

  * If yes → `pause = 0`
  * If no → `pause = 1`

### 📏 Output example:

```json
"pause": 0  // 0 = speaking, 1 = silent
```

---


## 4.🎯 Active Engagement Score 

The **Active Engagement Score** is a number between **0 and 100** that reflects **how engaging or expressive** a speaker sounds during each second of a talk or meeting.

This score is **not about the content of speech**, but **how it's delivered** — it quantifies **speaking energy, variation, and presence** in real time.

---

## ⚙️ How We Calculate It: The 4 Core Components

The score is built from **four voice-based features**, measured second-by-second:

---

### 1. 🎵 **Pitch Variation**

**What it is**:
Pitch refers to how high or low someone’s voice sounds. Think of it like musical notes — a speaker might shift between low and high tones as they speak.

**Why it matters**:
Natural pitch variation keeps speech interesting and helps express emotion. People who sound confident and energetic tend to vary their pitch.

**What we measure**:
We calculate the **standard deviation** of pitch within a second to understand how much it's changing.

| Variation Level | Interpretation                               |
| --------------- | -------------------------------------------- |
| High variation  | Expressive, confident, emotionally connected |
| Low variation   | Monotone, robotic, disengaged                |

---

### 2. 🔊 **Volume Variation**

**What it is**:
Volume is the loudness of the voice. Variation in volume — like going from quiet to strong — makes speech dynamic.

**Why it matters**:
Lively speakers tend to emphasize certain words, raise or lower their voice to maintain interest, and avoid sounding flat.

**What we measure**:
We look at **how much the volume changes** over the recent few seconds. If the volume stays too constant, it may feel dull.

| Variation Level | Interpretation                 |
| --------------- | ------------------------------ |
| High variation  | Natural delivery with emphasis |
| Low variation   | Dull or tired speech           |

---

### 3. 🌈 **Spectral Centroid Variation (Voice Texture / Brightness)**

**What it is**:
This captures the **texture or brightness** of the voice — whether it sounds sharp, clear, or more muffled and low.

**Why it matters**:
Energetic speech usually has a brighter tone. This measure reflects how lively the voice “feels” acoustically.

**What we measure**:
We calculate **how much this brightness value changes**, just like pitch and volume.

| Variation Level | Interpretation                        |
| --------------- | ------------------------------------- |
| High variation  | Clear, energetic, and dynamic tone    |
| Low variation   | Flat, low-energy, or emotionless tone |

---

### 4. ⏸️ **Pauses (Silence Detection)**

**What it is**:
This checks whether the person **stops speaking** for a noticeable period during the second.

**Why it matters**:
Frequent pauses or hesitations can indicate low confidence or disengagement. Short, natural pauses are fine — but too many reduce the sense of momentum.

**What we measure**:
We detect whether a second of audio contains speech or is silent using an AI-based voice activity detector.

| Pause Value | Interpretation                |
| ----------- | ----------------------------- |
| 0           | Speech detected (active)      |
| 1           | Silence or no voice (passive) |

---

## 🧮 Final Score Formula

We combine these features into a formula that balances all aspects:

```
Active Engagement Score =
10 × (
   0.35 × pitch_variation +
   0.35 × volume_variation +
   0.20 × tone_variation -
   0.10 × pauses
)
```

Then we **scale it to 0–100** for easy interpretation.

---

## 📊 How to Interpret the Score

| Score Range | What It Means                                            |
| ----------- | -------------------------------------------------------- |
| **80–100**  | 🌟 Highly engaging – expressive, confident, and natural  |
| **60–79**   | ✅ Moderately engaging – some variation, mostly confident |
| **40–59**   | ⚠️ Somewhat disengaging – may sound flat or uncertain    |
| **0–39**    | 🚫 Low engagement – monotone, hesitant, or passive       |

---

## 🔍 Real-World Example

Imagine two people giving a pitch:

* **Speaker A** speaks with varied tone, natural loudness shifts, and no awkward pauses → they get an **engagement score of 87**.
* **Speaker B** speaks in a monotone, at the same volume throughout, with frequent hesitations → they get a **score of 35**.

This metric helps us **quantify speaker presence and energy**, so we can offer **feedback or coaching** to improve communication.

---

Would you like this in presentation slides or as a one-pager PDF as well?
