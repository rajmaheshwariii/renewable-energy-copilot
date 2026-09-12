from __future__ import annotations

import pandas as pd

from decision_engine import recommend_action
from impact_calculator import calculate_impact
from what_if_simulator import (
    run_pipeline,
    simulate_scenario,
    compare_scenarios,
    simulate_multiple_scenarios,
)
from horizon_planner import plan_horizon
from mode_optimizer import compare_optimization_modes


OPERATIONAL_DATA = "member3_operational_dataset.csv"
ML_DATA = "ml_hourly_training_dataset.csv"


def build_base_inputs(row, predicted_generation_kw, risk_score=68.0):
    return {
        "predicted_generation_kw": float(predicted_generation_kw),
        "demand_kw": float(row["demand_kw"]),
        "battery_soc_pct": float(row["battery_soc_pct"]),
        "battery_capacity_kwh": float(row["battery_capacity_kwh"]),
        "max_charge_rate_kw": float(row["max_charge_rate_kw"]),
        "max_discharge_rate_kw": float(row["max_discharge_rate_kw"]),
        "backup_available": bool(row["backup_available"]),
        "backup_capacity_kw": float(row["backup_capacity_kw"]),
        "grid_export_available": bool(row["grid_export_available"]),
        "grid_export_limit_kw": float(row["grid_export_limit_kw"]),
        "risk_score": float(risk_score),
        "forecast_uncertainty_pct": 10.0,
        "electricity_price_inr_per_mwh":
            float(row["electricity_price_inr_per_mwh"]),
        "backup_cost_inr_per_mwh":
            float(row["backup_cost_inr_per_mwh"]),
        "backup_co2_kg_per_mwh":
            float(row["backup_co2_kg_per_mwh"]),
        "battery_degradation_cost_inr_per_mwh": 1200.0,
        "battery_health_pct": 95.0,
        "future_peak_price_inr_per_mwh": 12500.0,
        "future_peak_shortage_kw": 3500.0,
        "optimization_mode": "balanced",
        "interval_hours": 1.0,
    }


def main():
    ops = pd.read_csv(OPERATIONAL_DATA)
    ml = pd.read_csv(ML_DATA)

    # Merge by keys, never by row index.
    merged = ml.merge(
        ops,
        on=["plant_id", "plant_label", "timestamp_hour"],
        how="inner",
    )

    # ---------------------------------------------------------
    # 1. SINGLE-HOUR EXPLAINABLE DECISION
    # ---------------------------------------------------------
    row = merged.iloc[25]

    # Stand-in for Member 1 output until API integration.
    predicted_generation_kw = float(row["generation_ac_kw"]) * 0.90

    base_inputs = build_base_inputs(
        row,
        predicted_generation_kw,
        risk_score=68.0,
    )

    base = run_pipeline(base_inputs)

    print("\n=== EXPLAINABLE DECISION ===")
    print("Condition:", base["decision"]["condition"])
    print("Urgency:", base["decision"]["urgency"])
    print("Confidence:", base["decision"]["confidence_pct"], "%")
    print("Reserve SOC:", base["decision"]["dynamic_reserve_soc_pct"], "%")

    for action in base["decision"]["recommended_actions"]:
        print("-", action)

    print("\nWhy:")
    for reason in base["decision"]["explanation"]:
        print(" •", reason)

    # ---------------------------------------------------------
    # 2. WHAT-IF SLIDERS
    # ---------------------------------------------------------
    what_if = simulate_scenario(
        base_inputs,
        {
            "demand_kw": base_inputs["demand_kw"] * 1.35,
            "battery_soc_pct": 22.0,
            "backup_available": False,
        },
    )

    print("\n=== WHAT-IF COMPARISON ===")
    print(compare_scenarios(base, what_if))

    # ---------------------------------------------------------
    # 3. MULTIPLE SCENARIOS
    # ---------------------------------------------------------
    scenario_results = simulate_multiple_scenarios(
        base_inputs,
        {
            "Demand +30%": {
                "demand_kw": base_inputs["demand_kw"] * 1.30
            },
            "Battery SOC 20%": {
                "battery_soc_pct": 20.0
            },
            "Backup failure": {
                "backup_available": False
            },
        },
    )

    print("\n=== MULTIPLE SCENARIOS ===")
    for item in scenario_results:
        print(
            item["scenario_name"],
            "->",
            [
                a["action"]
                for a in item["result"]["decision"]["recommended_actions"]
            ]
        )

    # ---------------------------------------------------------
    # 4. OPTIMIZATION MODES
    # ---------------------------------------------------------
    mode_comparison = compare_optimization_modes(base_inputs)

    print("\n=== OPTIMIZATION MODES ===")
    for item in mode_comparison["mode_results"]:
        print(item)

    # ---------------------------------------------------------
    # 5. 24-HOUR MULTI-HOUR PLANNING
    # ---------------------------------------------------------
    horizon = merged[
        merged["plant_label"] == row["plant_label"]
    ].copy().iloc[20:44]

    # Stand-in forecast: actual generation with slight reduction.
    horizon["predicted_generation_kw"] = (
        horizon["generation_ac_kw"] * 0.92
    )
    horizon["risk_score"] = 55.0
    horizon["forecast_uncertainty_pct"] = 12.0

    plan, summary = plan_horizon(
        horizon,
        predicted_generation_col="predicted_generation_kw",
        optimization_mode="balanced",
        risk_score_col="risk_score",
        uncertainty_col="forecast_uncertainty_pct",
    )

    print("\n=== 24-HOUR PLAN ===")
    print(plan.head(10).to_string(index=False))
    print("\nPlan summary:")
    print(summary)

    plan.to_csv("sample_24h_dispatch_plan.csv", index=False)


if __name__ == "__main__":
    main()
