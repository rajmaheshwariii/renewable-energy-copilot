from __future__ import annotations


def calculate_impact(
    decision_result: dict,
    electricity_price_inr_per_mwh: float,
    backup_cost_inr_per_mwh: float,
    backup_co2_kg_per_mwh: float,
    battery_degradation_cost_inr_per_mwh: float = 1200.0,
    export_revenue_inr_per_mwh: float | None = None,
    interval_hours: float = 1.0,
) -> dict:
    """
    Estimate operational cost, revenue, battery degradation cost and CO2 impact.

    All values are estimated values and should be labelled as simulated.
    """
    if export_revenue_inr_per_mwh is None:
        export_revenue_inr_per_mwh = 0.80 * float(
            electricity_price_inr_per_mwh
        )

    totals = {
        "battery_discharge_kwh": 0.0,
        "battery_charge_kwh": 0.0,
        "backup_energy_kwh": 0.0,
        "exported_energy_kwh": 0.0,
        "curtailed_energy_kwh": 0.0,
        "unserved_energy_kwh": 0.0,
    }

    for item in decision_result["recommended_actions"]:
        action = item["action"]
        energy_kwh = float(item.get("power_kw", 0.0)) * interval_hours

        if action == "DISCHARGE_BATTERY":
            totals["battery_discharge_kwh"] += energy_kwh
        elif action == "CHARGE_BATTERY":
            totals["battery_charge_kwh"] += energy_kwh
        elif action == "ACTIVATE_BACKUP":
            totals["backup_energy_kwh"] += energy_kwh
        elif action == "EXPORT_TO_GRID":
            totals["exported_energy_kwh"] += energy_kwh
        elif action == "CURTAIL_GENERATION":
            totals["curtailed_energy_kwh"] += energy_kwh
        elif action == "UNSERVED_DEMAND_ALERT":
            totals["unserved_energy_kwh"] += energy_kwh

    mwh = {k.replace("_kwh", "_mwh"): v / 1000.0 for k, v in totals.items()}

    battery_throughput_mwh = (
        mwh["battery_discharge_mwh"] + mwh["battery_charge_mwh"]
    )

    battery_degradation_cost = (
        battery_throughput_mwh * battery_degradation_cost_inr_per_mwh
    )

    backup_cost = (
        mwh["backup_energy_mwh"] * backup_cost_inr_per_mwh
    )

    export_revenue = (
        mwh["exported_energy_mwh"] * export_revenue_inr_per_mwh
    )

    backup_co2 = (
        mwh["backup_energy_mwh"] * backup_co2_kg_per_mwh
    )

    # Battery discharge is treated as avoiding equivalent backup generation.
    avoided_backup_cost = (
        mwh["battery_discharge_mwh"] * backup_cost_inr_per_mwh
    )
    avoided_backup_co2 = (
        mwh["battery_discharge_mwh"] * backup_co2_kg_per_mwh
    )

    net_operational_cost = (
        backup_cost + battery_degradation_cost - export_revenue
    )

    return {
        **{k: round(v, 4) for k, v in mwh.items()},
        "battery_degradation_cost_inr": round(battery_degradation_cost, 2),
        "backup_cost_inr": round(backup_cost, 2),
        "export_revenue_inr": round(export_revenue, 2),
        "estimated_avoided_backup_cost_inr": round(avoided_backup_cost, 2),
        "backup_co2_emissions_kg": round(backup_co2, 2),
        "estimated_co2_avoided_kg": round(avoided_backup_co2, 2),
        "net_operational_cost_inr": round(net_operational_cost, 2),
    }
