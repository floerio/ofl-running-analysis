---
attributes:
  - name: Activity Type
    type: string
    description: Type of physical activity performed
    optional_names: activity_type,activity
    possible_values: Running,Other,Cycling,Walking

  - name: Date
    type: datetime
    description: "Date and time when the activity started (format: YYYY-MM-DD HH:MM:SS)"
    optional_names: start_date,start_time,activity_date,timestamp

  - name: Favorite
    type: boolean
    description: "Whether the activity is marked as a favorite (0 = no, 1 = yes)"
    optional_names: is_favorite,favorite_flag
    possible_values: 0,1

  - name: Title
    type: string
    description: User-given title or description of the activity
    optional_names: activity_title,name,description

  - name: Distance
    type: float
    description: Total distance covered during the activity in kilometers
    optional_names: distance_km,total_distance,distance

  - name: Calories
    type: integer
    description: Total calories burned during the activity
    optional_names: total_calories,calories_burned,energy

  - name: Time
    type: duration
    description: "Total duration of the activity (format: HH:MM:SS)"
    optional_names: duration,total_time,activity_time

  - name: Avg HR
    type: integer
    description: Average heart rate in beats per minute during the activity
    optional_names: avg_heart_rate,average_hr,mean_hr

  - name: Max HR
    type: integer
    description: Maximum heart rate in beats per minute during the activity
    optional_names: max_heart_rate,peak_hr,highest_hr

  - name: Aerobic TE
    type: float
    description: Aerobic Training Effect score (measure of cardiovascular benefit)
    optional_names: aerobic_training_effect,ate,cardio_score

  - name: Avg Run Cadence
    type: integer
    description: Average running cadence in steps per minute
    optional_names: avg_cadence,average_cadence,steps_per_minute,spm

  - name: Max Run Cadence
    type: integer
    description: Maximum running cadence in steps per minute
    optional_names: max_cadence,peak_cadence,highest_cadence

  - name: Avg Pace
    type: duration
    description: "Average pace per kilometer (format: MM:SS)"
    optional_names: avg_pace,average_pace,pace

  - name: Best Pace
    type: duration
    description: "Best (fastest) pace achieved during the activity (format: MM:SS)"
    optional_names: best_pace,fastest_pace,min_pace

  - name: Total Ascent
    type: integer
    description: Total elevation gain in meters during the activity
    optional_names: total_ascent,elevation_gain,ascent,climb

  - name: Total Descent
    type: integer
    description: Total elevation loss in meters during the activity
    optional_names: total_descent,elevation_loss,descent,drop

  - name: Avg Stride Length
    type: float
    description: Average stride length in meters
    optional_names: avg_stride_length,average_stride,stride

  - name: Avg Vertical Ratio
    type: float
    description: "Average vertical ratio (vertical oscillation divided by stride length, as percentage)"
    optional_names: avg_vertical_ratio,vertical_ratio

  - name: Avg Vertical Oscillation
    type: float
    description: Average vertical oscillation in centimeters (bounce height)
    optional_names: avg_vertical_oscillation,vertical_oscillation,bounce

  - name: Avg Ground Contact Time
    type: integer
    description: Average ground contact time in milliseconds
    optional_names: avg_ground_contact,ground_contact_time,contact_time

  - name: Avg GAP
    type: float
    description: "Average Ground contact time to Air time ratio (GAP)"
    optional_names: avg_gap,gap_ratio

  - name: Normalized Power
    type: integer
    description: Normalized Power - adjusted power output accounting for intensity variations
    optional_names: normalized_power,np,normalized_power

  - name: Training Stress Score
    type: float
    description: Training Stress Score measuring workout intensity and volume
    optional_names: training_stress_score,tss,stress_score

  - name: Avg Power
    type: integer
    description: Average power output in watts during the activity
    optional_names: avg_power,average_power,mean_power

  - name: Max Power
    type: integer
    description: Maximum power output in watts during the activity
    optional_names: max_power,peak_power,highest_power

  - name: Steps
    type: integer
    description: Total number of steps taken during the activity
    optional_names: total_steps,step_count

  - name: Body Battery Drain
    type: integer
    description: Change in body battery energy reserves (negative values indicate drain)
    optional_names: body_battery_drain,energy_drain,battery_change

  - name: Decompression
    type: integer
    description: Decompression time in minutes (recovery time needed)
    optional_names: decompression,recovery_time

  - name: Best Lap Time
    type: duration
    description: "Time of the fastest lap (format: MM:SS)"
    optional_names: best_lap_time,fastest_lap

  - name: Number of Laps
    type: integer
    description: Total number of laps completed during the activity
    optional_names: num_laps,lap_count,total_laps

  - name: Moving Time
    type: duration
    description: "Total time spent moving (excluding pauses, format: HH:MM:SS)"
    optional_names: moving_time,active_time

  - name: Elapsed Time
    type: duration
    description: "Total elapsed time including pauses (format: HH:MM:SS)"
    optional_names: elapsed_time,total_time,wall_time

  - name: Min Elevation
    type: integer
    description: Minimum elevation in meters during the activity
    optional_names: min_elevation,lowest_point,min_altitude

  - name: Max Elevation
    type: integer
    description: Maximum elevation in meters during the activity
    optional_names: max_elevation,highest_point,max_altitude
---