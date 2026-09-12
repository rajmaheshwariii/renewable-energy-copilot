from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .what_if_simulator import run_pipeline, simulate_scenario, compare_scenarios
    from .mode_optimizer import compare_optimization_modes
except ImportError:
    from what_if_simulator import run_pipeline, simulate_scenario, compare_scenarios
    from mode_optimizer import compare_optimization_modes


OptimizationMode = Literal[
    "balanced",
    "lowest_cost",
    "lowest_co2",
    "maximum_reliability",
]


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
    risk_score: float = Field(default=50, ge=0, le=100)
    forecast_uncertainty_pct: float = Field(default=10, ge=0)
    electricity_price_inr_per_mwh: float = Field(default=6000, ge=0)
    backup_cost_inr_per_mwh: float = Field(default=14000, ge=0)
    backup_co2_kg_per_mwh: float = Field(default=700, ge=0)
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


app = FastAPI(
    title="Renewable Energy Copilot - Member 3 API",
    version="1.0.0",
    description=(
        "API bridge between the React frontend and Member 3 decision, "
        "What-If, impact, and optimization modules."
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


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "member3-decision-api",
        "message": "Member 3 decision services are ready.",
    }


@app.post("/decision")
def decision(inputs: DecisionInputs) -> dict:
    try:
        return run_pipeline(inputs.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/what-if")
def what_if(request: WhatIfRequest) -> dict:
    try:
        base_inputs = request.base_inputs.model_dump()
        base_result = run_pipeline(base_inputs)
        what_if_result = simulate_scenario(base_inputs, request.changed_values)
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
        return compare_optimization_modes(inputs.model_dump())
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
