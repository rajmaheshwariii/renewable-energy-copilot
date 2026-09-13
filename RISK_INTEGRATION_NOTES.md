# Updated Risk assessment module Risk Integration

This build replaces the previous Risk assessment module `risk_config.py` and `risk_engine.py` with the updated dataset-aware versions.

## Supported forecast/generation columns
The updated engine can recognize `forecast_kw`, `p50_kw`, `p50`, `predicted_generation_kw`, or `generation_ac_kw` when risk is calculated from a DataFrame row.

## Uncertainty
It prefers `forecast_uncertainty_pct` or `uncertainty_pct`. If those are absent and `p10_kw`, `p90_kw`, and `plant_peak_reference_kw` are present, uncertainty is derived from the P10-P90 half-width as a percentage of plant capacity.

## Dataset-only defaults
The augmented generation dataset does not contain demand, battery SOC, backup status, or grid export status. For direct DataFrame testing only, the updated configuration provides explicit demo defaults. The integrated FastAPI endpoints continue to use the operational/user-provided values supplied by the application.

## Main files
- `backend/risk_and_explainability/risk_config.py` — updated configuration
- `backend/risk_and_explainability/risk_engine.py` — updated risk engine
- `backend/api.py` — API version updated to 5.1.0; existing risk endpoint integration is preserved

## Run
From the `backend` folder:

```bash
python -m uvicorn server:app --reload --port 8000
```

Then open `http://127.0.0.1:8000/docs`.
