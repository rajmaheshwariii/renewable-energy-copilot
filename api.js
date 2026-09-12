const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  let body = null
  try { body = await response.json() } catch { /* backend may be unavailable */ }

  if (!response.ok) {
    const message = body?.detail || `Backend request failed (${response.status})`
    throw new Error(message)
  }

  return body
}

export async function checkMember3Backend() {
  return apiFetch('/health')
}

export async function getDecision(inputs) {
  return apiFetch('/decision', {
    method: 'POST',
    body: JSON.stringify(inputs),
  })
}

export async function runWhatIf(baseInputs, changedValues) {
  return apiFetch('/what-if', {
    method: 'POST',
    body: JSON.stringify({ base_inputs: baseInputs, changed_values: changedValues }),
  })
}

export async function compareModes(inputs) {
  return apiFetch('/compare-modes', {
    method: 'POST',
    body: JSON.stringify(inputs),
  })
}

// Temporary adapter used until Member 1 and Member 2 APIs are connected.
// Forecast generation and demand come from the current frontend demo model;
// Member 3 itself runs in Python through FastAPI.
export function buildMember3Inputs(site, point, scenario, riskScore = 68) {
  const plantCapacityKw = site.capacity * 1000

  return {
    predicted_generation_kw: point.generation * 1000,
    demand_kw: point.demand * 1000,
    battery_soc_pct: scenario.battery,
    battery_capacity_kwh: site.capacity * 1000 * 0.8,
    max_charge_rate_kw: plantCapacityKw * 0.25,
    max_discharge_rate_kw: plantCapacityKw * 0.25,
    backup_available: scenario.backup,
    backup_capacity_kw: plantCapacityKw * 0.4,
    grid_export_available: true,
    grid_export_limit_kw: plantCapacityKw * 0.3,
    risk_score: riskScore,
    forecast_uncertainty_pct: 10,
    electricity_price_inr_per_mwh: 6000,
    backup_cost_inr_per_mwh: 14000,
    backup_co2_kg_per_mwh: 700,
    battery_degradation_cost_inr_per_mwh: 1200,
    battery_health_pct: 95,
    future_peak_price_inr_per_mwh: 12500,
    future_peak_shortage_kw: 3500,
    optimization_mode: 'balanced',
    max_soc_pct: 90,
    interval_hours: 1,
  }
}
