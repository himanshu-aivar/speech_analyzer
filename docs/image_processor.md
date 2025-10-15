# 🖼️ Image (Visual) Analyzer — UI Requirements (aligned with Audio & Text)

---

## 1) Quick overview — what the backend produces (keys & units)

* `facial_expressions`: list of `{ time: sec, expression: string }`

  * Unit: seconds, expression labels (happy, sad, angry, confused, surprised, calm, unknown, error, no\_face).
* `head_pose`: list of `{ time: sec, angle: { pitch: deg, yaw: deg, roll: deg } }`

  * Unit: degrees (°).
* `eye_contact`: list of `{ time: sec, eye_contact: { confidence: 0.0–1.0, direction: string } }`

  * Unit: confidence (0–1) → show as percentage (0–100%); direction = center/left/right/up/down.
* `pose_analysis`: list of `{ time: sec, pose: { direction: str, engagement: "high|medium|low", engagement_score: 0.0–1.0 } }`

  * Unit: engagement\_score (0–1) → show as 0–100 scale.
* `emotional_accuracy`: list of `{ time: sec, score: float }`

  * Unit: backend uses mapping in approx. range \[-1.0 .. +1.0] (happy=+1, sad=-1, surprised≈0). Show as **Emotional Valence** (-100 to +100) with sign.
* Per-frame timestamps are seconds (float). Thumbnails/frames are saved as `frame_<id>.jpg`.

---

## 2) Top Summary Panel (Hero) — 4–5 KPI cards (left → right)

Keep same visual hierarchy & color semantics used for Audio/Text.

* **Visual Engagement Score**

  * Source: average of `pose_analysis.*.engagement_score` across frames → scaled to `0–100`.
  * Unit: `0–100`
  * Visual: large circular gauge or progress badge. Subtitle: *"Average visual attention/pose engagement."*

* **Average Eye Contact**

  * Source: mean of `eye_contact.*.eye_contact.confidence` → percent.
  * Unit: `%` (0–100%)
  * Visual: numeric card + small indicator (Good / Low). If mean < threshold (e.g., 50%), show warning.

* **Emotional Valence**

  * Source: mean of `emotional_accuracy` \* 100 → range `-100 .. +100`
  * Unit: signed score (negative = negative valence, positive = positive valence)
  * Visual: horizontal delta bar with center at 0 (neutral). Color: green for positive, red for negative, gray at 0.

* **Face Detection Rate**

  * Source: % frames where `facial_expressions` ≠ `no_face`/`error` / total analyzed frames.
  * Unit: `%`
  * Visual: small donut or numeric card. If < threshold, show “No face detected often” indicator.

* **Expression Distribution (compact)** *(small card or icon cluster)*

  * Source: aggregated counts from `facial_expressions` by label → show top 3 with small percent chips.
  * Visual: micro stacked bar or three chips (e.g., Happy 45%, Neutral 30%, Surprised 10%).

---

## 3) Timeline Analysis (Main visualization area)

Single horizontal time axis (X = time in seconds). Stack aligned visual layers so developer/designer can toggle layers. Provide hover/tooltips for exact values.

* **Pose Engagement Over Time (line)**

  * Source: `pose_analysis.*.engagement_score` → Y = 0–100.
  * Visual: primary line chart (solid) with points per frame.

* **Head Pose (pitch / yaw / roll) Over Time (multi-line)**

  * Source: `head_pose.*.angle` → Y = degrees.
  * Visual: three lines (pitch, yaw, roll). Hover shows exact degrees at timestamp.

* **Eye Contact Confidence Over Time (line or bars)**

  * Source: `eye_contact.*.eye_contact.confidence` → displayed as % on secondary Y axis.
  * Visual: line with shaded area for low-confidence thresholds.

* **Emotional Valence Over Time (line/area)**

  * Source: `emotional_accuracy.*` → mapped -100..+100.
  * Visual: colored area above/below zero (green above, red below).

