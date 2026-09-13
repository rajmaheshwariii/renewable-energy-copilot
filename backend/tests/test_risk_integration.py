from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risk_and_explainability.risk_calculator import calculate_risk


def test_risk_assessment():
    result = calculate_risk(
        forecast_kw=8000,
        demand_kw=10000,
        battery_soc_pct=25,
        uncertainty_pct=10,
        backup_available=True,
        backup_capacity_kw=1000,
        grid_export_available=True,
        grid_export_limit_kw=3000,
    )
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_level"] in {"LOW", "MODERATE", "HIGH", "CRITICAL"}
    assert result["condition"] in {"NORMAL", "SHORTAGE", "SURPLUS", "HIGH_UNCERTAINTY"}


if __name__ == "__main__":
    test_risk_assessment()
    print("Risk assessment integration test passed.")
