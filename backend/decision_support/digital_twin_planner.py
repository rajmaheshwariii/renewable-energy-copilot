from __future__ import annotations

import pandas as pd

from .decision_recommendations import recommend_action
from .cost_emissions_impact import calculate_impact


def detect_peak_period(
    horizon_df: pd.DataFrame,
    demand_col: str = "demand_kw",
    timestamp_col: str = "timestamp_hour",
) -> dict:
    idx = horizon_df[demand_col].astype(float).idxmax()
    row = horizon_df.loc[idx]
    return {
        "timestamp": row[timestamp_col],
        "peak_demand_kw": float(row[demand_col]),
    }


def plan_horizon(
    horizon_df: pd.DataFrame,
    predicted_generation_col: str = "predicted_generation_kw",
    optimization_mode: str = "balanced",
    risk_score_col: str | None = None,
    uncertainty_col: str | None = None,
    battery_health_pct: float = 95.0,
    battery_degradation_cost_inr_per_mwh: float = 1200.0,
    min_planning_hours: int = 1,
) -> tuple[pd.DataFrame, dict]:
    """
    Multi-hour planner.

    The SOC is updated sequentially so one hourly decision affects later hours.
    Future peak demand/price is passed to the single-hour decision engine,
    enabling battery reservation for expected high-value/high-risk periods.
    """
    if len(horizon_df) < min_planning_hours:
        raise ValueError("Horizon does not contain enough rows.")

    df = horizon_df.copy().reset_index(drop=True)
    df["timestamp_hour"] = pd.to_datetime(df["timestamp_hour"])
    df = df.sort_values("timestamp_hour").reset_index(drop=True)

    current_soc = float(df.loc[0, "battery_soc_pct"])
    rows = []

    total_cost = 0.0
    total_co2 = 0.0
    total_unserved_mwh = 0.0

    for i, row in df.iterrows():
        future = df.iloc[i + 1:]

        future_peak_price = None
        future_peak_shortage = 0.0

        if len(future):
            future_peak_price = float(
                future["electricity_price_inr_per_mwh"].max()
            )

            future_shortages = (
                future["demand_kw"].astype(float)
                - future[predicted_generation_col].astype(float)
            ).clip(lower=0)

            if len(future_shortages):
                future_peak_shortage = float(future_shortages.max())

        risk_score = (
            float(row[risk_score_col])
            if risk_score_col and risk_score_col in row
            else 50.0
        )

        uncertainty = (
            float(row[uncertainty_col])
            if uncertainty_col and uncertainty_col in row
            else 10.0
        )

        decision = recommend_action(
            predicted_generation_kw=float(row[predicted_generation_col]),
            demand_kw=float(row["demand_kw"]),
            battery_soc_pct=current_soc,
            battery_capacity_kwh=float(row["battery_capacity_kwh"]),
            max_charge_rate_kw=float(row["max_charge_rate_kw"]),
            max_discharge_rate_kw=float(row["max_discharge_rate_kw"]),
            backup_available=bool(row["backup_available"]),
            backup_capacity_kw=float(row["backup_capacity_kw"]),
            grid_export_available=bool(row["grid_export_available"]),
            grid_export_limit_kw=float(row["grid_export_limit_kw"]),
            risk_score=risk_score,
            forecast_uncertainty_pct=uncertainty,
            electricity_price_inr_per_mwh=float(
                row["electricity_price_inr_per_mwh"]
            ),
            backup_cost_inr_per_mwh=float(
                row["backup_cost_inr_per_mwh"]
            ),
            battery_degradation_cost_inr_per_mwh=
                battery_degradation_cost_inr_per_mwh,
            battery_health_pct=battery_health_pct,
            future_peak_price_inr_per_mwh=future_peak_price,
            future_peak_shortage_kw=future_peak_shortage,
            optimization_mode=optimization_mode,
            interval_hours=1.0,
        )

        impact = calculate_impact(
            decision_result=decision,
            electricity_price_inr_per_mwh=float(
                row["electricity_price_inr_per_mwh"]
            ),
            backup_cost_inr_per_mwh=float(
                row["backup_cost_inr_per_mwh"]
            ),
            backup_co2_kg_per_mwh=float(
                row["backup_co2_kg_per_mwh"]
            ),
            battery_degradation_cost_inr_per_mwh=
                battery_degradation_cost_inr_per_mwh,
        )

        # Update SOC sequentially.
        capacity = float(row["battery_capacity_kwh"])
        stored_kwh = current_soc / 100.0 * capacity

        for action in decision["recommended_actions"]:
            p = float(action.get("power_kw", 0.0))
            if action["action"] == "CHARGE_BATTERY":
                stored_kwh += p * 0.95
            elif action["action"] == "DISCHARGE_BATTERY":
                stored_kwh -= p / 0.95

        current_soc = max(min(100.0 * stored_kwh / capacity, 95.0), 0.0)

        total_cost += impact["net_operational_cost_inr"]
        total_co2 += impact["backup_co2_emissions_kg"]
        total_unserved_mwh += impact["unserved_energy_mwh"]

        rows.append({
            "timestamp_hour": row["timestamp_hour"],
            "predicted_generation_kw":
                float(row[predicted_generation_col]),
            "demand_kw": float(row["demand_kw"]),
            "soc_after_action_pct": round(current_soc, 2),
            "reserve_soc_pct":
                decision["dynamic_reserve_soc_pct"],
            "condition": decision["condition"],
            "actions": " + ".join(
                a["action"]
                for a in decision["recommended_actions"]
            ),
            "confidence_pct": decision["confidence_pct"],
            "urgency": decision["urgency"],
            "net_cost_inr": impact["net_operational_cost_inr"],
            "backup_co2_kg":
                impact["backup_co2_emissions_kg"],
            "unserved_energy_mwh":
                impact["unserved_energy_mwh"],
        })

    plan_df = pd.DataFrame(rows)

    summary = {
        "optimization_mode": optimization_mode,
        "hours_planned": len(plan_df),
        "peak_demand": detect_peak_period(df),
        "total_net_operational_cost_inr": round(total_cost, 2),
        "total_backup_co2_kg": round(total_co2, 2),
        "total_unserved_energy_mwh": round(total_unserved_mwh, 4),
        "ending_battery_soc_pct": round(current_soc, 2),
    }

    return plan_df, summary
