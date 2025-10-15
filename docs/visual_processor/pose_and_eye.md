
---

# 👁️ Eye-related Metrics

### 1. **Eye Contact Confidence**

* **What it means**: How directly the speaker is looking at the audience/camera.
* **User interpretation**:

  * High (close to 1.0) → strong eye contact, engaging.
  * Medium → occasional glance away, partially engaged.
  * Low → looking elsewhere, disengaged.
* **UI idea**: Gauge/bar from 0–100%, or a per-second graph line.

### 2. **Eye Stability**

* **What it means**: How steady the gaze is (are eyes darting around or focused).
* **User interpretation**:

  * High stability → calm, confident, focused.
  * Low stability → nervousness, distraction.
* **UI idea**: Trend line showing variance; or a “steady vs. restless” tag.

---

# 🧑 Posture-related Metrics

### 3. **Head Orientation**

* **What it means**: Where the speaker’s head is directed.
* **Categories**: forward (audience), left, right, up, down, tilt.
* **User interpretation**:

  * *Forward* → addressing audience directly.
  * *Side/Down* → possible disengagement or hesitation.
  * *Tilt* → could indicate curiosity, emphasis, or distraction.
* **UI idea**: Small icon/arrow showing head direction per second.

### 4. **Posture Stability (Connection Strength)**

* **What it means**: How well the speaker keeps their head aligned and connected to the audience.
* **User interpretation**:

  * High → strong presence, connected to audience.
  * Medium → some wandering but generally aligned.
  * Low → frequent shifts, weaker presence.
* **UI idea**: A score (0–100%) and a time-series trend to show consistency.

---

# 🎯 How Users Will Interact

* On the **dashboard per second**:

  * Graph line for *eye contact confidence* and *connection strength*.
  * Trend indicator for *eye stability*.
  * Icon/label for *head orientation*.

* In the **summary report**:

  * Average values across the session.
  * Heatmap of high/low engagement moments.
  * Feedback like:

    * *“Strong eye contact 72% of the time”*
    * *“Occasionally looked away to the right (15%)”*
    * *“Maintained steady gaze 80% of the time → confident delivery”*.

---

👉 So effectively:

* **Confidence & Stability** = *quality scores (numerical/graph)*
* **Orientation** = *categorical feedback (direction icons/labels)*

---

Would you like me to **design a unified output schema** (like a JSON or Python dict) that contains all 4 metrics in a clean structure, ready to be visualized for the user?
