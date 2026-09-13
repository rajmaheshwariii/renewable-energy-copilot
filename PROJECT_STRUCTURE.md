# Renewable Energy Copilot — Organized Project Structure

The project has been renamed around **what each file does**, not around team-member numbers.

```text
renewable_energy_copilot/
├── README.md
├── PROJECT_STRUCTURE.md
├── backend/
│   ├── server.py                         # FastAPI application entry point
│   ├── requirements.txt
│   ├── forecasting/                      # 72-hour renewable generation forecast
│   │   ├── forecast_service.py           # Generate forecasts and explanations
│   │   ├── train_forecast_model.py       # Train/retrain the forecast model
│   │   ├── data/
│   │   │   └── renewable_training_data.csv
│   │   └── saved_model/
│   │       ├── expected_generation_model.json
│   │       ├── forecast_model_settings.json
│   │       ├── historical_generation.csv
│   │       ├── hourly_weather_patterns.csv
│   │       ├── forecast_accuracy_metrics.csv
│   │       └── test_forecast_results.csv
│   ├── risk_and_explainability/          # Risk score + forecast explanation
│   │   ├── risk_calculator.py
│   │   ├── risk_settings.py
│   │   └── forecast_explanation.py
│   ├── decision_support/                 # Actions, simulation, cost and CO₂
│   │   ├── decision_recommendations.py
│   │   ├── scenario_simulator.py
│   │   ├── optimization_comparison.py
│   │   ├── digital_twin_planner.py
│   │   ├── cost_emissions_impact.py
│   │   └── operational_data.csv
│   └── tests/
│       ├── test_decision_support.py
│       └── test_risk_integration.py
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── api.js
    │   ├── model.js
    │   ├── App.css
    │   └── index.css
    └── package.json
```

## Run the application

Backend:
```powershell
cd backend
python -m uvicorn server:app --reload --port 8000
```

Frontend:
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Forecast model retraining:
```powershell
cd backend
python -m forecasting.train_forecast_model
```
