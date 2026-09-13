from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


VALID_MODES = {"balanced", "lowest_cost", "lowest_co2", "maximum_reliability"}


def dynamic_reserve_soc(
    risk_score: float = 50.0,
    forecast_uncertainty_pct: float = 10.0,
    optimization_mode: str = "balanced",
    future_peak_shortage_kw: float = 0.0,
) -> float:
    """
    Compute a dynamic minimum battery reserve.

    Higher risk, uncertainty, reliability mode, or an expected future peak
    causes the engine to preserve more battery energy.
    """
    if optimization_mode not in VALID_MODES:
        raise ValueError(f"Unknown optimization mode: {optimization_mode}")

    # Start with a small reserve, then let the selected priority shape it.
    reserve = 5.0

    # Risk and uncertainty still matter, but objective-specific policy has a
    # stronger effect so the comparison modes can make distinct decisions.
    reserve += min(max(risk_score, 0.0), 100.0) * 0.08
    reserve += min(max(forecast_uncertainty_pct, 0.0), 50.0) * 0.10

    mode_floor = {
        "lowest_cost": 5.0,
        "lowest_co2": 5.0,
        "balanced": 12.0,
        "maximum_reliability": 25.0,
    }[optimization_mode]

    if optimization_mode == "maximum_reliability":
        reserve += 20.0
    elif optimization_mode == "balanced":
        reserve += 4.0
    elif optimization_mode in {"lowest_co2", "lowest_cost"}:
        reserve -= 5.0

    if future_peak_shortage_kw > 0:
        reserve += 5.0

    return round(min(max(reserve, mode_floor), 60.0), 2)


def action_confidence(
    risk_score: float,
    forecast_uncertainty_pct: float,
    remaining_unserved_kw: float,
    energy_gap_kw: float,
) -> tuple[float, str]:
    """
    Transparent confidence heuristic for the recommendation.
    """
    confidence = 90.0

    confidence -= min(max(forecast_uncertainty_pct, 0.0), 50.0) * 0.8

    if remaining_unserved_kw > 0:
        confidence -= 20.0

    if abs(energy_gap_kw) < 250:
        confidence -= 8.0

    # Extreme risk makes action urgency clearer even if forecast is uncertain.
    if risk_score >= 80:
        confidence += 4.0

    confidence = min(max(confidence, 35.0), 98.0)

    if risk_score >= 75:
        urgency = "CRITICAL"
    elif risk_score >= 50:
        urgency = "HIGH"
    elif risk_score >= 25:
        urgency = "MODERATE"
    else:
        urgency = "LOW"

    return round(confidence, 1), urgency


@dataclass
class DecisionResult:
    condition: str
    optimization_mode: str
    energy_gap_kw: float
    dynamic_reserve_soc_pct: float
    recommended_actions: list
    remaining_shortage_kw: float
    remaining_surplus_kw: float
    confidence_pct: float
    urgency: str
    explanation: list
    message: str


