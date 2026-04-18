# AgriMaster Pro — Algorithm Specification

## Overview
The Decision Engine runs every 30 seconds with 10 layers executed sequentially.
No external ML — uses statistics, rule-based logic, and linear regression.

## Layer Execution Order

| Layer | Name | Priority | Key Config |
|-------|------|----------|------------|
| L0 | Input Validation & Sensor Fusion | Always | `algorithm.plausibility.*` |
| L1 | Plant Stress Scoring | Always | Plant profiles from `plants_db.json` |
| L2 | Predictive Trend Analysis | Always | `algorithm.history_window_readings` |
| L3 | Irrigation Decision | Critical | `algorithm.irrigation.*` |
| L4 | pH Correction | High | `algorithm.ph.*` |
| L5 | Ventilation Control | Medium | `algorithm.ventilation.*` |
| L6 | Supplemental Lighting | Low | `algorithm.lighting.*` |
| L7 | Fertilizer Scheduling | Low | `algorithm.fertilizer.*` |
| L8 | Misting & Humidity | Low | `algorithm.misting.*` |
| L9 | Conflict Resolution | Always | `algorithm.conflicts.*` |
| L10 | Anomaly Detection & Alerts | Always | `alerts.thresholds.*` |

## Decision Flow

```
Sensor Data (every 5s from ESP32)
        │
        ▼
┌─── L0: Validate ───┐
│ Plausibility check  │
│ Outlier detection   │
│ Cross-validation    │
└─────────┬───────────┘
          ▼
┌─── L1: Stress ─────┐
│ Per-plant scoring   │
│ Weighted by params  │
│ Status assignment   │
└─────────┬───────────┘
          ▼
┌─── L2: Predict ────┐
│ Linear regression   │
│ Slope per minute    │
│ Time-to-critical    │
└─────────┬───────────┘
          ▼
┌─── L3-L8: Actions ─┐
│ Irrigation (L3)     │
│ pH dosing (L4)      │
│ Fan speed (L5)      │
│ Grow light (L6)     │
│ Fertilizer (L7)     │
│ Misting (L8)        │
└─────────┬───────────┘
          ▼
┌─── L9: Resolve ────┐
│ Priority sort       │
│ Conflict removal    │
│ Relay count limit   │
└─────────┬───────────┘
          ▼
┌─── L10: Alerts ────┐
│ Threshold checks    │
│ Sensor fault detect │
│ Deduplication       │
└─────────┬───────────┘
          ▼
   MQTT Commands → ESP32
   WebSocket → Dashboard
```

## Stress Score Formula
```
stress(current, min, max, opt):
  if in range: abs(current - opt) / (max - min) * 0.3
  if below min: 0.3 + (min-current)/min * 0.7, capped at 1.0
  if above max: 0.3 + (current-max)/max * 0.7, capped at 1.0
  if range_size <= 0: 0.0 (degenerate)
  if current is NaN: 0.5 (unknown)

total = temp*0.25 + humidity*0.20 + soil*0.20 + ph*0.20 + light*0.10 + co2*0.05
```

## Status Thresholds
- 0.00-0.15: Thriving 🌿
- 0.16-0.35: Good ✅
- 0.36-0.55: Stressed ⚠️
- 0.56-0.75: Critical 🔴
- 0.76-1.00: Dying ☠️

## Conflict Resolution Rules
1. Never pH-up and pH-down simultaneously
2. Never pH dosing and irrigation simultaneously
3. Never fertilizer and pH correction simultaneously
4. Max 3 relays active (15A power budget)
5. Priority: Emergency > pH > Critical > Ventilation > Preventive > Scheduled > Misting > Light > Fertilizer

## Safety Limits
- pH dose: max 30 seconds, 2-hour equilibration cooldown, 4-hour cross-type safety
- Irrigation: 30s-600s duration bounds
- Midday irrigation suppressed (11:00-14:00) unless CRITICAL
- Night misting suppressed 22:00-06:00 (fungal risk)
- Fan speed: max 30% change per cycle (motor protection), hysteresis band ±0.5°C
- Temperature >42°C → CRITICAL alert
- Startup misting suppression (B-07)

## State Persistence
Algorithm state (last action times, overrides) stored in `algorithm_state` SQLite table.
Restored on backend restart via `AlgorithmStateManager.restore_from_db()`.

## Override Mechanism
- POST `/api/algorithm/override` with `{action, duration_minutes}`
- Stored in `AlgorithmStateManager._overrides` dict
- Checked before each action: `is_overridden(target)` → skip action
- Expires automatically after `duration_minutes`

## Key Thresholds (from system.yaml)

| Parameter | Config Key | Default |
|-----------|-----------|---------|
| Irrigation critical factor | `algorithm.irrigation.critical_moisture_factor` | 0.85 |
| Predictive threshold | `algorithm.irrigation.predictive_minutes_threshold` | 45 min |
| Midday suppress window | `algorithm.irrigation.midday_suppress_start/end` | 11-14 |
| pH hysteresis band | `algorithm.ph.hysteresis_band` | 0.3 |
| pH equilibration | `algorithm.ph.equilibration_hours` | 2 hours |
| Fan humidity force | `algorithm.ventilation.humidity_force_min_pct` | 40% |
| Misting high deficit | `algorithm.misting.high_deficit_threshold` | 15% |
| Max simultaneous relays | `algorithm.conflicts.max_simultaneous_relays` | 3 |
