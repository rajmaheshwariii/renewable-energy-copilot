from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .decision_support.scenario_simulator import run_pipeline, compare_scenarios
    from .decision_support.optimization_comparison import compare_optimization_modes
    from .decision_support.digital_twin_planner import plan_horizon
    from .risk_and_explainability.risk_calculator import calculate_risk
    from .forecasting.forecast_service import forecast_for_plant, explain_forecast_for_plant, forecast_model_metrics, forecast_origin_bounds
except ImportError:
    from decision_support.scenario_simulator import run_pipeline, compare_scenarios
    from decision_support.optimization_comparison import compare_optimization_modes
    from decision_support.digital_twin_planner import plan_horizon
    from risk_and_explainability.risk_calculator import calculate_risk
    from forecasting.forecast_service import forecast_for_plant, explain_forecast_for_plant, forecast_model_metrics, forecast_origin_bounds


OptimizationMode = Literal[
    "balanced",
    "lowest_cost",
    "lowest_co2",
    "maximum_reliability",
]


class RiskInputs(BaseModel):
    predicted_generation_kw: float = Field(ge=0)
    demand_kw: float = Field(ge=0)
    battery_soc_pct: float = Field(ge=0, le=100)
    forecast_uncertainty_pct: float = Field(ge=0)
    backup_available: bool = True
    backup_capacity_kw: float = Field(default=0, ge=0)
    grid_export_available: bool = True
    grid_export_limit_kw: float = Field(default=0, ge=0)


class DecisionInputs(BaseModel):
    predicted_generation_kw: float = Field(ge=0)
    demand_kw: float = Field(ge=0)
    battery_soc_pct: float = Field(ge=0, le=100)
    battery_capacity_kwh: float = Field(gt=0)
    max_charge_rate_kw: float = Field(ge=0)
    max_discharge_rate_kw: float = Field(ge=0)
    backup_available: bool
    backup_capacity_kw: float = Field(ge=0)
    grid_export_available: bool = True
    grid_export_limit_kw: float = Field(ge=0)
    risk_score: float | None = Field(default=None, ge=0, le=100)
    forecast_uncertainty_pct: float = Field(ge=0)
    electricity_price_inr_per_mwh: float = Field(ge=0)
    backup_cost_inr_per_mwh: float = Field(ge=0)
    backup_co2_kg_per_mwh: float = Field(ge=0)
    battery_degradation_cost_inr_per_mwh: float = Field(default=1200, ge=0)
    battery_health_pct: float = Field(default=95, ge=0, le=100)
    future_peak_price_inr_per_mwh: float | None = Field(default=None, ge=0)
    future_peak_shortage_kw: float = Field(default=0, ge=0)
    optimization_mode: OptimizationMode = "balanced"
    max_soc_pct: float = Field(default=90, ge=0, le=100)
    interval_hours: float = Field(default=1, gt=0)


class WhatIfRequest(BaseModel):
    base_inputs: DecisionInputs
    changed_values: dict[str, Any]


class MultipleScenarioRequest(BaseModel):
    base_inputs: DecisionInputs
    scenarios: dict[str, dict[str, Any]]


class HorizonPlanRequest(BaseModel):
    plant_id: int
    predicted_generation_kw: list[float] = Field(min_length=1, max_length=168)
    forecast_uncertainty_pct: float = Field(ge=0)
    optimization_mode: OptimizationMode = "balanced"
    risk_score: float | None = Field(default=None, ge=0, le=100)


