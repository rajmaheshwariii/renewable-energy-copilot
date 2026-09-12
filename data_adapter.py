
"""
data_adapter.py

Purpose
-------
Convert a future Member 1 dataset with different column names into the
standard schema expected by the Renewable Energy Copilot pipeline.

This lets you change datasets later without rewriting Member 2/3 code.

Standard output schema
----------------------
Required:
    plant_id
    plant_label
    timestamp_hour
    generation_ac_kw

Optional but recommended:
    generation_dc_kw
    ambient_temperature_c
    module_temperature_c
    irradiation
    plant_peak_reference_kw
    capacity_factor
    hour_sin
    hour_cos

Typical usage
-------------
1. Create a column mapping for the new dataset.
2. Call adapt_dataset(...)
3. Use the returned standardized DataFrame with the rest of the project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


STANDARD_COLUMNS = [
    "plant_id",
    "plant_label",
    "timestamp_hour",
    "generation_ac_kw",
    "generation_dc_kw",
    "ambient_temperature_c",
    "module_temperature_c",
    "irradiation",
    "plant_peak_reference_kw",
    "capacity_factor",
    "hour_sin",
    "hour_cos",
]

REQUIRED_COLUMNS = [
    "plant_id",
    "plant_label",
    "timestamp_hour",
    "generation_ac_kw",
]


def _validate_mapping(column_mapping: dict[str, str]) -> None:
    """
    column_mapping format:

    {
        "source_column_name": "standard_column_name"
    }

    Example:
    {
        "datetime": "timestamp_hour",
        "plant": "plant_id",
        "power_kw": "generation_ac_kw"
    }
    """
    invalid_targets = [
        target
        for target in column_mapping.values()
        if target not in STANDARD_COLUMNS
    ]

    if invalid_targets:
        raise ValueError(
            "Column mapping contains unsupported standard columns: "
            f"{invalid_targets}"
        )


def _coerce_boolean_like(series: pd.Series) -> pd.Series:
    """
    Not currently required for Member 1 schema, but useful if this adapter
    is later extended for operational datasets.
    """
    mapping = {
        "true": True,
        "false": False,
        "yes": True,
        "no": False,
        "1": True,
        "0": False,
    }

    if series.dtype == bool:
        return series

    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .map(mapping)
    )


def _parse_timestamp(
    series: pd.Series,
    timestamp_format: Optional[str] = None,
    dayfirst: bool = False,
) -> pd.Series:
    """
    Parse timestamps robustly.

    Use timestamp_format whenever the future dataset has a known fixed format.
    """
    if timestamp_format:
        result = pd.to_datetime(
            series,
            format=timestamp_format,
            errors="coerce",
        )
    else:
        result = pd.to_datetime(
            series,
            errors="coerce",
            dayfirst=dayfirst,
        )

    return result


def _ensure_hourly(
    df: pd.DataFrame,
    hourly_aggregation: bool,
) -> pd.DataFrame:
    """
    Optionally convert sub-hourly data (e.g. 15-minute) into hourly data.

    Aggregation rules:
    - generation_ac_kw        -> sum
    - generation_dc_kw        -> sum
    - temperatures            -> mean
    - irradiation             -> mean
    - plant_peak_reference_kw -> max
    - capacity_factor         -> mean

    If data is already hourly, set hourly_aggregation=False.
    """
    if not hourly_aggregation:
        return df

    df = df.copy()

    df["timestamp_hour"] = (
        pd.to_datetime(df["timestamp_hour"])
        .dt.floor("h")
    )

    agg_rules = {}

    for col in df.columns:
        if col in ["plant_id", "plant_label", "timestamp_hour"]:
            continue

        if col in ["generation_ac_kw", "generation_dc_kw"]:
            agg_rules[col] = "sum"

        elif col in [
            "ambient_temperature_c",
            "module_temperature_c",
            "irradiation",
            "capacity_factor",
        ]:
            agg_rules[col] = "mean"

        elif col == "plant_peak_reference_kw":
            agg_rules[col] = "max"

        elif pd.api.types.is_numeric_dtype(df[col]):
            agg_rules[col] = "mean"

        else:
            agg_rules[col] = "first"

    return (
        df.groupby(
            ["plant_id", "plant_label", "timestamp_hour"],
            as_index=False,
        )
        .agg(agg_rules)
    )


def _add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create cyclic hour features if they are missing.
    """
    df = df.copy()

    hour = df["timestamp_hour"].dt.hour

    if "hour_sin" not in df.columns:
        df["hour_sin"] = np.sin(
            2 * np.pi * hour / 24
        )

    if "hour_cos" not in df.columns:
        df["hour_cos"] = np.cos(
            2 * np.pi * hour / 24
        )

    return df


