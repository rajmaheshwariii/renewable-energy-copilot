from __future__ import annotations

from copy import deepcopy

from .scenario_simulator import run_pipeline


MODES = [
    "lowest_cost",
    "lowest_co2",
    "maximum_reliability",
    "balanced",
]


def compare_optimization_modes(base_inputs: dict) -> dict:
    """
    Run the same operating state through all optimization modes.
    """
    results = []

    for mode in MODES:
        inputs = deepcopy(base_inputs)
        inputs["optimization_mode"] = mode
        result = run_pipeline(inputs)

        results.append({
            "mode": mode,
            "condition": result["decision"]["condition"],
            "actions": [
                a["action"]
                for a in result["decision"]["recommended_actions"]
            ],
            "confidence_pct":
                result["decision"]["confidence_pct"],
            "battery_reserve_pct":
                result["decision"].get("dynamic_reserve_soc_pct", 0.0),
            "remaining_shortage_kw":
                result["decision"]["remaining_shortage_kw"],
            "net_cost_inr":
                result["impact"]["net_operational_cost_inr"],
            "co2_kg":
                result["impact"]["backup_co2_emissions_kg"],
            "unserved_mwh":
                result["impact"]["unserved_energy_mwh"],
        })

    # Automatic recommendations for three common priorities.
    # Tie-break toward the policy that matches the requested objective.
    cost_priority = {"lowest_cost": 0, "balanced": 1, "lowest_co2": 2, "maximum_reliability": 3}
    co2_priority = {"lowest_co2": 0, "balanced": 1, "lowest_cost": 2, "maximum_reliability": 3}
    reliability_priority = {"maximum_reliability": 0, "balanced": 1, "lowest_co2": 2, "lowest_cost": 3}

    best_cost = min(
        results,
        key=lambda x: (x["unserved_mwh"], x["net_cost_inr"], cost_priority[x["mode"]])
    )

    best_co2 = min(
        results,
        key=lambda x: (x["unserved_mwh"], x["co2_kg"], co2_priority[x["mode"]])
    )

    best_reliability = min(
        results,
        key=lambda x: (
            x["unserved_mwh"],
            x["remaining_shortage_kw"],
            -x["confidence_pct"],
            reliability_priority[x["mode"]],
        )
    )

    return {
        "mode_results": results,
        "recommended_lowest_cost_mode": best_cost["mode"],
        "recommended_lowest_co2_mode": best_co2["mode"],
        "recommended_highest_reliability_mode":
            best_reliability["mode"],
    }
