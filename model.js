export const sites = [
  { id: 'kutch', name: 'Kutch Hybrid Park', location: 'Gujarat, India', capacity: 100, solar: 62, wind: 38, battery: 72 },
  { id: 'jaisalmer', name: 'Jaisalmer Energy Park', location: 'Rajasthan, India', capacity: 80, solar: 55, wind: 25, battery: 64 },
  { id: 'tirunelveli', name: 'Tirunelveli Wind Farm', location: 'Tamil Nadu, India', capacity: 60, solar: 0, wind: 60, battery: 58 },
]
export const defaultScenario = { cloud: 28, demand: 0, battery: 72, backup: true }
// Deterministic synthetic fixtures; these are not outputs from an ML model.
export function forecast(site, horizon = 24, scenario = defaultScenario) {
  return Array.from({ length: horizon + 1 }, (_, index) => {
    const hour = (index + 6) % 24
    const sunlight = Math.max(0, Math.sin((hour - 6) / 12 * Math.PI))
    const solar = site.solar * sunlight * (1 - scenario.cloud / 145)
    const wind = site.wind * (.53 + .13 * Math.sin(index * .48 + 1))
    const generation = Math.round((solar + wind) * 10) / 10
    const demand = Math.round(site.capacity * (.43 + .13 * Math.sin((hour - 12) / 12 * Math.PI)) * (1 + scenario.demand / 100) * 10) / 10
    const spread = generation * (.11 + index / 650)
    return { index, time: `${String(hour).padStart(2, '0')}:00`, day: Math.floor((index + 6) / 24) + 1, solar: +solar.toFixed(1), wind: +wind.toFixed(1), generation, demand, band: [Math.max(0, generation - spread), generation + spread], actual: index <= 5 ? +(generation * (1 + .035 * Math.sin(index * 2))).toFixed(1) : null }
  })
}
export function summarize(site, data, scenario = defaultScenario) {
  const intervals = data.slice(0, -1)
  const energy = intervals.reduce((total, item) => total + item.generation, 0)
  const shortage = intervals.reduce((total, item) => total + Math.max(0, item.demand - item.generation), 0)
  const surplus = intervals.reduce((total, item) => total + Math.max(0, item.generation - item.demand), 0)
  const batteryEnergy = site.capacity * .8 * scenario.battery / 100
  const uncovered = Math.max(0, shortage - batteryEnergy)
  const risk = Math.min(100, Math.max(0, Math.round(18 + uncovered / site.capacity * 8 + scenario.cloud * .12 - (scenario.backup ? 12 : 0))))
  return { energy, shortage, surplus, risk, batteryEnergy, cost: uncovered * (scenario.backup ? 7200 : 11000), co2: uncovered * (scenario.backup ? .7 : .82), avoided: energy * .71, peak: Math.max(...data.map(p => p.generation)) }
}
export function riskLabel(value) { return value < 40 ? 'Low risk' : value < 65 ? 'Moderate risk' : 'High risk' }
export function number(value, digits = 0) { return new Intl.NumberFormat('en-IN', { maximumFractionDigits: digits }).format(value) }
export function downloadFile(name, text, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type }))
  const link = document.createElement('a')
  link.href = url; link.download = name; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function forecastCsv(site, data) {
  return ['Data source,Synthetic demo', `Site,${site.name}`, 'Day,Time,Solar MW,Wind MW,Forecast MW,Demand MW,Lower MW,Upper MW', ...data.map(p => `${p.day},${p.time},${p.solar},${p.wind},${p.generation},${p.demand},${p.band[0].toFixed(2)},${p.band[1].toFixed(2)}`)].join('\n')
}