* **Facial Expression Band / Markers**

  * Source: `facial_expressions.*.expression` (categorical).
  * Visual options:

    * Colored band on top of timeline showing expression label per frame (categorical strip).
    * Or dot markers placed on timeline with color-coded icons (happy=yellow/green, sad=blue, angry=red, neutral=gray). Hover shows time & label.

* **No-face/Error Markers**

  * If frame yields `no_face` or `error`, show a distinct red cross marker on timeline. Useful for QC.

* **Thumbnail strip (optional, below timeline)**

  * Show small frame thumbnails at intervals or at marker hover/click. Clicking opens Frame Viewer at that frame.

---

## 4) Interactive Controls & Filters (above or to the side)

* Layer toggles: Engagement / Head Pose / Eye Contact / Emotional Valence / Expressions / Thumbnails.
* Time zoom: frame / 5s / 30s / full.
* Confidence threshold slider (filter frames below X confidence).
* Expression filter: show only frames with selected expression(s) (e.g., "show surprised frames").
* Export: CSV/JSON with per-frame metrics; download selected frame images as ZIP.

---

## 5) Frame Viewer & Detail Panel (collapsible, right or bottom)

When user clicks a timeline marker or thumbnail:

* **Large Frame Display** (full-size selected frame).

  * Overlay options (toggle): MediaPipe face landmarks, Rekognition bounding box, gaze vector arrow.

* **Detail card (numeric & textual)** for selected frame:

  * Timestamp (sec)
  * Expression: `expression` (label)
  * Emotional Valence: signed score (-100..+100) + short interpretation (e.g., "positive")
  * Head Pose: `pitch, yaw, roll` in degrees (show as numbers + small rotated head icon depicting direction)
  * Eye Contact: `confidence (%)` and `direction` (center/left/right/up/down)
  * Pose Analysis: `direction`, `engagement` (high/medium/low), `engagement_score` (0–100)
  * Rekognition raw confidence (if available) — optional small debug panel.

* **Actions**: jump to previous/next frame, mark frame for review, attach note, export image.

---

## 6) Mapping: backend → exact UI components (quick reference)

* `pose_analysis.*.engagement_score` → Timeline line chart & **Visual Engagement Score** (hero average). Display as 0–100.
* `eye_contact.*.eye_contact.confidence` → Timeline line & **Average Eye Contact** (hero, %).
* `emotional_accuracy.*.score` → Timeline area & **Emotional Valence** (hero, -100..+100).
* `facial_expressions.*.expression` → Expression band / markers & **Expression Distribution** (hero card).
* `head_pose.*.angle` → Multi-line chart (pitch/yaw/roll) + Frame detail numeric readout (degrees).
* `results` timestamps (time) → all timeline X axes, thumbnail times, frame viewer seek.
* No-face / error → red markers & flag in face detection rate.

---

## 7) Visual and interaction consistency (with Audio & Text)

* Use same primary color for **Engagement** across modules (Audio/Text/Visual).
* Use green = good / positive; red = issue/negative; gray = neutral.
* Hover tooltips everywhere with exact numeric values & timestamp, consistent formatting (e.g., `2.45 s`, `Yaw: -12.3°`, `Eye contact: 72%`).
* Clicking any timeline point should **seek the media** (if available) to the same timestamp — parity with Audio/Text flows.

---

## 8) UX notes & recommended thresholds (designer/dev callouts)

* Eye contact: treat `< 0.5` as low (show warning).
* Engagement label mapping: `>0.8` → high, `>0.5` → medium, else low (same logic used in backend). Display both label and numeric score.
* Emotional valence: show polarity and magnitude; do not over-interpret a single frame — show averages and distributions.
* If face detection rate is low (<60%), surface a prominent notice: *"Visual analysis may be unreliable — face not consistently visible."*

---

## 9) Future enhancements (nice-to-have)

* Per-chunk visual engagement curve (e.g., average over 5s or aligned with text pace chunks) to match Text/Audio chunking.
* Gaze heatmap over the whole recording (where the speaker looked most).
* Confidence bands (show standard deviation) for head pose and emotion scores.
* Small animated preview that scrubs the timeline with frame thumbnails (quick scouting mode).

---
