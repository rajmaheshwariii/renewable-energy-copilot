# 72-hour forecast and Digital Twin update

This build extends both Forecasting module forecast display and Decision support module Digital Twin planning to 72 hours.

Changes:
- Frontend requests 72 forecast hours.
- Generation Forecast page displays all 72 P10/P50/P90 rows.
- Digital Twin passes all 72 P50 values to `/plan-horizon`.
- Digital Twin shows average uncertainty across the 72-hour horizon.
- Backend forecast and operations endpoints default to 72 hours.
- The horizon planner remains generic and sequentially updates battery SOC across all supplied hours.
- Risk/decision input auto-selects the first meaningful daylight forecast instead of blindly using a night-time zero row.
