# Forecasting — augmented dataset / portable model

Runtime forecasting no longer loads a pickle/joblib model bundle. The deployed XGBoost models are saved using XGBoost's native JSON format in `saved_model/`, which avoids pandas/XGBoost pickle compatibility errors across machines.

## Training data
`renewable_training_preprocessed.csv` contains 9,792 hourly rows: the two original plants plus ten synthetic augmented variants. Synthetic variants are used **only for training**. The UI/API exposes only the original `Plant_1` and `Plant_2`.

## Evaluation split
Evaluation uses target timestamps chronologically: 70% train, 15% validation, 15% held-out test. This prevents near-duplicate augmented rows from the same future timestamp being randomly split across train/test.

## Retrain
From `backend/`:

```bash
python -m forecasting.train_forecast_model
```

This creates native XGBoost JSON models, metadata, climatology, history, and held-out metrics under `forecasting/saved_model/`.
