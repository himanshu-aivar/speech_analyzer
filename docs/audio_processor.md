
---

# 🎨 Speech Analyzer – UI Requirements

## 1. **Top Summary Panel (Hero Section)**

Show high-level stats as clean cards (numbers with labels, possibly icons):

* **Overall Engagement Score**

  * Range: `0 – 100`
  * Display: circular gauge or progress bar.
  * Label: *"Engagement Score"*

* **Speaking vs Pause Time**

  * Metric: % of time spent speaking vs pausing.
  * Display: donut chart or two side-by-side percentage bars.
  * Labels: *"Speaking Time"* / *"Pause Time"*.

* **Average Pitch**

  * Unit: Hertz (Hz)
  * Display: numeric value, with optional indicator (low/medium/high).
  * Label: *"Average Pitch (Hz)"*.

* **Average Volume**

  * Unit: normalized RMS (0–1 scale).
  * Display: numeric value, bar indicator.
  * Label: *"Average Volume"*.

---

## 2. **Timeline Analysis (Main Visualization Section)**

Show how metrics change **second by second**:

* **Engagement Over Time**

  * Line chart across duration.
  * Y-axis: Engagement score (0–100).
  * X-axis: Time (seconds).

* **Pitch Over Time**

  * Line chart overlay or separate chart.
  * Y-axis: Pitch (Hz).
  * X-axis: Time (seconds).

* **Volume Over Time**

  * Bar or line chart.
  * Y-axis: Normalized RMS (0–1).
  * X-axis: Time (seconds).

* **Pause Indicators**

  * Overlay on timeline (e.g., shaded vertical bars).
  * Show where `pause=1` (silence detected).

*(Designer should align colors and styles so that pitch, volume, engagement, and pauses are easily distinguishable.)*

---

## 3. **Layout Guidance**

* **Top section** → KPI cards (summary stats).
* **Middle section** → Interactive timeline visualizations (line & bar charts).
* Allow **hover tooltips** on charts for exact values (second, pitch, volume, engagement).

---

✅ **End Result**:
User lands on the page → immediately sees **overall engagement and talk/pause balance**.
Scrolling down → can explore **how engagement, pitch, and volume evolved** throughout the speech.
