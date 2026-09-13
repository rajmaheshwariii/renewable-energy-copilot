const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  let body = null
  try { body = await response.json() } catch { /* ignore */ }
  if (!response.ok) throw new Error(body?.detail || `Request failed (${response.status})`)
  return body
}

const post = (path, body) => apiFetch(path, { method: 'POST', body: JSON.stringify(body) })

export const getHealth = () => apiFetch('/health')
export const getPlants = () => apiFetch('/plants')
export const getPlantOperations = (plantId, limit = 72) =>
  apiFetch(`/operations/plant/${Number(plantId)}?limit=${Number(limit)}`)
export const runRiskAssessment = inputs => post('/risk', inputs)
export const runDecision = inputs => post('/decision', inputs)
export const runWhatIf = (baseInputs, changedValues) => post('/what-if', { base_inputs: baseInputs, changed_values: changedValues })
export const compareModes = inputs => post('/compare-modes', inputs)
export const compareMultipleScenarios = (baseInputs, scenarios) => post('/multiple-scenarios', { base_inputs: baseInputs, scenarios })
export const runHorizonPlan = payload => post('/plan-horizon', payload)

export const getPlantForecast = (plantId, horizonHours = 72, originTime = null) => {
  const params = new URLSearchParams({ horizon_hours: String(Number(horizonHours)) })
  if (originTime) params.set('origin_time', originTime)
  return apiFetch(`/forecast/plant/${Number(plantId)}?${params.toString()}`)
}

export const getIntegratedCurrent = (plantId, optimizationMode = 'balanced') =>
  apiFetch(`/copilot/current/${Number(plantId)}?optimization_mode=${encodeURIComponent(optimizationMode)}`)

export const getForecastExplanation = (plantId, horizon = 1, topN = 8, originTime = null) => {
  const params = new URLSearchParams({ horizon: String(Number(horizon)), top_n: String(Number(topN)) })
  if (originTime) params.set('origin_time', originTime)
  return apiFetch(`/forecast/explain/${Number(plantId)}?${params.toString()}`)
}

export const getForecastMetrics = () => apiFetch('/forecast/metrics')
