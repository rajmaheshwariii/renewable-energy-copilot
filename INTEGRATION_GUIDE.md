# Renewable Energy Copilot — Fully Integrated Prototype

This package connects the original React UI to all three project modules through FastAPI:

```text
Forecasting module forecasting
        ↓
P50 generation + uncertainty + SHAP
        ↓
Risk assessment module risk engine
        ↓
risk score / reasons / components
        ↓
Decision support module decision engine
        ↓
battery / backup / export / curtailment
        ↓
What-If / optimization modes / 24-hour planning / impact
```

## Forecasting module dataset

The active training file is:

`backend/forecasting/renewable_training_preprocessed.csv`

It contains **9,792 hourly rows** covering the two original plants plus ten synthetic augmented plant variants. The augmented variants are used only for model training. The dashboard exposes only `Plant_1` and `Plant_2` because those are the real/original runtime plants represented by the operational dataset.

The timestamp range is still approximately 34 days. The larger row count comes from augmentation, not additional months of real history.

## Leakage-safe evaluation

The forecasting evaluation is split by **target timestamp**, not randomly:

- earliest 70% of timestamps: training
- next 15%: validation / uncertainty calibration
- latest 15%: held-out test

This prevents a synthetic variant of a future timestamp from landing in training while a nearly identical original row for that same timestamp lands in test.

Current held-out results from the shipped saved_model:

- XGBoost P50 MAE: **947.82 kW**
- XGBoost P50 RMSE: **1732.23 kW**
- XGBoost P50 R²: **0.9378**
- 24-hour persistence MAE: **1189.77 kW**
- 24-hour persistence RMSE: **2286.15 kW**
- 24-hour persistence R²: **0.8916**
- empirical forecast interval coverage: **84.74%**

The model uses a reproducible 30,000-row sample from the chronologically valid training panel so retraining remains practical on ordinary student hardware.

## Portable model format

The old pickle/joblib bundle has been removed. The runtime model is stored as:

`backend/forecasting/saved_model/expected_generation_model.json`

using **XGBoost native JSON serialization**. This avoids the pandas `StringDtype` and old-XGBoost pickle compatibility error encountered earlier.

Supporting saved_model are plain JSON/CSV files:

- `forecast_model_settings.json`
- `historical_generation.csv`
- `hourly_weather_patterns.csv`
- `forecast_accuracy_metrics.csv`
- `test_forecast_results.csv`

## Forecast uncertainty

The P50 point forecast is produced by XGBoost. Prediction intervals are generated from absolute validation residuals separately for 1–24h, 25–48h, and 49–72h horizon buckets. The UI reports uncertainty as half the P10–P90 width divided by plant reference capacity.

## Weather limitation

There is no live future-weather API in the supplied project. Future target weather features therefore use per-plant, per-hour historical climatology. In a real deployment this should be replaced with NWP/weather API forecasts.

## SHAP

SHAP TreeExplainer is connected to the deployed XGBoost model through:

`GET /forecast/explain/{plant_id}`

The AI Insights page can show the top model features and whether each feature increases or decreases the generation forecast.

## Run

Backend:

```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn server:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open FastAPI docs at `http://127.0.0.1:8000/docs`.

## Retrain Forecasting module

From `backend/`:

```bash
python -m forecasting.train_forecast_model
```

This regenerates the native XGBoost model and all evaluation/support saved_model.
