# Data Dictionary

## Activity Type
**Label:** Activity Type
**Description:** The type of physical activity (e.g. Running, Trail Running, Indoor Running, Cycling, Walking). Use exact values in WHERE clauses — they are case-sensitive.

## Date
**Label:** Date
**Description:** Date and time when the activity started, format YYYY-MM-DD HH:MM:SS. Use strftime or date_trunc for grouping by day, month, or year.

## Favorite
**Label:** Favorite
**Description:** Whether the activity is marked as a favorite (0 = no, 1 = yes).

## Title
**Label:** Title
**Description:** User-given name or description of the activity (e.g. "Hamburg Morning Run", "Race"). Free text — use ILIKE for fuzzy matching.

## Distance
**Label:** Distance (km)
**Description:** Total distance covered in kilometres. Stored with a comma decimal separator in the source CSV (e.g. "8,76") — always use REPLACE("Distance", ',', '.') before casting to DOUBLE.

## Calories
**Label:** Calories (kcal)
**Description:** Total calories burned during the activity.

## Time
**Label:** Duration (HH:MM:SS)
**Description:** Total duration of the activity in HH:MM:SS format. Use epoch/interval functions to compare durations numerically.

## Avg HR
**Label:** Average Heart Rate (bpm)
**Description:** Average heart rate in beats per minute. Useful for intensity analysis; typical easy-run range is 130–150 bpm.

## Max HR
**Label:** Maximum Heart Rate (bpm)
**Description:** Peak heart rate in beats per minute recorded during the activity.

## Aerobic TE
**Label:** Aerobic Training Effect
**Description:** Garmin Aerobic Training Effect score (0–5) measuring cardiovascular benefit of the session.

## Avg Run Cadence
**Label:** Average Cadence (spm)
**Description:** Average running cadence in steps per minute. Optimal range is generally 170–180 spm.

## Max Run Cadence
**Label:** Maximum Cadence (spm)
**Description:** Maximum running cadence in steps per minute during the activity.

## Avg Pace
**Label:** Average Pace (MM:SS /km)
**Description:** Average pace per kilometre in MM:SS format (e.g. "5:30" means 5 minutes 30 seconds per km). Use safe_pace_to_seconds() for numeric comparisons.

## Best Pace
**Label:** Best Pace (MM:SS /km)
**Description:** Fastest pace achieved during the activity in MM:SS format.

## Total Ascent
**Label:** Total Ascent (m)
**Description:** Total elevation gain in metres. Relevant for hilly or trail runs.

## Total Descent
**Label:** Total Descent (m)
**Description:** Total elevation loss in metres.

## Avg Stride Length
**Label:** Average Stride Length (m)
**Description:** Average stride length in metres. Longer strides at lower cadence can indicate fatigue.

## Avg Vertical Ratio
**Label:** Average Vertical Ratio (%)
**Description:** Vertical oscillation divided by stride length, expressed as a percentage. Lower is more efficient (typical range 6–10%).

## Avg Vertical Oscillation
**Label:** Average Vertical Oscillation (cm)
**Description:** Average bounce height in centimetres per step. Lower values indicate better running economy (typical range 6–13 cm).

## Avg Ground Contact Time
**Label:** Average Ground Contact Time (ms)
**Description:** Average time the foot is in contact with the ground per step, in milliseconds. Lower values indicate a more efficient stride (typical range 160–300 ms).

## Avg GAP
**Label:** Average Grade-Adjusted Pace (MM:SS /km)
**Description:** Pace adjusted for gradient, making uphill and downhill efforts comparable.

## Normalized Power® (NP®)
**Label:** Normalized Power (W)
**Description:** Power output normalised for intensity variations, in watts. Gives a better measure of effort than average power alone.

## Training Stress Score®
**Label:** Training Stress Score (TSS)
**Description:** Garmin Training Stress Score — measures workout intensity and volume. Higher TSS means more physiological stress.

## Avg Power
**Label:** Average Power (W)
**Description:** Average power output in watts during the activity.

## Max Power
**Label:** Maximum Power (W)
**Description:** Peak power output in watts during the activity.

## Steps
**Label:** Total Steps
**Description:** Total number of steps taken during the activity.

## Body Battery Drain
**Label:** Body Battery Drain
**Description:** Change in Garmin Body Battery energy reserves. Negative values (e.g. -15) indicate energy drained. Raw values in the CSV may include a leading quote (e.g. `'-15`) — handled by ignore_errors=true on CSV load.

## Decompression
**Label:** Decompression
**Description:** Decompression indicator (dive-related field from Garmin; typically empty for running activities).

## Best Lap Time
**Label:** Best Lap Time (MM:SS)
**Description:** Time of the fastest lap in MM:SS format.

## Number of Laps
**Label:** Number of Laps
**Description:** Total number of laps completed during the activity.

## Moving Time
**Label:** Moving Time (HH:MM:SS)
**Description:** Total time spent actively moving, excluding pauses, in HH:MM:SS format.

## Elapsed Time
**Label:** Elapsed Time (HH:MM:SS)
**Description:** Total wall-clock time from start to finish including pauses, in HH:MM:SS format.

## Min Elevation
**Label:** Minimum Elevation (m)
**Description:** Lowest elevation point reached during the activity, in metres above sea level.

## Max Elevation
**Label:** Maximum Elevation (m)
**Description:** Highest elevation point reached during the activity, in metres above sea level.
