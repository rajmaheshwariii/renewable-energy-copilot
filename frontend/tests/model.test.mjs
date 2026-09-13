import assert from 'node:assert/strict'
import { test } from 'node:test'
import { defaultScenario, forecast, sites, summarize } from '../src/testing/demo_forecast_helpers.js'

test('generation stays within capacity and intervals contain predictions for all sites and horizons', () => {
  for (const site of sites) for (const horizon of [24, 48, 72]) {
    const data = forecast(site, horizon)
    assert.equal(data.length, horizon + 1)
    for (const p of data) {
      assert.ok(p.generation >= 0 && p.generation <= site.capacity)
      assert.ok(p.band[0] <= p.generation && p.band[1] >= p.generation)
      assert.ok(p.demand >= 0)
    }
    const totals = summarize(site, data)
    assert.equal(totals.energy, data.slice(0, -1).reduce((sum, p) => sum + p.generation, 0))
    assert.ok(totals.risk >= 0 && totals.risk <= 100)
  }
})

test('more cloud reduces solar energy while wind-only generation is unaffected', () => {
  const cloudy = { ...defaultScenario, cloud: 90 }
  const total = (site, input) => summarize(site, forecast(site, 24, input), input).energy
  assert.ok(total(sites[0], cloudy) < total(sites[0], defaultScenario))
  assert.equal(total(sites[2], cloudy), total(sites[2], defaultScenario))
})

test('demand and backup stress raises risk; storage reduces estimated supply cost', () => {
  const site = sites[0]
  const result = input => summarize(site, forecast(site, 24, input), input)
  const base = result(defaultScenario)
  assert.ok(result({ ...defaultScenario, demand: 60, battery: 0, backup: false }).risk > base.risk)
  assert.ok(result({ ...defaultScenario, battery: 100 }).cost < result({ ...defaultScenario, battery: 0 }).cost)
})
