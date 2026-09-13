"""
Renewable Energy Risk Engine

This module converts renewable generation forecasts and
operational conditions into:

    1. Renewable Risk Score (0-100)
    2. Risk Level
    3. Operating Condition
    4. Risk Component Scores
    5. Human-readable Risk Reasons

Inputs:
    - Forecasted generation
    - Demand
    - Battery SOC
    - Forecast uncertainty
    - Backup availability/capacity
    - Grid export availability/limit

Output:
    A dictionary containing all risk information.
"""


from typing import Dict, List, Any, Optional

try:
    from .risk_config import (
        RISK_WEIGHTS,
        RISK_THRESHOLDS,
        SHORTAGE_THRESHOLD_PCT,
        SURPLUS_THRESHOLD_PCT,
        BATTERY_THRESHOLDS,
        MAX_UNCERTAINTY_FOR_100_RISK,
        BACKUP_RISK,
        GRID_RISK,
        DEFAULT_UNCERTAINTY_PCT,
        DEFAULT_DEMAND_KW,
        DEFAULT_DEMAND_AS_CAPACITY_FRACTION,
        DEFAULT_BATTERY_SOC_PCT,
        DEFAULT_BACKUP_AVAILABLE,
        DEFAULT_BACKUP_CAPACITY_KW,
        DEFAULT_GRID_EXPORT_AVAILABLE,
        DEFAULT_GRID_EXPORT_LIMIT_KW,
        FORECAST_COLUMN_CANDIDATES,
        UNCERTAINTY_COLUMN_CANDIDATES,
        CAPACITY_COLUMN,
        MIN_RISK_SCORE,
        MAX_RISK_SCORE,
    )
