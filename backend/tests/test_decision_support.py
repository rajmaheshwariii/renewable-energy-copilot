from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decision_support.decision_recommendations import recommend_action, dynamic_reserve_soc


def common():
    return dict(
        battery_capacity_kwh=40000,
        max_charge_rate_kw=5000,
        max_discharge_rate_kw=5000,
        backup_capacity_kw=6000,
        grid_export_limit_kw=4000,
        risk_score=60,
        forecast_uncertainty_pct=10,
        electricity_price_inr_per_mwh=6000,
        backup_cost_inr_per_mwh=14000,
        battery_degradation_cost_inr_per_mwh=1200,
        battery_health_pct=95,
        optimization_mode="balanced",
    )


def test_shortage_uses_resources():
    x = common()
    result = recommend_action(
        predicted_generation_kw=5000,
        demand_kw=9000,
        battery_soc_pct=70,
        backup_available=True,
        grid_export_available=True,
        **x,
    )
    actions = [a["action"] for a in result["recommended_actions"]]
    assert "DISCHARGE_BATTERY" in actions
    assert result["remaining_shortage_kw"] == 0


def test_surplus_charge_or_export():
    x = common()
    result = recommend_action(
        predicted_generation_kw=12000,
        demand_kw=7000,
        battery_soc_pct=50,
        backup_available=True,
        grid_export_available=True,
        **x,
    )
    actions = [a["action"] for a in result["recommended_actions"]]
    assert "CHARGE_BATTERY" in actions


def test_reserve_increases_with_risk():
    low = dynamic_reserve_soc(10, 5, "balanced", 0)
    high = dynamic_reserve_soc(90, 20, "maximum_reliability", 5000)
    assert high > low


if __name__ == "__main__":
    test_shortage_uses_resources()
    test_surplus_charge_or_export()
    test_reserve_increases_with_risk()
    print("All tests passed.")
