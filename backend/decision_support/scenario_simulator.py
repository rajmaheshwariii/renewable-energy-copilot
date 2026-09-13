from __future__ import annotations

from copy import deepcopy

from .decision_recommendations import recommend_action
from .cost_emissions_impact import calculate_impact


DECISION_FIELDS = {
    "predicted_generation_kw",
    "demand_kw",
    "battery_soc_pct",
    "battery_capacity_kwh",
    "max_charge_rate_kw",
    "max_discharge_rate_kw",
    "backup_available",
    "backup_capacity_kw",
    "grid_export_available",
    "grid_export_limit_kw",
    "risk_score",
    "forecast_uncertainty_pct",
    "electricity_price_inr_per_mwh",
    "backup_cost_inr_per_mwh",
    "battery_degradation_cost_inr_per_mwh",
    "battery_health_pct",
    "future_peak_price_inr_per_mwh",
    "future_peak_shortage_kw",
    "optimization_mode",
    "max_soc_pct",
    "interval_hours",
}


def run_pipeline(inputs: dict) -> dict:
    decision_inputs = {
        k: v for k, v in inputs.items()
        if k in DECISION_FIELDS
    }

    decision = recommend_action(**decision_inputs)

    impact = calculate_impact(
        decision_result=decision,
        electricity_price_inr_per_mwh=inputs[
            "electricity_price_inr_per_mwh"
        ],
        backup_cost_inr_per_mwh=inputs[
            "backup_cost_inr_per_mwh"
        ],
        backup_co2_kg_per_mwh=inputs[
            "backup_co2_kg_per_mwh"
        ],
        battery_degradation_cost_inr_per_mwh=inputs.get(
            "battery_degradation_cost_inr_per_mwh", 1200.0
        ),
        interval_hours=inputs.get("interval_hours", 1.0),
    )

    return {
        "scenario_inputs": deepcopy(inputs),
        "decision": decision,
        "impact": impact,
    }


def simulate_scenario(base_inputs: dict, changed_values: dict) -> dict:
    """
    Slider/toggle values from the frontend are passed in changed_values.

    Example:
        changed_values = {
            "demand_kw": 12000,
            "battery_soc_pct": 25,
            "backup_available": False
        }
    """
    new_inputs = deepcopy(base_inputs)

    for key, value in changed_values.items():
        if key not in new_inputs:
            raise KeyError(f"Unknown What-If field: {key}")
        new_inputs[key] = value

    return run_pipeline(new_inputs)


def compare_scenarios(base_result: dict, what_if_result: dict) -> dict:
    return {
        "base_condition": base_result["decision"]["condition"],
        "what_if_condition": what_if_result["decision"]["condition"],
        "base_actions": [
            x["action"]
            for x in base_result["decision"]["recommended_actions"]
        ],
        "what_if_actions": [
            x["action"]
            for x in what_if_result["decision"]["recommended_actions"]
        ],
        "base_confidence_pct":
            base_result["decision"]["confidence_pct"],
        "what_if_confidence_pct":
            what_if_result["decision"]["confidence_pct"],
        "base_net_cost_inr":
            base_result["impact"]["net_operational_cost_inr"],
        "what_if_net_cost_inr":
            what_if_result["impact"]["net_operational_cost_inr"],
        "base_co2_kg":
            base_result["impact"]["backup_co2_emissions_kg"],
        "what_if_co2_kg":
            what_if_result["impact"]["backup_co2_emissions_kg"],
        "cost_change_inr": round(
            what_if_result["impact"]["net_operational_cost_inr"]
            - base_result["impact"]["net_operational_cost_inr"],
            2,
        ),
        "co2_change_kg": round(
            what_if_result["impact"]["backup_co2_emissions_kg"]
            - base_result["impact"]["backup_co2_emissions_kg"],
            2,
        ),
    }


def simulate_multiple_scenarios(base_inputs: dict, scenarios: dict) -> list:
    """
    scenarios:
    {
        "High Demand": {"demand_kw": 15000},
        "Low SOC": {"battery_soc_pct": 20},
        "Backup Failure": {"backup_available": False}
    }
    """
    results = []

    for name, changes in scenarios.items():
        result = simulate_scenario(base_inputs, changes)
        results.append({
            "scenario_name": name,
            "changes": changes,
            "result": result,
        })

    return results
