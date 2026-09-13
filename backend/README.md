# Renewable Energy Copilot Backend

This backend runs the operational decision layer only. It does not include a forecasting model or risk model.

The decision engine requires upstream `predicted_generation_kw`, `risk_score`, and `forecast_uncertainty_pct`. The UI leaves these values blank until they are supplied rather than inventing them.

## Main services
- Single-hour operational recommendation
- What-If comparison, including grid-export availability
- Optimization-mode comparison
- Multiple scenario comparison
- Sequential multi-hour / 24-hour battery planning
- Impact calculation for cost, backup CO2 and unserved energy

## Run
```bash
python -m pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8000
```

Open `http://127.0.0.1:8000/docs` for the API documentation.
