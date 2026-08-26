# Business Glossary

This glossary defines running-specific terms, Garmin metric names, and common
user phrasings. The LLM uses this context to correctly interpret informal or
ambiguous questions and map them to the right columns in the data.

---

## Easy Run / Recovery Run / Zone 2
**Refers to:** A low-intensity aerobic run.
**Maps to:** Activities where `Avg HR` is below approximately 145 bpm, or pace is slower than 6:00 min/km.
**Notes:** Users may say "easy runs", "recovery runs", or "Z2 runs". These are interchangeable.

## Hard Run / Tempo Run / Threshold Run / Speed Work
**Refers to:** A high-intensity run.
**Maps to:** Activities where `Avg HR` is above approximately 165 bpm, or `Training Stress Score®` is high (above 80).
**Notes:** Users may say "hard sessions", "tempo", "intervals", or "quality runs".

## Long Run
**Refers to:** A run with distance above approximately 15 km.
**Maps to:** Activities where `Distance` > 15 (after converting comma decimal separator).
**Notes:** Users may say "long runs" or "LR".

## Race / Competition
**Refers to:** A race or competitive event.
**Maps to:** Activities where `Title` contains words like "Race", "Marathon", "HM", "10K", "5K", or similar race-distance keywords.
**Notes:** Users may say "race", "competition", "event", or refer to specific distances like "my last marathon".

## Trail Run
**Refers to:** An off-road running activity.
**Maps to:** `Activity Type` = 'Trail Running', or `Title` containing "Trail".

## Indoor Run / Treadmill
**Refers to:** A run performed on a treadmill or indoor track.
**Maps to:** `Activity Type` = 'Indoor Running'.

## Hamburg / Home
**Refers to:** Runs performed in Hamburg — the primary training location.
**Maps to:** The majority of activities (no explicit location column; Hamburg is the default location when not otherwise specified).

## Gremersdorf
**Refers to:** Runs performed in Gremersdorf — a secondary training location.
**Maps to:** Activities with `Title` containing "Gremersdorf", or runs from known Gremersdorf dates.

## Kungälv
**Refers to:** Runs performed in Kungälv, Sweden.
**Maps to:** Activities with `Title` containing "Kungälv" or "Kungalv".

## TSS / Training Stress Score
**Refers to:** The overall training load of a session.
**Maps to:** `Training Stress Score®`
**Notes:** Higher values mean more physiological stress. A hard marathon effort might score 250+; an easy hour around 50.

## NP / Normalized Power
**Refers to:** The effort-adjusted power output.
**Maps to:** `Normalized Power® (NP®)`

## HR / Heart Rate
**Refers to:** Heart rate during a run.
**Maps to:** `Avg HR` (average) and `Max HR` (peak). Users may ask about "average heart rate", "HR", "bpm", "pulse".

## Cadence / Steps Per Minute / SPM
**Refers to:** Running cadence.
**Maps to:** `Avg Run Cadence` (average steps per minute) and `Max Run Cadence`.

## Pace
**Refers to:** Speed expressed as time per kilometre (MM:SS format).
**Maps to:** `Avg Pace` (average), `Best Pace` (fastest). Users may say "how fast", "what pace", "speed".
**Notes:** Pace values use a comma decimal separator in the raw CSV and are stored as strings in MM:SS format. Use safe_pace_to_seconds() for numeric comparisons.

## Vertical Oscillation / Bounce
**Refers to:** The vertical movement of the runner's torso per step.
**Maps to:** `Avg Vertical Oscillation` (in centimetres).

## Ground Contact Time / GCT
**Refers to:** Time the foot spends on the ground per step.
**Maps to:** `Avg Ground Contact Time` (in milliseconds).

## GAP / Grade-Adjusted Pace
**Refers to:** Pace adjusted for elevation gradient.
**Maps to:** `Avg GAP`

## Aerobic TE / Training Effect
**Refers to:** Garmin's measure of the cardiovascular benefit of a session.
**Maps to:** `Aerobic TE` (scale 0–5).

## Body Battery
**Refers to:** Garmin's energy reserve metric.
**Maps to:** `Body Battery Drain` — how much energy was consumed during the activity (negative values mean drain).

## Elevation / Ascent / Climb
**Refers to:** Total height gained during a run.
**Maps to:** `Total Ascent` (metres gained). Users may also ask about `Total Descent` for descent.