def _add_capacity_factor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate capacity factor when plant_peak_reference_kw is available
    but capacity_factor is missing.

    capacity_factor = generation_ac_kw / plant_peak_reference_kw
    """
    df = df.copy()

    if (
        "capacity_factor" not in df.columns
        and "plant_peak_reference_kw" in df.columns
    ):
        peak = pd.to_numeric(
            df["plant_peak_reference_kw"],
            errors="coerce",
        )

        generation = pd.to_numeric(
            df["generation_ac_kw"],
            errors="coerce",
        )

        with np.errstate(
            divide="ignore",
            invalid="ignore",
        ):
            cf = generation / peak

        df["capacity_factor"] = (
            cf.replace([np.inf, -np.inf], np.nan)
            .clip(lower=0)
        )

    return df


def _infer_peak_reference(df: pd.DataFrame) -> pd.DataFrame:
    """
    If the future dataset does not contain plant capacity, infer a
    prototype reference value from the 99.5th percentile of generation
    for each plant.

    IMPORTANT:
    This is only a fallback estimate for prototyping.
    Real plant nameplate capacity should be used in production.
    """
    df = df.copy()

    if "plant_peak_reference_kw" not in df.columns:
        peak_map = (
            df.groupby("plant_id")["generation_ac_kw"]
            .quantile(0.995)
            .to_dict()
        )

        df["plant_peak_reference_kw"] = (
            df["plant_id"]
            .map(peak_map)
        )

    return df


def validate_standard_schema(
    df: pd.DataFrame,
    strict: bool = True,
) -> dict:
    """
    Validate the standardized dataset.

    Returns a validation report.
    """
    missing_required = [
        col
        for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    duplicate_keys = 0

    if all(
        col in df.columns
        for col in [
            "plant_id",
            "plant_label",
            "timestamp_hour",
        ]
    ):
        duplicate_keys = int(
            df.duplicated(
                subset=[
                    "plant_id",
                    "plant_label",
                    "timestamp_hour",
                ]
            ).sum()
        )

    invalid_timestamps = (
        int(df["timestamp_hour"].isna().sum())
        if "timestamp_hour" in df.columns
        else None
    )

    negative_generation = (
        int(
            (
                pd.to_numeric(
                    df["generation_ac_kw"],
                    errors="coerce",
                ) < 0
            ).sum()
        )
        if "generation_ac_kw" in df.columns
        else None
    )

    report = {
        "rows": len(df),
        "missing_required_columns": missing_required,
        "duplicate_key_rows": duplicate_keys,
        "invalid_timestamps": invalid_timestamps,
        "negative_generation_rows": negative_generation,
    }

    if strict:
        problems = []

        if missing_required:
            problems.append(
                f"missing required columns: {missing_required}"
            )

        if duplicate_keys > 0:
            problems.append(
                f"{duplicate_keys} duplicate plant/timestamp rows"
            )

        if invalid_timestamps and invalid_timestamps > 0:
            problems.append(
                f"{invalid_timestamps} invalid timestamps"
            )

        if problems:
            raise ValueError(
                "Dataset validation failed: "
                + "; ".join(problems)
            )

    return report


def adapt_dataset(
    input_csv: str | Path,
    column_mapping: dict[str, str],
    output_csv: str | Path | None = None,
    timestamp_format: Optional[str] = None,
    dayfirst: bool = False,
    hourly_aggregation: bool = False,
    default_plant_id: Optional[int | str] = None,
    default_plant_label: Optional[str] = None,
    infer_peak_if_missing: bool = True,
    drop_invalid_rows: bool = True,
) -> pd.DataFrame:
    """
    Convert a new dataset into the project's standard Member 1 schema.

    Parameters
    ----------
    input_csv:
        Path to future raw/processed dataset.

    column_mapping:
        Mapping FROM source column TO standard project column.

        Example:
        {
            "datetime": "timestamp_hour",
            "site_id": "plant_id",
            "solar_kw": "generation_ac_kw",
            "temp": "ambient_temperature_c",
            "ghi": "irradiation",
        }

    hourly_aggregation:
        True if incoming dataset is 5/10/15/30-minute data and needs
        conversion to hourly rows.

    default_plant_id / default_plant_label:
        Useful for a dataset containing only one plant and no explicit
        plant identifier.

    Returns
    -------
    Standardized pandas DataFrame.
    """

    _validate_mapping(column_mapping)

    input_csv = Path(input_csv)

    if not input_csv.exists():
        raise FileNotFoundError(
            f"Dataset not found: {input_csv}"
        )

    df = pd.read_csv(input_csv)

    # -----------------------------------------------------
    # 1. Rename future dataset columns into standard names
    # -----------------------------------------------------
    source_columns = set(column_mapping.keys())

    missing_source = [
        col
        for col in source_columns
        if col not in df.columns
    ]

    if missing_source:
        raise ValueError(
            "These mapped source columns do not exist "
            f"in the dataset: {missing_source}"
        )

    df = df.rename(
        columns=column_mapping
    )

    # -----------------------------------------------------
    # 2. Add default plant identity when necessary
    # -----------------------------------------------------
    if "plant_id" not in df.columns:
        if default_plant_id is None:
            raise ValueError(
                "No plant_id column exists. "
                "Provide a plant mapping or default_plant_id."
            )
        df["plant_id"] = default_plant_id

    if "plant_label" not in df.columns:
        if default_plant_label is None:
            df["plant_label"] = (
                "Plant_"
                + df["plant_id"].astype(str)
            )
        else:
            df["plant_label"] = default_plant_label

    # -----------------------------------------------------
    # 3. Parse timestamp
    # -----------------------------------------------------
    if "timestamp_hour" not in df.columns:
        raise ValueError(
            "The column mapping must provide timestamp_hour."
        )

    df["timestamp_hour"] = _parse_timestamp(
        df["timestamp_hour"],
        timestamp_format=timestamp_format,
        dayfirst=dayfirst,
    )

    # -----------------------------------------------------
    # 4. Convert known numerical fields
    # -----------------------------------------------------
    numeric_fields = [
        "generation_ac_kw",
        "generation_dc_kw",
        "ambient_temperature_c",
        "module_temperature_c",
        "irradiation",
        "plant_peak_reference_kw",
        "capacity_factor",
        "hour_sin",
        "hour_cos",
    ]

    for col in numeric_fields:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce",
            )

    # -----------------------------------------------------
    # 5. Basic cleanup
    # -----------------------------------------------------
    if "generation_ac_kw" in df.columns:
        df["generation_ac_kw"] = (
            df["generation_ac_kw"]
            .clip(lower=0)
        )

    if "generation_dc_kw" in df.columns:
        df["generation_dc_kw"] = (
            df["generation_dc_kw"]
            .clip(lower=0)
        )

    if "irradiation" in df.columns:
        df["irradiation"] = (
            df["irradiation"]
            .clip(lower=0)
        )

    if drop_invalid_rows:
        required_now = [
            col
            for col in [
                "timestamp_hour",
                "generation_ac_kw",
            ]
            if col in df.columns
        ]

        df = df.dropna(
            subset=required_now
        )

    # -----------------------------------------------------
    # 6. Optional conversion to hourly data
    # -----------------------------------------------------
    df = _ensure_hourly(
        df,
        hourly_aggregation=hourly_aggregation,
    )

    # -----------------------------------------------------
    # 7. Add/fill derived project features
    # -----------------------------------------------------
    if infer_peak_if_missing:
        df = _infer_peak_reference(df)

    df = _add_capacity_factor(df)
    df = _add_time_features(df)

    # -----------------------------------------------------
    # 8. Keep standard columns first, extras afterwards
    # -----------------------------------------------------
    standard_present = [
        c
        for c in STANDARD_COLUMNS
        if c in df.columns
    ]

    extras = [
        c
        for c in df.columns
        if c not in standard_present
    ]

    df = df[
        standard_present + extras
    ]

    # -----------------------------------------------------
    # 9. Sort and remove duplicate keys
    # -----------------------------------------------------
    df = df.sort_values(
        [
            "plant_id",
            "timestamp_hour",
        ]
    ).reset_index(drop=True)

    df = df.drop_duplicates(
        subset=[
            "plant_id",
            "plant_label",
            "timestamp_hour",
        ],
        keep="last",
    ).reset_index(drop=True)

    # -----------------------------------------------------
    # 10. Validate
    # -----------------------------------------------------
    report = validate_standard_schema(
        df,
        strict=True,
    )

    print("\nDataset adapter validation")
    print("--------------------------")
    for key, value in report.items():
        print(f"{key}: {value}")

    # -----------------------------------------------------
    # 11. Save
    # -----------------------------------------------------
    if output_csv is not None:
        output_csv = Path(output_csv)
        output_csv.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df.to_csv(
            output_csv,
            index=False,
        )

        print(
            f"\nStandardized dataset saved to: "
            f"{output_csv}"
        )

    return df


# =========================================================
# EXAMPLE 1
# Your CURRENT dataset
# =========================================================

CURRENT_DATASET_MAPPING = {
    "plant_id": "plant_id",
    "plant_label": "plant_label",
    "timestamp_hour": "timestamp_hour",
    "generation_ac_kw": "generation_ac_kw",
    "generation_dc_kw": "generation_dc_kw",
    "ambient_temperature_c": "ambient_temperature_c",
    "module_temperature_c": "module_temperature_c",
    "irradiation": "irradiation",
    "plant_peak_reference_kw": "plant_peak_reference_kw",
    "capacity_factor": "capacity_factor",
    "hour_sin": "hour_sin",
    "hour_cos": "hour_cos",
}


# =========================================================
# EXAMPLE 2
# Hypothetical FUTURE dataset
# =========================================================

EXAMPLE_FUTURE_MAPPING = {
    "site_id": "plant_id",
    "site_name": "plant_label",
    "datetime": "timestamp_hour",
    "solar_output_kw": "generation_ac_kw",
    "dc_output_kw": "generation_dc_kw",
    "ambient_temp": "ambient_temperature_c",
    "panel_temp": "module_temperature_c",
    "solar_irradiance": "irradiation",
    "rated_capacity_kw": "plant_peak_reference_kw",
}


if __name__ == "__main__":
    # Example for the current project dataset.
    #
    # Change INPUT and MAPPING whenever the project dataset changes.

    INPUT = "ml_hourly_training_dataset.csv"
    OUTPUT = "standardized_ml_dataset.csv"

    standardized = adapt_dataset(
        input_csv=INPUT,
        column_mapping=CURRENT_DATASET_MAPPING,
        output_csv=OUTPUT,
        hourly_aggregation=False,
    )

    print("\nFirst 5 standardized rows:")
    print(standardized.head())
