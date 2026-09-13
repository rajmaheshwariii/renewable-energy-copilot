"""
Configuration for the Renewable Energy Risk Engine.

Updated for the augmented renewable dataset with columns:
plant_id, plant_label, timestamp_hour, generation_ac_kw,
generation_dc_kw, ambient_temperature_c, module_temperature_c,
irradiation, plant_peak_reference_kw, capacity_factor,
hour_sin, hour_cos.

The dataset itself does not contain demand, battery SOC, backup status,
grid-export status, or model uncertainty. For dataset-only testing,
clearly labelled demo defaults are used below. In the integrated app,
real/user-provided operational values should replace them.
"""

# ============================================================
# DATASET COLUMN NAMES
# ============================================================

PLANT_ID_COLUMN = "plant_id"
PLANT_LABEL_COLUMN = "plant_label"
TIMESTAMP_COLUMN = "timestamp_hour"
GENERATION_COLUMN = "generation_ac_kw"
CAPACITY_COLUMN = "plant_peak_reference_kw"

# Forecast output aliases supported by risk_calculator.py
FORECAST_COLUMN_CANDIDATES = [
    "forecast_kw",
    "p50_kw",
    "p50",
    "predicted_generation_kw",
    "generation_ac_kw",
]

UNCERTAINTY_COLUMN_CANDIDATES = [
    "forecast_uncertainty_pct",
    "uncertainty_pct",
]

# ============================================================
# DEMO OPERATIONAL DEFAULTS
# ============================================================
# These are only used when running risk assessment directly on the
# historical/augmented dataset, because that dataset does not
# contain operational demand/battery/backup/grid fields.

DEFAULT_DEMAND_KW = 0.0
DEFAULT_DEMAND_AS_CAPACITY_FRACTION = 0.60
DEFAULT_BATTERY_SOC_PCT = 50.0
DEFAULT_BACKUP_AVAILABLE = True
DEFAULT_BACKUP_CAPACITY_KW = 10000.0
DEFAULT_GRID_EXPORT_AVAILABLE = True
DEFAULT_GRID_EXPORT_LIMIT_KW = 10000.0
DEFAULT_UNCERTAINTY_PCT = 10.0

# ============================================================
# RISK COMPONENT WEIGHTS
# ============================================================

RISK_WEIGHTS = {
    "energy": 0.40,
    "battery": 0.20,
    "uncertainty": 0.15,
    "backup": 0.15,
    "grid": 0.10,
}

# ============================================================
# RISK SCORE LEVELS
# ============================================================

RISK_THRESHOLDS = {
    "low": 25,
    "moderate": 50,
    "high": 75,
}

# ============================================================
# SHORTAGE / SURPLUS THRESHOLDS
# ============================================================

SHORTAGE_THRESHOLD_PCT = 10.0
SURPLUS_THRESHOLD_PCT = 10.0

# ============================================================
# BATTERY THRESHOLDS
# ============================================================

BATTERY_THRESHOLDS = {
    "critical": 20.0,
    "low": 30.0,
    "healthy": 60.0,
    "high": 80.0,
}

# ============================================================
# FORECAST UNCERTAINTY
# ============================================================

UNCERTAINTY_THRESHOLDS = {
    "low": 5.0,
    "moderate": 10.0,
    "high": 20.0,
    "critical": 30.0,
}

MAX_UNCERTAINTY_FOR_100_RISK = 30.0

# ============================================================
# BACKUP / GRID RISK VALUES
# ============================================================

BACKUP_RISK = {
    "available_and_sufficient": 20.0,
    "available_but_insufficient": 80.0,
    "unavailable": 100.0,
}

GRID_RISK = {
    "normal": 20.0,
    "export_limit_exceeded": 80.0,
    "export_unavailable": 100.0,
}

# ============================================================
# SCORE LIMITS
# ============================================================

MIN_RISK_SCORE = 0.0
MAX_RISK_SCORE = 100.0


def validate_weights():
    total = sum(RISK_WEIGHTS.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Risk weights must sum to 1.0, but got {total}")
    return True


validate_weights()