app = FastAPI(
    title="Renewable Energy Copilot API",
    version="5.1.0",
    description=(
        "Forecasting, risk assessment, explanations, and decision support are integrated end to end."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_operational() -> pd.DataFrame:
    path = Path(__file__).resolve().parent / "decision_support/operational_data.csv"
    if not path.exists():
        raise FileNotFoundError("operational_data.csv was not found")
    df = pd.read_csv(path)
    df["timestamp_hour"] = pd.to_datetime(df["timestamp_hour"])
    return df


def _serialize_plan(plan_df: pd.DataFrame) -> list[dict]:
    records = []
    for record in plan_df.to_dict(orient="records"):
        out = {}
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                out[key] = value.isoformat()
            elif pd.isna(value):
                out[key] = None
            elif hasattr(value, "item"):
                out[key] = value.item()
            else:
                out[key] = value
        records.append(out)
    return records


def _risk_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    return calculate_risk(
        forecast_kw=float(data["predicted_generation_kw"]),
        demand_kw=float(data["demand_kw"]),
        battery_soc_pct=float(data["battery_soc_pct"]),
        uncertainty_pct=float(data["forecast_uncertainty_pct"]),
        backup_available=bool(data["backup_available"]),
        backup_capacity_kw=float(data["backup_capacity_kw"]),
        grid_export_available=bool(data["grid_export_available"]),
        grid_export_limit_kw=float(data["grid_export_limit_kw"]),
    )


def _with_risk_assessment(data: dict[str, Any], force: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    enriched = deepcopy(data)
    assessment = _risk_from_dict(enriched)
    if force or enriched.get("risk_score") is None:
        enriched["risk_score"] = assessment["risk_score"]
    return enriched, assessment


def _pipeline_with_risk(data: dict[str, Any]) -> dict[str, Any]:
    enriched, risk = _with_risk_assessment(data)
    result = run_pipeline(enriched)
    result["risk_assessment"] = risk
    return result


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "renewable-energy-copilot-api",
        "version": app.version,
        "forecasting": "ready",
        "risk_assessment": "ready",
        "forecast_explanation": "ready",
        "decision_support": "ready",
        "message": "Forecasting, explanations, risk assessment, and decision support are ready.",
    }


@app.get("/forecast/plant/{plant_id}")
def plant_forecast(plant_id: int, horizon_hours: int = 72, origin_time: str | None = None) -> dict:
    """Return a 1-72 hour generation forecast from a selected historical or upcoming start time."""
    try:
        return forecast_for_plant(plant_id=plant_id, horizon_hours=horizon_hours, origin_time=origin_time)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Forecast failed: {exc}") from exc


@app.get("/forecast/metrics")
def forecast_metrics() -> dict:
    try:
        return forecast_model_metrics()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Forecast metrics failed: {exc}") from exc


@app.get("/forecast/explain/{plant_id}")
def forecast_explain(plant_id: int, horizon: int = 1, top_n: int = 8, origin_time: str | None = None) -> dict:
    try:
        return explain_forecast_for_plant(plant_id=plant_id, horizon=horizon, top_n=top_n, origin_time=origin_time)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Forecast explanation failed: {exc}") from exc


@app.get("/copilot/current/{plant_id}")
def copilot_current(plant_id: int, optimization_mode: OptimizationMode = "balanced") -> dict:
    """End-to-end forecast, risk, and decision result for the latest operational row."""
    try:
        ops = _load_operational()
        rows = ops[ops["plant_id"] == plant_id].sort_values("timestamp_hour")
        if rows.empty:
            raise ValueError(f"No operational rows found for plant_id={plant_id}")
        row = rows.iloc[-1]
        fc = forecast_for_plant(plant_id=plant_id, horizon_hours=1)
        point = fc["points"][0]
        data = {
            "predicted_generation_kw": float(point["p50_kw"]),
            "demand_kw": float(row["demand_kw"]),
            "battery_soc_pct": float(row["battery_soc_pct"]),
            "battery_capacity_kwh": float(row["battery_capacity_kwh"]),
            "max_charge_rate_kw": float(row["max_charge_rate_kw"]),
            "max_discharge_rate_kw": float(row["max_discharge_rate_kw"]),
            "backup_available": bool(row["backup_available"]),
            "backup_capacity_kw": float(row["backup_capacity_kw"]),
            "grid_export_available": bool(row["grid_export_available"]),
            "grid_export_limit_kw": float(row["grid_export_limit_kw"]),
            "risk_score": None,
            "forecast_uncertainty_pct": float(point["forecast_uncertainty_pct"]),
            "electricity_price_inr_per_mwh": float(row["electricity_price_inr_per_mwh"]),
            "backup_cost_inr_per_mwh": float(row["backup_cost_inr_per_mwh"]),
            "backup_co2_kg_per_mwh": float(row["backup_co2_kg_per_mwh"]),
            "optimization_mode": optimization_mode,
        }
        result = _pipeline_with_risk(data)
        return {
            "forecast": point,
            "operational_timestamp": pd.Timestamp(row["timestamp_hour"]).isoformat(),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Integrated copilot run failed: {exc}") from exc


@app.get("/plants")
def plants() -> dict:
    try:
        df = _load_operational()
        result = []
        for (plant_id, plant_label), group in df.groupby(["plant_id", "plant_label"]):
            bounds = forecast_origin_bounds(int(plant_id))
            result.append({
                "plant_id": int(plant_id),
                "plant_label": str(plant_label),
                "first_timestamp": group["timestamp_hour"].min().isoformat(),
                "last_timestamp": group["timestamp_hour"].max().isoformat(),
                "earliest_forecast_origin": bounds["earliest_origin_time"],
                "latest_forecast_origin": bounds["latest_origin_time"],
                "latest_historical_origin": bounds.get("latest_historical_origin_time", group["timestamp_hour"].max().isoformat()),
                "future_planning_days": bounds.get("future_planning_days", 0),
                "row_count": int(len(group)),
            })
        return {"plants": result}
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/operations/plant/{plant_id}")
def plant_operations(plant_id: int, limit: int = 72) -> dict:
    try:
        if limit < 1 or limit > 168:
            raise ValueError("limit must be between 1 and 168")
        df = _load_operational()
        rows = df[df["plant_id"] == plant_id].sort_values("timestamp_hour")
        if rows.empty:
            raise ValueError(f"No operational rows found for plant_id={plant_id}")
        rows = rows.tail(limit)
        plant_label = str(rows.iloc[-1]["plant_label"])
        fields = [
            "plant_id", "plant_label", "timestamp_hour", "demand_kw",
            "battery_soc_pct", "battery_capacity_kwh", "max_charge_rate_kw",
            "max_discharge_rate_kw", "battery_power_kw", "backup_available",
            "backup_capacity_kw", "grid_export_available", "grid_export_limit_kw",
            "electricity_price_inr_per_mwh", "backup_cost_inr_per_mwh",
            "backup_co2_kg_per_mwh", "operational_fields_source",
        ]
        payload = []
        for _, row in rows.iterrows():
            item = {}
            for field in fields:
                value = row[field]
                if field == "timestamp_hour":
                    item[field] = pd.Timestamp(value).isoformat()
                elif field in {"backup_available", "grid_export_available"}:
                    item[field] = bool(value)
                elif field == "plant_id":
                    item[field] = int(value)
                elif field in {"plant_label", "operational_fields_source"}:
                    item[field] = str(value)
                else:
                    item[field] = float(value)
            payload.append(item)
        return {
            "plant": {"plant_id": int(plant_id), "plant_label": plant_label},
            "rows": payload,
            "note": "Values are read from decision_support/operational_data.csv.",
        }
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/risk")
def risk(inputs: RiskInputs) -> dict:
    try:
        data = inputs.model_dump()
        data["predicted_generation_kw"] = data.pop("predicted_generation_kw")
        data["forecast_uncertainty_pct"] = data.pop("forecast_uncertainty_pct")
        return _risk_from_dict(data)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/decision")
def decision(inputs: DecisionInputs) -> dict:
    try:
        return _pipeline_with_risk(inputs.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/what-if")
def what_if(request: WhatIfRequest) -> dict:
    try:
        raw_base = request.base_inputs.model_dump()
        base_result = _pipeline_with_risk(raw_base)

        changed = deepcopy(raw_base)
        allowed = set(raw_base.keys())
        for key, value in request.changed_values.items():
            if key not in allowed:
                raise ValueError(f"Unknown What-If field: {key}")
            changed[key] = value
        changed["risk_score"] = None
        what_if_result = _pipeline_with_risk(changed)

        comparison = compare_scenarios(base_result, what_if_result)
        return {
            "base": base_result,
            "what_if": what_if_result,
            "comparison": comparison,
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/compare-modes")
def compare_modes(inputs: DecisionInputs) -> dict:
    try:
        enriched, risk_assessment = _with_risk_assessment(inputs.model_dump())
        result = compare_optimization_modes(enriched)
        result["risk_assessment"] = risk_assessment
        return result
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/multiple-scenarios")
def multiple_scenarios(request: MultipleScenarioRequest) -> dict:
    try:
        if not request.scenarios:
            raise ValueError("At least one scenario is required.")

        raw_base = request.base_inputs.model_dump()
        results = []
        for scenario_name, changes in request.scenarios.items():
            scenario = deepcopy(raw_base)
            for key, value in changes.items():
                if key not in scenario:
                    raise ValueError(f"Unknown scenario field: {key}")
                scenario[key] = value
            scenario["risk_score"] = None
            results.append({
                "scenario_name": scenario_name,
                "changes": changes,
                "result": _pipeline_with_risk(scenario),
            })
        return {"results": results}
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/plan-horizon")
def plan_horizon_request(request: HorizonPlanRequest) -> dict:
    try:
        hours = len(request.predicted_generation_kw)
        df = _load_operational()
        rows = (
            df[df["plant_id"] == request.plant_id]
            .sort_values("timestamp_hour")
            .tail(hours)
            .copy()
        )
        if len(rows) != hours:
            raise ValueError(
                f"Requested {hours} planning hours but only {len(rows)} operational rows are available."
            )

        rows["predicted_generation_kw"] = [float(x) for x in request.predicted_generation_kw]
        rows["forecast_uncertainty_pct"] = float(request.forecast_uncertainty_pct)

        risk_scores = []
        risk_levels = []
        for _, row in rows.iterrows():
            risk_assessment = calculate_risk(
                forecast_kw=float(row["predicted_generation_kw"]),
                demand_kw=float(row["demand_kw"]),
                battery_soc_pct=float(row["battery_soc_pct"]),
                uncertainty_pct=float(request.forecast_uncertainty_pct),
                backup_available=bool(row["backup_available"]),
                backup_capacity_kw=float(row["backup_capacity_kw"]),
                grid_export_available=bool(row["grid_export_available"]),
                grid_export_limit_kw=float(row["grid_export_limit_kw"]),
            )
            score = float(request.risk_score) if request.risk_score is not None else float(risk_assessment["risk_score"])
            risk_scores.append(score)
            risk_levels.append(risk_assessment["risk_level"])

        rows["risk_score"] = risk_scores

        plan_df, summary = plan_horizon(
            rows,
            predicted_generation_col="predicted_generation_kw",
            optimization_mode=request.optimization_mode,
            risk_score_col="risk_score",
            uncertainty_col="forecast_uncertainty_pct",
            min_planning_hours=1,
        )

        peak = summary.get("peak_demand", {})
        if isinstance(peak.get("timestamp"), pd.Timestamp):
            peak["timestamp"] = peak["timestamp"].isoformat()

        plan_records = _serialize_plan(plan_df)
        for index, item in enumerate(plan_records):
            item["risk_score"] = round(float(risk_scores[index]), 2)
            item["risk_level"] = risk_levels[index]

        return {
            "plan": plan_records,
            "summary": summary,
            "source": {
                "operational_rows": "decision_support/operational_data.csv",
                "predicted_generation": "supplied in request",
                "risk_score": "calculated by the risk assessment engine" if request.risk_score is None else "supplied override",
                "forecast_uncertainty": "supplied in request",
            },
        }
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
