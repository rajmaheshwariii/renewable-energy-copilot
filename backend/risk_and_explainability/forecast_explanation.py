"""SHAP bridge for the integrated Renewable Energy Copilot.

The project uses the saved forecasting model for runtime predictions,
so this module delegates to the forecasting service's runtime feature builder instead
of loading fragile pickle/joblib artifacts.
"""

try:
    from ..forecasting.forecast_service import explain_forecast_for_plant
except ImportError:
    from forecasting.forecast_service import explain_forecast_for_plant


def explain_plant_forecast(plant_id: int, horizon: int = 1, top_n: int = 8) -> dict:
    return explain_forecast_for_plant(plant_id=plant_id, horizon=horizon, top_n=top_n)


class RenewableSHAPExplainer:
    """Compatibility wrapper around the integrated forecast explanation."""

    def __init__(self, plant_id: int):
        self.plant_id = int(plant_id)

    def generate_explanation(self, horizon: int = 1, top_n: int = 8):
        return explain_plant_forecast(self.plant_id, horizon=horizon, top_n=top_n)

    def get_top_features(self, horizon: int = 1, top_n: int = 5):
        return self.generate_explanation(horizon=horizon, top_n=top_n)["top_features"]
