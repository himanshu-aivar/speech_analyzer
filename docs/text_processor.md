
# 📝 Text Analyzer — UI Requirements (aligned with Audio layout)

---

## 1) Top Summary Panel (Hero — always visible)

(4–5 KPI cards, left → right)

* **Textual Engagement Score**

  * Value: `textual_engagement_score`
  * Unit: `0 – 100`
  * Visual: circular gauge / large badge + small subtitle *("Calculated from sentiment, clarity, repetition")*.

* **Words Per Minute (WPM)**

  * Value: `words_per_minute` (global)
  * Unit: `words / min`
  * Visual: numeric card with small label (also show `pace_feedback` badge: slow/normal/fast).

* **Speaking vs Pause Time**

  * Derived from `pace_chunks` (speech\_duration sum) and `pause_details` (sum of pause durations).
  * Units: seconds and %
  * Visual: donut chart (Speaking % vs Pause %) + numeric seconds below.

* **Total Filler Words**

  * Value: `filler_words.total`
  * Unit: count (int)
  * Visual: numeric card (if > configurable threshold, show warning badge).

* **Pause Breakdown** *(small card)*

  * Values: `legitimate_pauses`, `awkward_pauses`
  * Unit: counts
  * Visual: two small stacked counters or micro bar (legitimate grey / awkward red).

---

## 2) Timeline Analysis (Main visualization area — center of page)

(Second-by-second won’t apply for text; use 5s chunks and event markers)

* **Pace Over Time**

  * Data source: `pace_chunks` (per 5s) → `wpm` (unit: words/min)
  * Visual: bar or line chart (X = time window, Y = WPM). Hover shows `start_time`, `end_time`, `words_spoken`, `speech_duration`, `wpm`.

* **Pause Markers (Overlay)**

  * Data source: `pause_details` (each item: `start_time`, `duration`, `type`)
  * Visual: shaded vertical regions or thin colored overlays on the pace chart. Color: legitimate = gray, awkward = red. Hover for duration & type.

* **Filler Word Markers**

  * Data source: `filler_words.events` (each event has `word`, `start_time`)
  * Visual: small dot markers on the same timeline; clicking opens a quick popover with the word and timestamp. Color: yellow.

* **(Optional) Chunk Engagement Indicator**

  * Note: backend currently provides only a global `textual_engagement_score`. If you want a per-chunk engagement curve, compute (future) per-chunk textual engagement using the same weighted formula applied to chunk text (sentiment, repetition, clarity). If not implemented, show the global score only in the hero.

---

## 3) Interactive Controls (above or beside timeline)

* Toggle layers: show/hide Fillers / Pauses / Pace bars.
* Zoom: 5s / 30s / full timeline.
* Export: CSV of `pace_chunks` and `pause_details`.
* Seek: clicking on any timeline marker should jump/highlight corresponding place in the transcript and, if available, media playback.

---

## 4) Bottom / Collapsible Panel — Transcript & Event Lists

(Transcript is **not** primary; keep it collapsible/expandable)

* **Transcript (collapsible)**

  * Data source: `transcript` (string)
  * Visual: scrollable text with inline highlights:

    * Fillers → yellow highlight (based on `filler_words.events` timestamps)
    * Awkward pause locations → small red inline marker (link to pause details)
    * Positive words → green underline, negative words → red underline (optional, uses your positive/negative lists)
  * Interaction: clicking a highlighted word jumps timeline to that timestamp.

* **Event List (tabs or side panel)**

  * Filler events (list with word + start\_time)
  * Pauses (list with start\_time + duration + type)
  * Pace chunks (list / table with start\_time, end\_time, words\_spoken, speech\_duration, wpm)
  * Visual: paginated list with small action icons (jump/export).

---

## 5) Mapping: backend fields → exact UI components (quick reference)

* `textual_engagement_score` → Hero circular gauge (0–100).
* `words_per_minute` → Hero numeric card + `pace_feedback` badge (slow/normal/fast).
* `filler_words.total` → Hero numeric card (count).
* `filler_words.events` → Timeline dot markers & transcript highlights (use `start_time`).
* `pace_chunks` → Timeline bar / line chart (per 5s) + hover popovers.
* `pace_variation` → small stat under WPM (std dev, numeric).
* `legitimate_pauses` / `awkward_pauses` → hero/pause breakdown card.
* `pause_details` → Timeline overlays + event list (duration, type, start\_time).
* `transcript` → Collapsible transcript panel with inline highlights and click-to-seek.

---

## 6) Visual & Interaction consistency (follow audio look & feel)

* Keep same page hierarchy and color semantics as audio:

  * Engagement/score primary color (e.g., blue).
  * Good/neutral (speaking, legitimate pause) = gray / green tints.
  * Issues (fillers, awkward pauses) = yellow / red.
* Enable consistent hover tooltips showing exact numeric values and timestamps.
* Keep small legends under/next to the timeline to explain marker colors.

---

## 7) Notes & future improvements (designer/dev callouts)

* **Per-chunk textual engagement**: currently backend returns global `textual_engagement_score` only. If you want a per-chunk engagement chart like audio's engagement-over-time, add a small pass that computes the engagement formula on each `pace_chunk` (use chunk text from transcript word timestamps).
* **Sync with media**: if UI has media playback (video/audio), clicking timeline markers should seek the media to the event timestamp. This gives parity with audio UI behavior.
* **Accessibility**: ensure highlights and colors have good contrast and add tooltip/readout for screen readers.

---

If you want, I’ll now **translate this into a compact Figma spec** (component list + spacing rules + color tokens) or provide the **exact JSON → UI mapping** your frontend dev can use to wire API → components. Which one should I do next?