except ImportError:
    from .risk_settings import (
        RISK_WEIGHTS,
        RISK_THRESHOLDS,
        SHORTAGE_THRESHOLD_PCT,
        SURPLUS_THRESHOLD_PCT,
        BATTERY_THRESHOLDS,
        MAX_UNCERTAINTY_FOR_100_RISK,
        BACKUP_RISK,
        GRID_RISK,
        DEFAULT_UNCERTAINTY_PCT,
        DEFAULT_DEMAND_KW,
        DEFAULT_DEMAND_AS_CAPACITY_FRACTION,
        DEFAULT_BATTERY_SOC_PCT,
        DEFAULT_BACKUP_AVAILABLE,
        DEFAULT_BACKUP_CAPACITY_KW,
        DEFAULT_GRID_EXPORT_AVAILABLE,
        DEFAULT_GRID_EXPORT_LIMIT_KW,
        FORECAST_COLUMN_CANDIDATES,
        UNCERTAINTY_COLUMN_CANDIDATES,
        CAPACITY_COLUMN,
        MIN_RISK_SCORE,
        MAX_RISK_SCORE,
    )


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """
    Keep a value inside a specified range.
    """

    return max(minimum, min(value, maximum))


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float.

    Handles:
        None
        NaN
        strings
        invalid values
    """

    try:
        if value is None:
            return default

        result = float(value)

        if result != result:  # NaN check
            return default

        return result

    except (TypeError, ValueError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """
    Safely convert common values into boolean.
    """

    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, str):

        value_lower = value.strip().lower()

        if value_lower in {
            "true",
            "1",
            "yes",
            "available",
            "on",
        }:
            return True

        if value_lower in {
            "false",
            "0",
            "no",
            "unavailable",
            "off",
        }:
            return False

    return bool(value)


# ============================================================
# ENERGY ANALYSIS
# ============================================================

def calculate_energy_gap(
    forecast_kw: float,
    demand_kw: float,
) -> float:
    """
    Calculate generation-demand gap.

    Positive:
        surplus generation

    Negative:
        generation shortage
    """

    return forecast_kw - demand_kw


def calculate_shortage(
    forecast_kw: float,
    demand_kw: float,
) -> float:
    """
    Calculate shortage in kW.
    """

    return max(demand_kw - forecast_kw, 0.0)


def calculate_surplus(
    forecast_kw: float,
    demand_kw: float,
) -> float:
    """
    Calculate surplus in kW.
    """

    return max(forecast_kw - demand_kw, 0.0)


# ============================================================
# ENERGY RISK
# ============================================================

def calculate_energy_risk(
    forecast_kw: float,
    demand_kw: float,
) -> float:
    """
    Calculate energy shortage risk from 0-100.

    A shortage equal to or greater than demand produces
    a maximum energy risk of 100.
    """

    forecast_kw = max(safe_float(forecast_kw), 0.0)
    demand_kw = max(safe_float(demand_kw), 0.0)

    if demand_kw <= 0:
        return 0.0

    shortage = calculate_shortage(
        forecast_kw,
        demand_kw,
    )

    shortage_ratio = shortage / demand_kw

    risk = shortage_ratio * 100.0

    return round(clamp(risk), 2)


# ============================================================
# BATTERY RISK
# ============================================================

def calculate_battery_risk(
    battery_soc_pct: float,
    shortage_kw: float,
) -> float:
    """
    Calculate battery-related risk.

    Battery risk matters more when the system is facing
    an energy shortage.

    If there is no shortage, battery risk is kept low because
    a low SOC is not necessarily an immediate grid problem.
    """

    soc = clamp(
        safe_float(battery_soc_pct),
        0.0,
        100.0,
    )

    shortage_kw = max(
        safe_float(shortage_kw),
        0.0,
    )

    # No shortage means battery is not immediately required
    if shortage_kw <= 0:
        return 20.0

    # Low SOC -> high risk
    risk = 100.0 - soc

    return round(clamp(risk), 2)


# ============================================================
# UNCERTAINTY RISK
# ============================================================

def calculate_uncertainty_risk(
    uncertainty_pct: Optional[float],
) -> float:
    """
    Convert forecast uncertainty percentage into a 0-100
    uncertainty risk score.

    Example:
        5%  -> 16.67
        10% -> 33.33
        20% -> 66.67
        30% -> 100
    """

    if uncertainty_pct is None:
        uncertainty_pct = DEFAULT_UNCERTAINTY_PCT

    uncertainty_pct = max(
        safe_float(
            uncertainty_pct,
            DEFAULT_UNCERTAINTY_PCT,
        ),
        0.0,
    )

    risk = (
        uncertainty_pct
        / MAX_UNCERTAINTY_FOR_100_RISK
    ) * 100.0

    return round(clamp(risk), 2)


# ============================================================
# BACKUP RISK
# ============================================================

def calculate_backup_risk(
    backup_available: bool,
    backup_capacity_kw: float,
    shortage_kw: float,
) -> float:
    """
    Calculate backup generation risk.

    Cases:

        Backup unavailable
            -> 100

        Backup available but insufficient
            -> 80

        Backup available and sufficient
            -> 20

    If there is no shortage, backup availability is not
    an immediate concern, so risk is low.
    """

    backup_available = safe_bool(
        backup_available,
        default=False,
    )

    backup_capacity_kw = max(
        safe_float(backup_capacity_kw),
        0.0,
    )

    shortage_kw = max(
        safe_float(shortage_kw),
        0.0,
    )

    # No shortage -> backup isn't currently needed
    if shortage_kw <= 0:
        return 20.0

    if not backup_available:
        return BACKUP_RISK["unavailable"]

    if backup_capacity_kw < shortage_kw:
        return BACKUP_RISK["available_but_insufficient"]

    return BACKUP_RISK["available_and_sufficient"]


# ============================================================
# GRID CONSTRAINT RISK
# ============================================================

def calculate_grid_risk(
    surplus_kw: float,
    grid_export_available: bool,
    grid_export_limit_kw: float,
) -> float:
    """
    Calculate grid export constraint risk.

    If there is no surplus, grid export constraints are not
    immediately relevant.

    If surplus exists:

        Export unavailable
            -> 100

        Export limit exceeded
            -> 80

        Export available within limit
            -> 20
    """

    surplus_kw = max(
        safe_float(surplus_kw),
        0.0,
    )

    grid_export_available = safe_bool(
        grid_export_available,
        default=False,
    )

    grid_export_limit_kw = max(
        safe_float(grid_export_limit_kw),
        0.0,
    )

    # No surplus -> no immediate export problem
    if surplus_kw <= 0:
        return GRID_RISK["normal"]

    if not grid_export_available:
        return GRID_RISK["export_unavailable"]

    if surplus_kw > grid_export_limit_kw:
        return GRID_RISK["export_limit_exceeded"]

    return GRID_RISK["normal"]


# ============================================================
# CONDITION CLASSIFICATION
# ============================================================

def classify_condition(
    forecast_kw: float,
    demand_kw: float,
    uncertainty_pct: Optional[float],
) -> str:
    """
    Classify the operating condition.

    Possible values:

        NORMAL
        SHORTAGE
        SURPLUS
        HIGH_UNCERTAINTY
    """

    forecast_kw = max(
        safe_float(forecast_kw),
        0.0,
    )

    demand_kw = max(
        safe_float(demand_kw),
        0.0,
    )

    if uncertainty_pct is None:
        uncertainty_pct = DEFAULT_UNCERTAINTY_PCT

    uncertainty_pct = max(
        safe_float(uncertainty_pct),
        0.0,
    )

    # High uncertainty gets priority because the forecast
    # itself is unreliable.
    if uncertainty_pct >= 20.0:
        return "HIGH_UNCERTAINTY"

    if demand_kw <= 0:
        return "NORMAL"

    shortage_limit = demand_kw * (
        1.0 - SHORTAGE_THRESHOLD_PCT / 100.0
    )

    surplus_limit = demand_kw * (
        1.0 + SURPLUS_THRESHOLD_PCT / 100.0
    )

    if forecast_kw < shortage_limit:
        return "SHORTAGE"

    if forecast_kw > surplus_limit:
        return "SURPLUS"

    return "NORMAL"


# ============================================================
# RISK LEVEL
# ============================================================

def classify_risk_level(
    risk_score: float,
) -> str:
    """
    Convert numerical risk score to risk category.
    """

    score = clamp(
        safe_float(risk_score),
        MIN_RISK_SCORE,
        MAX_RISK_SCORE,
    )

    if score <= RISK_THRESHOLDS["low"]:
        return "LOW"

    if score <= RISK_THRESHOLDS["moderate"]:
        return "MODERATE"

    if score <= RISK_THRESHOLDS["high"]:
        return "HIGH"

    return "CRITICAL"


# ============================================================
# RISK REASONS
# ============================================================

def generate_risk_reasons(
    forecast_kw: float,
    demand_kw: float,
    battery_soc_pct: float,
    uncertainty_pct: float,
    backup_available: bool,
    backup_capacity_kw: float,
    grid_export_available: bool,
    grid_export_limit_kw: float,
) -> List[str]:
    """
    Generate human-readable reasons explaining why risk
    is high or why a particular condition exists.
    """

    reasons = []

    forecast_kw = max(
        safe_float(forecast_kw),
        0.0,
    )

    demand_kw = max(
        safe_float(demand_kw),
        0.0,
    )

    battery_soc_pct = clamp(
        safe_float(battery_soc_pct),
        0.0,
        100.0,
    )

    uncertainty_pct = max(
        safe_float(uncertainty_pct),
        0.0,
    )

    backup_available = safe_bool(
        backup_available,
        False,
    )

    backup_capacity_kw = max(
        safe_float(backup_capacity_kw),
        0.0,
    )

    grid_export_available = safe_bool(
        grid_export_available,
        False,
    )

    grid_export_limit_kw = max(
        safe_float(grid_export_limit_kw),
        0.0,
    )

    shortage = calculate_shortage(
        forecast_kw,
        demand_kw,
    )

    surplus = calculate_surplus(
        forecast_kw,
        demand_kw,
    )

    # --------------------------------------------------------
    # Shortage
    # --------------------------------------------------------

    if demand_kw > 0 and shortage > 0:

        shortage_pct = (
            shortage / demand_kw
        ) * 100.0

        if shortage_pct >= 30:

            reasons.append(
                f"Forecast generation is "
                f"{shortage_pct:.1f}% below demand"
            )

        elif shortage_pct >= 10:

            reasons.append(
                f"Forecast generation is "
                f"{shortage_pct:.1f}% below demand"
            )

    # --------------------------------------------------------
    # Surplus
    # --------------------------------------------------------

    if demand_kw > 0 and surplus > 0:

        surplus_pct = (
            surplus / demand_kw
        ) * 100.0

        if surplus_pct >= 10:

            reasons.append(
                f"Forecast generation is "
                f"{surplus_pct:.1f}% above demand"
            )

    # --------------------------------------------------------
    # Battery
    # --------------------------------------------------------

    if battery_soc_pct <= BATTERY_THRESHOLDS["critical"]:

        reasons.append(
            f"Battery SOC is critically low "
            f"({battery_soc_pct:.1f}%)"
        )

    elif battery_soc_pct <= BATTERY_THRESHOLDS["low"]:

        reasons.append(
            f"Battery SOC is low "
            f"({battery_soc_pct:.1f}%)"
        )

    elif surplus > 0 and battery_soc_pct >= BATTERY_THRESHOLDS["high"]:

        reasons.append(
            f"Battery is nearly full "
            f"({battery_soc_pct:.1f}%), limiting storage "
            f"of surplus energy"
        )

    # --------------------------------------------------------
    # Uncertainty
    # --------------------------------------------------------

    if uncertainty_pct >= 20:

        reasons.append(
            f"Forecast uncertainty is high "
            f"({uncertainty_pct:.1f}%)"
        )

    elif uncertainty_pct >= 10:

        reasons.append(
            f"Forecast uncertainty is moderate "
            f"({uncertainty_pct:.1f}%)"
        )

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    if shortage > 0:

        if not backup_available:

            reasons.append(
                "Backup generation is unavailable"
            )

        elif backup_capacity_kw < shortage:

            reasons.append(
                "Available backup capacity cannot "
                "fully cover the expected shortage"
            )

    # --------------------------------------------------------
    # Grid export
    # --------------------------------------------------------

    if surplus > 0:

        if not grid_export_available:

            reasons.append(
                "Grid export is unavailable, "
                "creating curtailment risk"
            )

        elif surplus > grid_export_limit_kw:

            reasons.append(
                "Expected surplus exceeds the "
                "grid export limit"
            )

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    if not reasons:

        reasons.append(
            "Generation and demand are within "
            "normal operating range"
        )

    return reasons


# ============================================================
# COMPLETE RISK CALCULATION
# ============================================================

def calculate_risk(
    forecast_kw: float,
    demand_kw: float,
    battery_soc_pct: float,
    uncertainty_pct: Optional[float] = None,
    backup_available: bool = True,
    backup_capacity_kw: float = 0.0,
    grid_export_available: bool = True,
    grid_export_limit_kw: float = 0.0,
) -> Dict[str, Any]:
    """
    Main Renewable Risk Engine.

    Returns a complete risk assessment.

    Parameters
    ----------
    forecast_kw:
        Predicted renewable generation.

    demand_kw:
        Expected electricity demand.

    battery_soc_pct:
        Battery state of charge from 0-100%.

    uncertainty_pct:
        Estimated forecast uncertainty percentage.

    backup_available:
        Whether backup generation is available.

    backup_capacity_kw:
        Maximum available backup generation.

    grid_export_available:
        Whether renewable surplus can be exported.

    grid_export_limit_kw:
        Maximum grid export capacity.

    Returns
    -------
    dict
        Complete risk assessment.
    """

    # --------------------------------------------------------
    # Clean inputs
    # --------------------------------------------------------

    forecast_kw = max(
        safe_float(forecast_kw),
        0.0,
    )

    demand_kw = max(
        safe_float(demand_kw),
        0.0,
    )

    battery_soc_pct = clamp(
        safe_float(battery_soc_pct),
        0.0,
        100.0,
    )

    if uncertainty_pct is None:
        uncertainty_pct = DEFAULT_UNCERTAINTY_PCT

    uncertainty_pct = max(
        safe_float(uncertainty_pct),
        0.0,
    )

    backup_available = safe_bool(
        backup_available,
        True,
    )

    backup_capacity_kw = max(
        safe_float(backup_capacity_kw),
        0.0,
    )

    grid_export_available = safe_bool(
        grid_export_available,
        True,
    )

    grid_export_limit_kw = max(
        safe_float(grid_export_limit_kw),
        0.0,
    )

    # --------------------------------------------------------
    # Energy calculations
    # --------------------------------------------------------

    energy_gap_kw = calculate_energy_gap(
        forecast_kw,
        demand_kw,
    )

    shortage_kw = calculate_shortage(
        forecast_kw,
        demand_kw,
    )

    surplus_kw = calculate_surplus(
        forecast_kw,
        demand_kw,
    )

    # --------------------------------------------------------
    # Individual risk components
    # --------------------------------------------------------

    energy_risk = calculate_energy_risk(
        forecast_kw,
        demand_kw,
    )

    battery_risk = calculate_battery_risk(
        battery_soc_pct,
        shortage_kw,
    )

    uncertainty_risk = calculate_uncertainty_risk(
        uncertainty_pct,
    )

    backup_risk = calculate_backup_risk(
        backup_available,
        backup_capacity_kw,
        shortage_kw,
    )

    grid_risk = calculate_grid_risk(
        surplus_kw,
        grid_export_available,
        grid_export_limit_kw,
    )

    # --------------------------------------------------------
    # Weighted total
    # --------------------------------------------------------

    risk_score = (
        RISK_WEIGHTS["energy"] * energy_risk
        +
        RISK_WEIGHTS["battery"] * battery_risk
        +
        RISK_WEIGHTS["uncertainty"] * uncertainty_risk
        +
        RISK_WEIGHTS["backup"] * backup_risk
        +
        RISK_WEIGHTS["grid"] * grid_risk
    )

    risk_score = round(
        clamp(
            risk_score,
            MIN_RISK_SCORE,
            MAX_RISK_SCORE,
        ),
        2,
    )

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    risk_level = classify_risk_level(
        risk_score
    )

    condition = classify_condition(
        forecast_kw,
        demand_kw,
        uncertainty_pct,
    )

    # --------------------------------------------------------
    # Human-readable reasons
    # --------------------------------------------------------

    reasons = generate_risk_reasons(
        forecast_kw=forecast_kw,
        demand_kw=demand_kw,
        battery_soc_pct=battery_soc_pct,
        uncertainty_pct=uncertainty_pct,
        backup_available=backup_available,
        backup_capacity_kw=backup_capacity_kw,
        grid_export_available=grid_export_available,
        grid_export_limit_kw=grid_export_limit_kw,
    )

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {
        "forecast_kw": round(forecast_kw, 2),
        "demand_kw": round(demand_kw, 2),

        "energy_gap_kw": round(
            energy_gap_kw,
            2,
        ),

        "shortage_kw": round(
            shortage_kw,
            2,
        ),

        "surplus_kw": round(
            surplus_kw,
            2,
        ),

        "battery_soc_pct": round(
            battery_soc_pct,
            2,
        ),

        "uncertainty_pct": round(
            uncertainty_pct,
            2,
        ),

        "condition": condition,

        "risk_score": risk_score,

        "risk_level": risk_level,

        "risk_components": {
            "energy_risk": energy_risk,
            "battery_risk": battery_risk,
            "uncertainty_risk": uncertainty_risk,
            "backup_risk": backup_risk,
            "grid_risk": grid_risk,
        },

        "risk_weights": RISK_WEIGHTS.copy(),

        "risk_reasons": reasons,
    }


# ============================================================
# DATAFRAME SUPPORT
# ============================================================

def _first_present(row, candidates, default=None):
    """Return the first non-null value found in a pandas row."""
    for name in candidates:
        if name in row.index:
            value = row.get(name)
            if value is not None:
                try:
                    if value == value:  # not NaN
                        return value
                except Exception:
                    return value
    return default


def _derive_uncertainty_pct(row):
    """
    Prefer an uncertainty percentage supplied by the forecasting service.
    If it is missing but P10/P90 exist, derive uncertainty as
    half-width of the interval divided by plant capacity.
    """
    direct = _first_present(
        row,
        UNCERTAINTY_COLUMN_CANDIDATES,
        None,
    )
    if direct is not None:
        return max(safe_float(direct, DEFAULT_UNCERTAINTY_PCT), 0.0)

    p10 = _first_present(row, ["p10_kw", "p10"], None)
    p90 = _first_present(row, ["p90_kw", "p90"], None)
    capacity = row.get(CAPACITY_COLUMN, None)

    if p10 is not None and p90 is not None and capacity is not None:
        p10 = safe_float(p10)
        p90 = safe_float(p90)
        capacity = safe_float(capacity)
        if capacity > 0:
            half_width = max(p90 - p10, 0.0) / 2.0
            return round((half_width / capacity) * 100.0, 2)

    return DEFAULT_UNCERTAINTY_PCT


def _derive_demand_kw(row):
    """
    Use explicit demand when supplied.
    For direct testing on the augmented historical dataset only,
    derive a clearly-labelled demo demand from plant capacity.
    """
    if "demand_kw" in row.index:
        value = row.get("demand_kw")
        if value is not None:
            try:
                if value == value:
                    return max(safe_float(value), 0.0)
            except Exception:
                pass

    capacity = safe_float(row.get(CAPACITY_COLUMN, 0.0))
    if capacity > 0:
        return capacity * DEFAULT_DEMAND_AS_CAPACITY_FRACTION

    return DEFAULT_DEMAND_KW


def calculate_risk_from_row(row) -> Dict[str, Any]:
    """
    Calculate risk from either:
      1) forecast output (preferred), or
      2) the augmented historical dataset for demo/testing.

    Supported generation columns:
      forecast_kw, p50_kw, p50, predicted_generation_kw,
      generation_ac_kw

    The augmented dataset does not contain demand, battery SOC,
    uncertainty, backup or grid-export fields. Missing operational
    values therefore use the demo defaults in risk_settings.py.
    """

    forecast_kw = _first_present(
        row,
        FORECAST_COLUMN_CANDIDATES,
        0.0,
    )

    demand_kw = _derive_demand_kw(row)
    uncertainty_pct = _derive_uncertainty_pct(row)

    battery_soc_pct = row.get(
        "battery_soc_pct",
        DEFAULT_BATTERY_SOC_PCT,
    )

    backup_available = row.get(
        "backup_available",
        DEFAULT_BACKUP_AVAILABLE,
    )

    backup_capacity_kw = row.get(
        "backup_capacity_kw",
        DEFAULT_BACKUP_CAPACITY_KW,
    )

    grid_export_available = row.get(
        "grid_export_available",
        DEFAULT_GRID_EXPORT_AVAILABLE,
    )

    grid_export_limit_kw = row.get(
        "grid_export_limit_kw",
        DEFAULT_GRID_EXPORT_LIMIT_KW,
    )

    return calculate_risk(
        forecast_kw=forecast_kw,
        demand_kw=demand_kw,
        battery_soc_pct=battery_soc_pct,
        uncertainty_pct=uncertainty_pct,
        backup_available=backup_available,
        backup_capacity_kw=backup_capacity_kw,
        grid_export_available=grid_export_available,
        grid_export_limit_kw=grid_export_limit_kw,
    )


# ============================================================
# BATCH PROCESSING
# ============================================================

def add_risk_columns_to_dataframe(df):
    """
    Add risk information to every row of a pandas DataFrame.

    Expected columns:

        forecast_kw OR generation_ac_kw
        demand_kw
        battery_soc_pct
        uncertainty_pct (optional)
        backup_available
        backup_capacity_kw
        grid_export_available
        grid_export_limit_kw

    Returns:
        DataFrame with additional risk columns.
    """

    import pandas as pd

    results = []

    for _, row in df.iterrows():

        result = calculate_risk_from_row(
            row
        )

        results.append(result)

    risk_df = pd.DataFrame(
        results,
        index=df.index,
    )

    # Select useful output columns
    output_columns = [
        "energy_gap_kw",
        "shortage_kw",
        "surplus_kw",
        "condition",
        "risk_score",
        "risk_level",
        "risk_components",
        "risk_reasons",
    ]

    for column in output_columns:

        if column in risk_df.columns:

            df[column] = risk_df[column]

    return df