def recommend_action(
    predicted_generation_kw: float,
    demand_kw: float,
    battery_soc_pct: float,
    battery_capacity_kwh: float,
    max_charge_rate_kw: float,
    max_discharge_rate_kw: float,
    backup_available: bool,
    backup_capacity_kw: float,
    grid_export_available: bool,
    grid_export_limit_kw: float,
    risk_score: float = 50.0,
    forecast_uncertainty_pct: float = 10.0,
    electricity_price_inr_per_mwh: float = 6000.0,
    backup_cost_inr_per_mwh: float = 14000.0,
    battery_degradation_cost_inr_per_mwh: float = 1200.0,
    battery_health_pct: float = 95.0,
    future_peak_price_inr_per_mwh: Optional[float] = None,
    future_peak_shortage_kw: float = 0.0,
    optimization_mode: str = "balanced",
    max_soc_pct: float = 90.0,
    interval_hours: float = 1.0,
) -> dict:
    """
    Explainable, constrained renewable-energy decision engine.

    Modes:
      - balanced
      - lowest_cost
      - lowest_co2
      - maximum_reliability

    Positive energy gap => surplus.
    Negative energy gap => shortage.
    """

    if optimization_mode not in VALID_MODES:
        raise ValueError(
            f"optimization_mode must be one of {sorted(VALID_MODES)}"
        )

    predicted_generation_kw = max(float(predicted_generation_kw), 0.0)
    demand_kw = max(float(demand_kw), 0.0)
    battery_soc_pct = min(max(float(battery_soc_pct), 0.0), 100.0)
    battery_capacity_kwh = max(float(battery_capacity_kwh), 0.0)
    max_charge_rate_kw = max(float(max_charge_rate_kw), 0.0)
    max_discharge_rate_kw = max(float(max_discharge_rate_kw), 0.0)
    backup_capacity_kw = max(float(backup_capacity_kw), 0.0)
    grid_export_limit_kw = max(float(grid_export_limit_kw), 0.0)
    battery_health_pct = min(max(float(battery_health_pct), 0.0), 100.0)
    interval_hours = max(float(interval_hours), 1e-9)

    energy_gap_kw = predicted_generation_kw - demand_kw
    reserve_soc = dynamic_reserve_soc(
        risk_score=risk_score,
        forecast_uncertainty_pct=forecast_uncertainty_pct,
        optimization_mode=optimization_mode,
        future_peak_shortage_kw=future_peak_shortage_kw,
    )

    actions = []
    explanation = [
        f"Predicted generation is {predicted_generation_kw:.1f} kW and demand is {demand_kw:.1f} kW.",
        f"Dynamic battery reserve is {reserve_soc:.1f}% because risk={risk_score:.0f}/100 and forecast uncertainty={forecast_uncertainty_pct:.1f}%.",
    ]
    remaining_shortage = 0.0
    remaining_surplus = 0.0

    # Battery-health derating: a degraded battery is used more conservatively.
    health_factor = max(battery_health_pct / 100.0, 0.50)
    effective_discharge_rate = max_discharge_rate_kw * health_factor
    effective_charge_rate = max_charge_rate_kw * health_factor

    # ---------------------------------------------------------
    # SHORTAGE
    # ---------------------------------------------------------
    if energy_gap_kw < 0:
        condition = "SHORTAGE"
        shortage_kw = abs(energy_gap_kw)

        usable_fraction = max((battery_soc_pct - reserve_soc) / 100.0, 0.0)
        usable_energy_kwh = battery_capacity_kwh * usable_fraction * health_factor
        energy_limited_discharge_kw = usable_energy_kwh / interval_hours

        potential_battery_kw = min(
            shortage_kw,
            effective_discharge_rate,
            energy_limited_discharge_kw,
        )

        # Decide whether battery or backup should be preferred first.
        battery_preferred = True

        if optimization_mode == "maximum_reliability":
            # Preserve battery reserve more strongly; still use battery above reserve.
            battery_preferred = risk_score >= 45 or not backup_available

        elif optimization_mode == "lowest_cost":
            # Compare degradation cost with backup cost.
            battery_preferred = (
                battery_degradation_cost_inr_per_mwh < backup_cost_inr_per_mwh
            )

            # If the future price is much higher and current risk is low,
            # preserve some battery for the expensive future period.
            if (
                future_peak_price_inr_per_mwh is not None
                and future_peak_price_inr_per_mwh
                > electricity_price_inr_per_mwh * 1.35
                and risk_score < 50
                and backup_available
            ):
                potential_battery_kw *= 0.40
                explanation.append(
                    "Battery discharge is reduced because a more expensive future peak is expected."
                )

        elif optimization_mode == "lowest_co2":
            # Prefer battery before fossil backup.
            battery_preferred = True

        # Helper for applying battery discharge
        def use_battery(amount_kw: float):
            nonlocal shortage_kw
            amount_kw = min(max(amount_kw, 0.0), shortage_kw)
            if amount_kw > 0:
                actions.append({
                    "action": "DISCHARGE_BATTERY",
                    "power_kw": round(amount_kw, 3),
                    "reason": (
                        "Stored renewable energy is available above the dynamic reserve."
                    ),
                })
                shortage_kw -= amount_kw
                explanation.append(
                    f"Battery supplies {amount_kw:.1f} kW while keeping SOC reserve protection."
                )

        # Helper for backup
        def use_backup():
            nonlocal shortage_kw
            if shortage_kw > 0 and backup_available:
                backup_kw = min(shortage_kw, backup_capacity_kw)
                if backup_kw > 0:
                    actions.append({
                        "action": "ACTIVATE_BACKUP",
                        "power_kw": round(backup_kw, 3),
                        "reason": "Remaining shortage cannot be covered by renewable generation alone.",
                    })
                    shortage_kw -= backup_kw
                    explanation.append(
                        f"Backup supplies {backup_kw:.1f} kW of the remaining deficit."
                    )

        if battery_preferred:
            use_battery(potential_battery_kw)
            use_backup()
        else:
            use_backup()
            # Battery can still cover anything backup could not.
            use_battery(min(potential_battery_kw, shortage_kw))

        remaining_shortage = max(shortage_kw, 0.0)

        if remaining_shortage > 0:
            actions.append({
                "action": "UNSERVED_DEMAND_ALERT",
                "power_kw": round(remaining_shortage, 3),
                "reason": "Available battery and backup capacity are insufficient.",
            })
            explanation.append(
                f"{remaining_shortage:.1f} kW remains unserved; operator intervention is required."
            )

        if not actions:
            actions.append({
                "action": "MONITOR_SHORTAGE",
                "power_kw": 0.0,
                "reason": "Shortage exists but no dispatch resource is currently usable.",
            })

        message = (
            "Shortage detected. Dispatch is selected using battery reserve, "
            f"cost/CO2/reliability policy, and backup constraints ({optimization_mode})."
        )

    # ---------------------------------------------------------
    # SURPLUS
    # ---------------------------------------------------------
    elif energy_gap_kw > 0:
        condition = "SURPLUS"
        surplus_kw = energy_gap_kw

        available_fraction = max((max_soc_pct - battery_soc_pct) / 100.0, 0.0)
        available_storage_kwh = battery_capacity_kwh * available_fraction
        storage_limited_charge_kw = available_storage_kwh / interval_hours

        potential_charge_kw = min(
            surplus_kw,
            effective_charge_rate,
            storage_limited_charge_kw,
        )

        # Price-aware order:
        # if export value is attractive NOW and no high future price is expected,
        # lowest-cost mode can export before charging.
        export_first = False
        if optimization_mode == "lowest_cost" and grid_export_available:
            if future_peak_price_inr_per_mwh is None:
                future_peak_price_inr_per_mwh = electricity_price_inr_per_mwh
            export_first = (
                electricity_price_inr_per_mwh
                >= future_peak_price_inr_per_mwh * 0.95
                and battery_soc_pct >= 55
            )

        def charge_battery(amount_kw: float):
            nonlocal surplus_kw
            amount_kw = min(max(amount_kw, 0.0), surplus_kw)
            if amount_kw > 0:
                actions.append({
                    "action": "CHARGE_BATTERY",
                    "power_kw": round(amount_kw, 3),
                    "reason": "Store renewable surplus for a later shortage or higher-value period.",
                })
                surplus_kw -= amount_kw
                explanation.append(
                    f"Battery absorbs {amount_kw:.1f} kW of renewable surplus."
                )

        def export_grid():
            nonlocal surplus_kw
            if surplus_kw > 0 and grid_export_available:
                export_kw = min(surplus_kw, grid_export_limit_kw)
                if export_kw > 0:
                    actions.append({
                        "action": "EXPORT_TO_GRID",
                        "power_kw": round(export_kw, 3),
                        "reason": "Export renewable surplus that is not being stored.",
                    })
                    surplus_kw -= export_kw
                    explanation.append(
                        f"{export_kw:.1f} kW is exported to the grid."
                    )

        if export_first:
            export_grid()
            charge_battery(min(potential_charge_kw, surplus_kw))
            explanation.append(
                "Price-aware mode favored immediate export before additional battery charging."
            )
        else:
            charge_battery(potential_charge_kw)
            export_grid()

        remaining_surplus = max(surplus_kw, 0.0)

        if remaining_surplus > 0:
            actions.append({
                "action": "CURTAIL_GENERATION",
                "power_kw": round(remaining_surplus, 3),
                "reason": "Battery and grid export limits cannot absorb all surplus generation.",
            })
            explanation.append(
                f"{remaining_surplus:.1f} kW must be curtailed as a last resort."
            )

        message = (
            "Surplus detected. The engine chooses between charging, exporting, "
            f"and curtailment using the {optimization_mode} policy."
        )

    # ---------------------------------------------------------
    # BALANCED
    # ---------------------------------------------------------
    else:
        condition = "BALANCED"
        actions.append({
            "action": "NO_ACTION",
            "power_kw": 0.0,
            "reason": "Predicted renewable generation matches demand.",
        })
        explanation.append("No dispatch action is required.")
        message = "Generation and demand are balanced."

    confidence, urgency = action_confidence(
        risk_score=risk_score,
        forecast_uncertainty_pct=forecast_uncertainty_pct,
        remaining_unserved_kw=remaining_shortage,
        energy_gap_kw=energy_gap_kw,
    )

    return asdict(
        DecisionResult(
            condition=condition,
            optimization_mode=optimization_mode,
            energy_gap_kw=round(energy_gap_kw, 3),
            dynamic_reserve_soc_pct=reserve_soc,
            recommended_actions=actions,
            remaining_shortage_kw=round(remaining_shortage, 3),
            remaining_surplus_kw=round(remaining_surplus, 3),
            confidence_pct=confidence,
            urgency=urgency,
            explanation=explanation,
            message=message,
        )
    )
