import { useEffect, useMemo, useState } from 'react'
import {
  Activity, ArrowRight, BatteryCharging, Cable, ChevronDown, ChevronRight,
  CircleHelp, Download, FlaskConical, LayoutDashboard, Leaf, Loader2, MapPin,
  Menu, PanelLeftClose, RefreshCw, Settings, ShieldCheck, SlidersHorizontal,
  Sparkles, TrendingUp, X, Zap
} from 'lucide-react'
import {
  getPlants, getPlantOperations, runRiskAssessment, runDecision, runWhatIf,
  compareModes, compareMultipleScenarios, runHorizonPlan, getPlantForecast,
  getForecastExplanation
} from './services/backend_api'
import './App.css'

const navigation = [
  { name: 'Overview', icon: LayoutDashboard, group: 'WORKSPACE' },
  { name: 'Generation forecast', icon: TrendingUp },
  { name: 'AI insights', icon: Sparkles },
  { name: 'Risk & decisions', icon: ShieldCheck },
  { name: 'What-If simulator', icon: SlidersHorizontal },
  { name: 'Digital twin', icon: Cable },
  { name: 'Impact & reports', icon: Leaf, group: 'ANALYTICS' },
]

const pageInfo = {
  Overview: ['Your energy, in perspective.', 'See the most important operating conditions at a glance.'],
  'Generation forecast': ['Plan the next 72 hours.', 'Choose a date and time, then view the expected renewable generation for the following 72 hours.'],
  'AI insights': ['Understand what is driving the forecast.', 'See the strongest factors behind the expected generation and the resulting operating risk.'],
  'Risk & decisions': ['Turn the forecast into action.', 'Review risk and get a practical recommendation for battery, backup, export, or curtailment.'],
  'What-If simulator': ['Explore the possibilities.', 'Change demand, battery level, backup, or grid support and compare the outcome.'],
  'Digital twin': ['Simulate the next 72 hours.', 'See how battery level, cost, emissions, and supply balance evolve hour by hour.'],
  'Impact & reports': ['Measure what matters.', 'Compare scenarios and understand their cost, emissions, and reliability impact.'],
  Settings: ['Personalize your workspace.', 'Choose the defaults that make the dashboard easier for you to use.'],
}

const MODES = [
  ['balanced', 'Balanced'],
  ['lowest_cost', 'Lowest cost'],
  ['lowest_co2', 'Lowest emissions'],
  ['maximum_reliability', 'Highest reliability'],
]

const num = (v, d = 1) => Number(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: d })
const mw = kw => `${num(Number(kw) / 1000, 2)} MW`
const money = v => `₹${num(v, 2)}`
const formatDateTime = value => value ? new Date(value).toLocaleString() : '—'
const datetimeLocal = value => value ? String(value).slice(0, 16) : ''
const safeName = value => String(value || 'renewable-energy').replace(/[^a-z0-9_-]+/gi, '_')

const friendlyMode = mode => ({
  balanced: 'Balanced',
  lowest_cost: 'Lowest cost',
  lowest_co2: 'Lowest emissions',
  maximum_reliability: 'Highest reliability',
}[mode] || String(mode || '').replaceAll('_', ' '))

const friendlyAction = action => ({
  DISCHARGE_BATTERY: 'Use stored battery energy',
  CHARGE_BATTERY: 'Charge the battery',
  ACTIVATE_BACKUP: 'Use backup power',
  EXPORT_TO_GRID: 'Export extra energy to the grid',
  CURTAIL_RENEWABLE: 'Reduce renewable output',
  NO_ACTION: 'No special action needed',
}[action] || String(action || 'No action').replaceAll('_', ' ').toLowerCase())

const friendlyCondition = condition => ({
  SHORTAGE: 'Energy shortage expected',
  SURPLUS: 'Extra energy expected',
  NORMAL: 'Normal operating range',
  HIGH_UNCERTAINTY: 'Forecast is less certain',
}[condition] || String(condition || '').replaceAll('_', ' ').toLowerCase())

const friendlyFlag = flag => ({
  'night/low-sun': 'Night / very low sunlight',
  'expected high generation': 'High generation expected',
  'expected low generation': 'Low generation expected',
  'within normal range': 'Normal generation expected',
}[flag] || flag)

const FEATURE_NAMES = {
  gen_lag_1: 'Generation one hour earlier',
  gen_lag_2: 'Generation two hours earlier',
  gen_lag_3: 'Generation three hours earlier',
  gen_lag_24: 'Generation at the same time yesterday',
  gen_lag_48: 'Generation at the same time two days earlier',
  gen_lag_72: 'Generation at the same time three days earlier',
  gen_rollmean_24: 'Average generation during the previous day',
  gen_rollmean_72: 'Average generation during the previous three days',
  gen_rollstd_24: 'How much generation varied during the previous day',
  gen_rollstd_72: 'How much generation varied during the previous three days',
  irr_origin: 'Recent sunlight level',
  ambient_origin: 'Recent air temperature',
  module_origin: 'Recent solar panel temperature',
  plant_peak_reference_kw: 'Plant generation capacity',
  horizon: 'How far ahead the forecast is',
  target_hour_sin: 'Time of day pattern',
  target_hour_cos: 'Time of day pattern',
  target_doy_sin: 'Seasonal time pattern',
  target_doy_cos: 'Seasonal time pattern',
  target_dow: 'Day of the week',
  irradiation_clim: 'Typical sunlight for this hour',
  ambient_temperature_c_clim: 'Typical air temperature for this hour',
  module_temperature_c_clim: 'Typical solar panel temperature for this hour',
}

const friendlyFeature = feature => FEATURE_NAMES[feature] || String(feature || '').replaceAll('_', ' ')
const friendlyDirection = impact => Number(impact) > 0 ? 'Raises expected generation' : Number(impact) < 0 ? 'Lowers expected generation' : 'Little or no effect'
const friendlyFeatureValue = (feature, value) => {
  const v = Number(value)
  if (!Number.isFinite(v)) return '—'
  if (feature.startsWith('gen_lag_') || feature.startsWith('gen_rollmean_') || feature.startsWith('gen_rollstd_') || feature === 'plant_peak_reference_kw') return mw(v)
  if (feature === 'ambient_origin' || feature === 'module_origin' || feature === 'ambient_temperature_c_clim' || feature === 'module_temperature_c_clim') return `${num(v,1)} °C`
  if (feature === 'irr_origin' || feature === 'irradiation_clim') return `${num(v * 100,1)}% sunlight level`
  if (feature === 'horizon') return `${num(v,0)} hours ahead`
  if (feature === 'target_dow') return ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'][Math.max(0,Math.min(6,Math.round(v)))]
  if (['target_hour_sin','target_hour_cos'].includes(feature)) return 'Time-of-day pattern'
  if (['target_doy_sin','target_doy_cos'].includes(feature)) return 'Seasonal pattern'
  return num(v,3)
}
const friendlyImpact = value => {
  const impact = Number(value || 0)
  if (Math.abs(impact) < 0.01) return 'Very little change'
  return `${impact >= 0 ? 'Raises' : 'Lowers'} expected generation by ${num(Math.abs(impact)/1000,2)} MW`
}

function Badge({ children, tone = 'green' }) { return <span className={`badge ${tone}`}>{children}</span> }
function IconBox({ icon: Icon, tone = 'green' }) { return <span className={`icon-box ${tone}`}><Icon size={19} /></span> }
function CardTitle({ title, subtitle, children }) { return <div className="card-title"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{children}</div> }
function Metric({ icon, label, value, unit, footer, tone }) {
  return <section className="card metric"><div className="metric-top"><span>{label}</span><IconBox icon={icon} tone={tone} /></div><div className="metric-value">{value}<span>{unit}</span></div>{footer && <div className="metric-foot">{footer}</div>}</section>
}
function BusyButton({ busy, children, ...props }) { return <button {...props} disabled={busy || props.disabled}>{busy ? <><Loader2 size={15} className="spin" /> Working…</> : children}</button> }
function Toggle({ checked, onChange, label }) { return <label className="toggle-row"><span>{label}</span><button type="button" className={`toggle ${checked ? 'on' : ''}`} onClick={() => onChange(!checked)} aria-pressed={checked}><span /></button></label> }

function DecisionPriorityPicker({ value, onChange }) {
  const descriptions = {
    balanced: 'Balance cost, emissions, battery use, and reliability',
    lowest_cost: 'Prefer the lowest estimated operating cost',
    lowest_co2: 'Prefer the lowest estimated emissions',
    maximum_reliability: 'Keep the largest safety margin for supply',
  }
  return <div className="priority-picker" role="radiogroup" aria-label="Decision priority">
    {MODES.map(([modeValue, label]) => <button
      key={modeValue}
      type="button"
      role="radio"
      aria-checked={value === modeValue}
      className={`priority-option ${value === modeValue ? 'active' : ''}`}
      onClick={() => onChange(modeValue)}
    >
      <span>{label}</span>
      <small>{descriptions[modeValue]}</small>
    </button>)}
  </div>
}

function PlantScene() {
  return <svg className="plant-scene" viewBox="0 0 470 230" aria-hidden="true"><ellipse cx="269" cy="192" rx="173" ry="23" fill="#0e513c" opacity=".1" /><path d="M91 119 263 47 449 126 274 211Z" fill="#8eae7c" /><path d="M91 110 263 38 449 117 274 199Z" fill="#d6e8b7" /><g fill="#2e6170">{[0,1,2].map(r=>[0,1,2].map(c=><rect key={`${r}-${c}`} x={150+c*42+r*22} y={92+c*14-r*12} width="30" height="15" transform="skewY(20)"/>))}</g>{[[328,69],[383,98],[268,42]].map(([x,y])=><g key={x} transform={`translate(${x} ${y})`} stroke="#fffdf1" strokeWidth="4"><path d="M0 35V-30"/><path d="M0-30 0-65M0-30 28-12M0-30-28-12"/></g>)}</svg>
}

function WaitCard({ title, text, icon: Icon }) {
  return <section className="card"><CardTitle title={title} subtitle={text}><Icon size={20} className="muted" /></CardTitle><div className="empty-state"><span className="icon-box"><Icon size={25} /></span><h3>No forecast is available yet.</h3><p>Choose a valid date and time, then generate the 72-hour forecast.</p></div></section>
}

function DecisionResult({ result }) {
  if (!result) return null
  const d = result.decision || result
  const impact = result.impact || {}
  return <section className="card recommendation-card"><CardTitle title="Recommended operating plan"><div className="flex gap-2"><Badge tone={d.condition === 'SHORTAGE' ? 'amber' : 'green'}>{friendlyCondition(d.condition)}</Badge><Badge tone="neutral">{friendlyMode(d.optimization_mode)}</Badge></div></CardTitle>
    <div className="summary-numbers"><div><span>Recommendation confidence</span><strong>{num(d.confidence_pct)}<small>%</small></strong></div><div><span>Priority level</span><strong>{String(d.urgency || '').toLowerCase()}</strong></div><div><span>Battery reserve</span><strong>{num(d.dynamic_reserve_soc_pct)}<small>%</small></strong></div></div>
    <div className="action-grid">{(d.recommended_actions || []).map((a,i)=><article key={`${a.action}-${i}`}><IconBox icon={Zap}/><span className="action-number">{String(i+1).padStart(2,'0')}</span><h3>{friendlyAction(a.action)}</h3><p>{mw(a.power_kw)}</p><p>{a.reason}</p></article>)}</div>
    {d.explanation?.length ? <div className="info-banner"><CircleHelp size={18}/><div><b>Why this recommendation?</b><p>{d.explanation.join(' ')}</p></div></div> : null}
    <div className="summary-numbers"><div><span>Estimated operating cost</span><strong>{money(impact.net_operational_cost_inr || 0)}</strong></div><div><span>Backup emissions</span><strong>{num(impact.backup_co2_kg || impact.backup_co2_emissions_kg || 0)}<small> kg CO₂</small></strong></div><div><span>Energy demand not served</span><strong>{num(impact.unserved_energy_mwh || 0,4)}<small> MWh</small></strong></div></div>
  </section>
}

function emptyScenario(index) { return { id:`${Date.now()}-${index}`, name:`Scenario ${index}`, demandPct:'', socPct:'', generationMW:'', backup:'same', grid:'same' } }

function downloadBlob(content, type, filename) {
  const blob = content instanceof Blob ? content : new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function csvEscape(value) {
  const text = String(value ?? '')
  return /[",\n]/.test(text) ? `"${text.replaceAll('"','""')}"` : text
}

function simplePdf(lines) {
  const clean = text => String(text).replaceAll('₹','INR ').replaceAll('CO₂','CO2').replaceAll('–','-').replaceAll('—','-').replace(/[^\x20-\x7E]/g,'?').replaceAll('\\','\\\\').replaceAll('(','\\(').replaceAll(')','\\)')
  const pages = []
  for (let i=0;i<lines.length;i+=44) pages.push(lines.slice(i,i+44))
  const objects = []
  const pageIds = pages.map((_,i)=>4+i*2)
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>'
  objects[2] = `<< /Type /Pages /Kids [${pageIds.map(id=>`${id} 0 R`).join(' ')}] /Count ${pages.length} >>`
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'
  pages.forEach((pageLines,i)=>{
    const pageId = 4+i*2, contentId = pageId+1
    objects[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`
    const body = `BT\n/F1 9 Tf\n40 755 Td\n${pageLines.map((line,j)=>`${j===0?'':'0 -16 Td\n'}(${clean(line)}) Tj`).join('\n')}\nET`
    objects[contentId] = `<< /Length ${body.length} >>\nstream\n${body}\nendstream`
  })
  let pdf = '%PDF-1.4\n'
  const offsets = [0]
  for (let id=1; id<objects.length; id++) {
    offsets[id] = pdf.length
    pdf += `${id} 0 obj\n${objects[id]}\nendobj\n`
  }
  const xref = pdf.length
  pdf += `xref\n0 ${objects.length}\n0000000000 65535 f \n`
  for (let id=1;id<objects.length;id++) pdf += `${String(offsets[id]).padStart(10,'0')} 00000 n \n`
  pdf += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`
  return new Blob([pdf], { type:'application/pdf' })
}

export default function App() {
  const [page, setPage] = useState('Overview')
  const [sidebar, setSidebar] = useState(false)
  const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const [exportOpen, setExportOpen] = useState(false)
  const [plants, setPlants] = useState([])
  const [plantId, setPlantId] = useState(null)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [generationMW, setGenerationMW] = useState('')
  const [forecastData, setForecastData] = useState(null)
  const [forecastStart, setForecastStart] = useState('')
  const [forecastBusy, setForecastBusy] = useState(false)
  const [autoDaylight, setAutoDaylight] = useState(true)
  const [defaultExportFormat, setDefaultExportFormat] = useState('pdf')

  const [riskResult, setRiskResult] = useState(null)
  const [riskBusy, setRiskBusy] = useState(false)
  const [shapResult, setShapResult] = useState(null)
  const [shapBusy, setShapBusy] = useState(false)
  const [uncertaintyPct, setUncertaintyPct] = useState('')
  const [mode, setMode] = useState('balanced')
  const [decisionResult, setDecisionResult] = useState(null)
  const [decisionBusy, setDecisionBusy] = useState(false)
  const [modeResult, setModeResult] = useState(null)
  const [modeBusy, setModeBusy] = useState(false)
  const [whatIfDemandPct, setWhatIfDemandPct] = useState('')
  const [whatIfSoc, setWhatIfSoc] = useState('')
  const [whatIfBackup, setWhatIfBackup] = useState(null)
  const [whatIfGrid, setWhatIfGrid] = useState(null)
  const [whatIfResult, setWhatIfResult] = useState(null)
  const [whatIfBusy, setWhatIfBusy] = useState(false)
  const [scenarios, setScenarios] = useState([emptyScenario(1)])
  const [scenarioResult, setScenarioResult] = useState(null)
  const [scenarioBusy, setScenarioBusy] = useState(false)
  const [horizonResult, setHorizonResult] = useState(null)
  const [horizonBusy, setHorizonBusy] = useState(false)
  const [labError, setLabError] = useState('')

  useEffect(()=>{
    getPlants().then(r=>{
      const list = r.plants || []
      setPlants(list)
      if (list.length) setPlantId(list[0].plant_id)
    }).catch(e=>setError(e.message))
  },[])

  const meta = useMemo(()=>plants.find(p=>Number(p.plant_id)===Number(plantId)),[plants,plantId])

  const chooseDecisionPoint = fc => {
    if (!fc?.points?.length) return null
    if (!autoDaylight) return fc.points[0]
    return fc.points.find(p=>Number(p.p50_kw)>0 && p.flag!=='night/low-sun') || fc.points[0]
  }

  const applyForecast = fc => {
    setForecastData(fc)
    const point = chooseDecisionPoint(fc)
    if (point) {
      setGenerationMW(String(Number(point.p50_kw)/1000))
      setUncertaintyPct(String(point.forecast_uncertainty_pct))
    }
  }

  useEffect(()=>{
    if (!plantId || !meta) return
    const start = datetimeLocal(meta.latest_historical_origin || meta.last_timestamp || meta.latest_forecast_origin)
    setForecastStart(start)
    setLoading(true)
    setForecastBusy(true)
    setError('')
    Promise.all([getPlantOperations(plantId,72), getPlantForecast(plantId,72,start)])
      .then(([ops,fc])=>{ setData(ops); applyForecast(fc) })
      .catch(e=>setError(e.message))
      .finally(()=>{ setLoading(false); setForecastBusy(false) })
  },[plantId,meta?.latest_historical_origin,meta?.latest_forecast_origin])

  useEffect(()=>{
    if (!forecastData) return
    const point = chooseDecisionPoint(forecastData)
    if (point) {
      setGenerationMW(String(Number(point.p50_kw)/1000))
      setUncertaintyPct(String(point.forecast_uncertainty_pct))
    }
  },[autoDaylight])

  const rows = data?.rows || []
  const current = rows.at(-1)
  const decisionPoint = useMemo(()=>chooseDecisionPoint(forecastData),[forecastData,autoDaylight])
  const upstreamReady = generationMW!=='' && uncertaintyPct!=='' && Number(generationMW)>=0 && Number(uncertaintyPct)>=0

  const baseInputs = useMemo(()=> current && upstreamReady ? {
    predicted_generation_kw:Number(generationMW)*1000,
    demand_kw:Number(current.demand_kw), battery_soc_pct:Number(current.battery_soc_pct), battery_capacity_kwh:Number(current.battery_capacity_kwh),
    max_charge_rate_kw:Number(current.max_charge_rate_kw), max_discharge_rate_kw:Number(current.max_discharge_rate_kw),
    backup_available:Boolean(current.backup_available), backup_capacity_kw:Number(current.backup_capacity_kw),
    grid_export_available:Boolean(current.grid_export_available), grid_export_limit_kw:Number(current.grid_export_limit_kw),
    risk_score:null, forecast_uncertainty_pct:Number(uncertaintyPct),
    electricity_price_inr_per_mwh:Number(current.electricity_price_inr_per_mwh), backup_cost_inr_per_mwh:Number(current.backup_cost_inr_per_mwh),
    backup_co2_kg_per_mwh:Number(current.backup_co2_kg_per_mwh), optimization_mode:mode
  }:null,[current,upstreamReady,generationMW,uncertaintyPct,mode])

  const riskInputs = useMemo(()=> current && upstreamReady ? {
    predicted_generation_kw:Number(generationMW)*1000,
    demand_kw:Number(current.demand_kw), battery_soc_pct:Number(current.battery_soc_pct),
    forecast_uncertainty_pct:Number(uncertaintyPct), backup_available:Boolean(current.backup_available),
    backup_capacity_kw:Number(current.backup_capacity_kw), grid_export_available:Boolean(current.grid_export_available),
    grid_export_limit_kw:Number(current.grid_export_limit_kw)
  }:null,[current,upstreamReady,generationMW,uncertaintyPct])

  const execute = async (fn,setBusy,setResult)=>{ setLabError(''); setBusy(true); try{setResult(await fn())}catch(e){setLabError(e.message)}finally{setBusy(false)} }
  const runRisk = ()=> riskInputs && execute(()=>runRiskAssessment(riskInputs),setRiskBusy,setRiskResult)
  const runShap = ()=> plantId && decisionPoint && execute(()=>getForecastExplanation(plantId,decisionPoint.horizon,8,forecastStart),setShapBusy,setShapResult)
  useEffect(()=>{ if(riskInputs){ runRiskAssessment(riskInputs).then(setRiskResult).catch(()=>{}) } },[riskInputs])
  const runBase = ()=> baseInputs && execute(()=>runDecision(baseInputs),setDecisionBusy,setDecisionResult)
  const runModes = ()=> baseInputs && execute(()=>compareModes(baseInputs),setModeBusy,setModeResult)
  const runWI = ()=>{ if(!baseInputs)return; const c={}; if(whatIfDemandPct!=='')c.demand_kw=current.demand_kw*(1+Number(whatIfDemandPct)/100); if(whatIfSoc!=='')c.battery_soc_pct=Number(whatIfSoc); if(whatIfBackup!==null)c.backup_available=whatIfBackup; if(whatIfGrid!==null)c.grid_export_available=whatIfGrid; if(!Object.keys(c).length){setLabError('Change at least one What-If input.');return} execute(()=>runWhatIf(baseInputs,c),setWhatIfBusy,setWhatIfResult) }
  const updateScenario=(id,f,v)=>setScenarios(s=>s.map(x=>x.id===id?{...x,[f]:v}:x))
  const runScenarioCompare=()=>{ if(!baseInputs)return; const payload={}; scenarios.forEach(s=>{const c={}; if(s.demandPct!=='')c.demand_kw=current.demand_kw*(1+Number(s.demandPct)/100); if(s.socPct!=='')c.battery_soc_pct=Number(s.socPct); if(s.generationMW!=='')c.predicted_generation_kw=Number(s.generationMW)*1000; if(s.backup!=='same')c.backup_available=s.backup==='true'; if(s.grid!=='same')c.grid_export_available=s.grid==='true'; if(Object.keys(c).length)payload[s.name||'Scenario']=c}); if(!Object.keys(payload).length){setLabError('Configure at least one scenario change.');return} execute(()=>compareMultipleScenarios(baseInputs,payload),setScenarioBusy,setScenarioResult) }

  const horizonValues=useMemo(()=>forecastData?.points?.slice(0,72).map(p=>Number(p.p50_kw)/1000)||[],[forecastData])
  const horizonUncertainty=useMemo(()=>{const pts=forecastData?.points?.slice(0,72)||[]; return pts.length?pts.reduce((a,p)=>a+Number(p.forecast_uncertainty_pct||0),0)/pts.length:Number(uncertaintyPct||0)},[forecastData,uncertaintyPct])
  const run72=()=>{ if(horizonValues.length!==72){setLabError('A complete 72-hour forecast is required before running the simulation.');return} execute(()=>runHorizonPlan({plant_id:Number(plantId), predicted_generation_kw:horizonValues.map(v=>v*1000), forecast_uncertainty_pct:Number(horizonUncertainty), optimization_mode:mode}),setHorizonBusy,setHorizonResult) }

  const navigate = p=>{setPage(p); setSidebar(false); setWorkspaceOpen(false); window.scrollTo({top:0,behavior:'smooth'})}

  const runSelectedForecast = async () => {
    if (!plantId || !forecastStart) return
    setForecastBusy(true); setLabError(''); setShapResult(null); setDecisionResult(null); setHorizonResult(null)
    try { applyForecast(await getPlantForecast(plantId,72,forecastStart)) }
    catch (e) { setLabError(e.message) }
    finally { setForecastBusy(false) }
  }

  const resetInteractiveInputs = () => {
    setMode('balanced')
    setAutoDaylight(true)
    setWhatIfDemandPct(''); setWhatIfSoc(''); setWhatIfBackup(null); setWhatIfGrid(null)
    setScenarios([emptyScenario(1)]); setWhatIfResult(null); setScenarioResult(null); setDecisionResult(null); setModeResult(null); setHorizonResult(null)
  }

  const exportRows = useMemo(()=> (forecastData?.points || []).slice(0,72).map((p,i)=>({
    'Forecast time': formatDateTime(p.target_time),
    'Hour ahead': i+1,
    'Lower estimate (MW)': Number(p.p10_kw)/1000,
    'Expected generation (MW)': Number(p.p50_kw)/1000,
    'Upper estimate (MW)': Number(p.p90_kw)/1000,
    'Forecast uncertainty (%)': Number(p.forecast_uncertainty_pct),
    'Generation outlook': friendlyFlag(p.flag),
  })),[forecastData])

  const exportData = format => {
    setExportOpen(false)
    if (!exportRows.length) { setLabError('Generate a forecast before exporting.'); return }
    const start = String(forecastData.points[0]?.origin_time || forecastStart).slice(0,16).replaceAll(':','-')
    const base = `${safeName(data?.plant?.plant_label)}_72-hour_forecast_${start}`
    const headers = Object.keys(exportRows[0])
    if (format === 'json') {
      const payload = {
        plant: data?.plant?.plant_label,
        forecast_start: forecastData.points[0]?.origin_time,
        forecast_length_hours: 72,
        hourly_forecast: exportRows,
      }
      downloadBlob(JSON.stringify(payload,null,2),'application/json',`${base}.json`)
    } else if (format === 'csv') {
      const csv = [headers.join(','), ...exportRows.map(r=>headers.map(h=>csvEscape(r[h])).join(','))].join('\n')
      downloadBlob(csv,'text/csv;charset=utf-8',`${base}.csv`)
    } else if (format === 'excel') {
      const table = `<table><thead><tr>${headers.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${exportRows.map(r=>`<tr>${headers.map(h=>`<td>${r[h]}</td>`).join('')}</tr>`).join('')}</tbody></table>`
      const html = `<html><head><meta charset="utf-8"></head><body><h2>72-hour renewable generation forecast</h2>${table}</body></html>`
      downloadBlob(html,'application/vnd.ms-excel',`${base}.xls`)
    } else {
      const lines = [
        'Renewable Energy Copilot - 72-hour Forecast',
        `Plant: ${data?.plant?.plant_label || plantId}`,
        `Forecast starting point: ${formatDateTime(forecastData.points[0]?.origin_time)}`,
        '',
        'Time | Lower MW | Expected MW | Upper MW | Uncertainty % | Outlook',
        ...exportRows.map(r=>`${r['Forecast time']} | ${Number(r['Lower estimate (MW)']).toFixed(2)} | ${Number(r['Expected generation (MW)']).toFixed(2)} | ${Number(r['Upper estimate (MW)']).toFixed(2)} | ${Number(r['Forecast uncertainty (%)']).toFixed(2)} | ${r['Generation outlook']}`)
      ]
      downloadBlob(simplePdf(lines),'application/pdf',`${base}.pdf`)
    }
  }

  if(error) return <div className="center"><h2>Project data could not be loaded</h2><p>{error}</p></div>
  if(!plantId||loading||!data||!current) return <div className="center"><RefreshCw className="spin"/><p>Loading your energy workspace…</p></div>

  const fieldInputs = <div className="settings-form">
    <label>Expected generation (MW)<input type="number" value={generationMW} readOnly/><small>Forecast value used for the selected operating decision</small></label>
    <label>Forecast uncertainty (%)<input type="number" value={uncertaintyPct} readOnly/><small>How wide the likely generation range is</small></label>
    <div className="decision-priority-field"><span className="field-label">Decision priority</span><DecisionPriorityPicker value={mode} onChange={setMode}/></div>
  </div>

  return <div className="app-shell min-h-screen bg-canvas font-sans text-ink antialiased">
    <a className="skip-link" href="#main-content">Skip to content</a>
    {sidebar&&<div className="sidebar-overlay" onClick={()=>setSidebar(false)}/>}<aside className={`sidebar ${sidebar?'open':''}`}>
      <a className="brand" href="#" onClick={e=>{e.preventDefault();navigate('Overview')}}><span className="brand-mark"><Leaf size={25}/></span><span>renewable<span>ENERGY COPILOT</span></span></a>
      <button className="mobile-close icon-button" onClick={()=>setSidebar(false)}><PanelLeftClose size={20}/></button>
      <div className="workspace-switcher">
        <button className="workspace-label workspace-toggle" onClick={()=>setWorkspaceOpen(v=>!v)} aria-expanded={workspaceOpen}><span className="workspace-icon">E</span><div>Energy workspace<small>Planning and operations</small></div><ChevronDown size={14} className={workspaceOpen?'rotate':''}/></button>
        {workspaceOpen&&<div className="workspace-menu"><button onClick={()=>navigate('Overview')}>Overview</button><button onClick={()=>navigate('Generation forecast')}>Forecasting</button><button onClick={()=>navigate('Risk & decisions')}>Decisions</button><button onClick={()=>navigate('What-If simulator')}>Simulations</button></div>}
      </div>
      <nav>{navigation.map(({name,icon:Icon,group})=><div key={name}>{group&&<div className="nav-group">{group}</div>}<button className={`nav-item ${page===name?'active':''}`} onClick={()=>navigate(name)}><Icon size={18}/><span>{name}</span>{name==='What-If simulator'&&<span className="nav-new">LIVE</span>}</button></div>)}</nav>
      <div className="sidebar-bottom"><button className={`nav-item ${page==='Settings'?'active':''}`} onClick={()=>navigate('Settings')}><Settings size={18}/>Settings</button><div className="sidebar-user"><span className="avatar">U</span><div><b>Operator</b><small>Energy planning</small></div></div></div>
    </aside>

    <div className="workspace"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-menu" onClick={()=>setSidebar(true)}><Menu size={20}/></button><span>Workspace</span><ChevronRight size={13}/><b>{page}</b></div><div className="topbar-actions"><span className="top-avatar subtle-avatar" title="Profile">U</span></div></header>

    <main id="main-content" tabIndex={-1}>
      <div className="page-heading"><div><div className="page-eyebrow">{page.toUpperCase()}</div><h1>{pageInfo[page][0]}</h1><p>{pageInfo[page][1]}</p></div><div className="heading-actions export-wrap"><button className="secondary" onClick={()=>setExportOpen(v=>!v)}><Download size={15}/>Export report<ChevronDown size={13}/></button>{exportOpen&&<div className="export-menu"><button onClick={()=>exportData('pdf')}>PDF report</button><button onClick={()=>exportData('excel')}>Excel spreadsheet</button><button onClick={()=>exportData('csv')}>CSV file</button><button onClick={()=>exportData('json')}>JSON data</button></div>}</div></div>

      <div className="context-bar"><label className="site-select"><MapPin size={15}/><select value={plantId} onChange={e=>setPlantId(Number(e.target.value))}>{plants.map(p=><option value={p.plant_id} key={p.plant_id}>{p.plant_label}</option>)}</select><ChevronDown size={13}/></label><span className="context-divider"/><span className="site-location">Plant ID: {plantId}</span></div>

      {labError&&<div className="info-banner error-banner"><CircleHelp size={18}/><p>{labError}</p></div>}

      {page==='Overview'&&<><section className="welcome-banner"><div className="banner-copy"><div className="eyebrow"><span/> ENERGY PLANNING</div><h2>More foresight.<br/>Better energy decisions.</h2><p>See current operating conditions, forecast generation, understand risk, and choose practical actions.</p><button onClick={()=>navigate('Risk & decisions')}>Open decisions <ArrowRight size={16}/></button></div><PlantScene/><div className="banner-tag"><span className="tiny-dot"/> Live workspace</div></section><div className="metric-grid"><Metric icon={Activity} label="Demand" value={num(current.demand_kw/1000,2)} unit="MW"/><Metric icon={BatteryCharging} tone="amber" label="Battery level" value={num(current.battery_soc_pct,1)} unit="%" footer={`${num(current.battery_capacity_kwh/1000,2)} MWh storage capacity`}/><Metric icon={Zap} label="Backup capacity" value={num(current.backup_capacity_kw/1000,2)} unit="MW" footer={current.backup_available?'Available':'Unavailable'}/><Metric icon={ShieldCheck} label="Grid export limit" value={num(current.grid_export_limit_kw/1000,2)} unit="MW" footer={current.grid_export_available?'Export available':'Export unavailable'}/></div><div className="overview-bottom"><section className="card recommendation-card"><CardTitle title="Current operating limits"/><div className="summary-numbers"><div><span>Maximum battery charging</span><strong>{mw(current.max_charge_rate_kw)}</strong></div><div><span>Maximum battery discharge</span><strong>{mw(current.max_discharge_rate_kw)}</strong></div><div><span>Electricity price</span><strong>{money(current.electricity_price_inr_per_mwh)}<small>/MWh</small></strong></div></div><div className="info-banner"><ShieldCheck size={18}/><div><b>Ready for planning</b><p>Use the forecast, risk, and simulation pages to explore upcoming conditions and possible responses.</p></div></div></section><section className="simulator-promo"><span className="promo-icon"><FlaskConical size={22}/></span><h2>What if things change?</h2><p>Test demand, storage, backup, and grid-support changes.</p><button onClick={()=>navigate('What-If simulator')}>Run a simulation <ArrowRight size={15}/></button><div className="promo-circles"/></section></div></>}

      {page==='Generation forecast'&&<><section className="card forecast-picker"><CardTitle title="Choose when the 72-hour forecast should begin" subtitle="Select a historical or upcoming date and time."/><div className="forecast-picker-row"><label>Forecast starting point<input type="datetime-local" step="3600" value={forecastStart} min={datetimeLocal(meta?.earliest_forecast_origin)} max={datetimeLocal(meta?.latest_forecast_origin)} onChange={e=>setForecastStart(e.target.value)}/></label><BusyButton className="primary" busy={forecastBusy} onClick={runSelectedForecast}><TrendingUp size={15}/>Generate 72-hour forecast</BusyButton></div><div className="forecast-date-help"><span><b>Available through:</b> {formatDateTime(meta?.latest_forecast_origin)}</span><span><b>Latest measured plant data:</b> {formatDateTime(meta?.latest_historical_origin || meta?.last_timestamp)}</span></div><p className="footnote">For dates after the latest measured plant record, the forecast uses the latest available plant state together with historical operating patterns.</p></section>{forecastBusy?<section className="card"><div className="center compact-center"><Loader2 className="spin"/><p>Generating 72-hour forecast…</p></div></section>:forecastData?.points?.length?<><div className="metric-grid"><Metric icon={TrendingUp} label="Expected generation next hour" value={num(forecastData.points[0].p50_kw/1000,2)} unit="MW" footer={`Likely range ${num(forecastData.points[0].p10_kw/1000,2)}–${num(forecastData.points[0].p90_kw/1000,2)} MW`}/><Metric icon={Activity} label="Forecast uncertainty" value={num(forecastData.points[0].forecast_uncertainty_pct,2)} unit="%" footer="Lower means the expected range is tighter"/><Metric icon={Zap} label="Plant capacity" value={num(forecastData.plant_reference_capacity_kw/1000,2)} unit="MW"/><Metric icon={TrendingUp} label="Forecast length" value="72" unit="hours" footer={`${formatDateTime(forecastData.points[0].target_time)} to ${formatDateTime(forecastData.points.at(-1)?.target_time)}`}/></div><section className="card"><CardTitle title="72-hour generation forecast" subtitle="Expected generation with a lower and upper likely estimate."/><div className="table-wrap"><table><thead><tr><th>Forecast time</th><th>Lower estimate</th><th>Expected generation</th><th>Upper estimate</th><th>Uncertainty</th><th>Generation outlook</th></tr></thead><tbody>{forecastData.points.slice(0,72).map((r,i)=><tr key={i}><td>{formatDateTime(r.target_time)}</td><td>{mw(r.p10_kw)}</td><td><b>{mw(r.p50_kw)}</b></td><td>{mw(r.p90_kw)}</td><td>{num(r.forecast_uncertainty_pct,2)}%</td><td>{friendlyFlag(r.flag)}</td></tr>)}</tbody></table></div></section></>:<WaitCard title="Generation forecast unavailable" text="Choose a valid date and time to create a forecast." icon={TrendingUp}/>}</>}

      {page==='AI insights'&&<><section className="card insights-card"><CardTitle title="Forecast insights" subtitle="Review the operating risk and the strongest factors influencing expected generation."/><div className="two-column insights-input-grid"><div>{fieldInputs}</div><div className="forecast-snapshot"><h3>Selected forecast snapshot</h3><div className="snapshot-grid"><div><span>Forecast time</span><strong>{formatDateTime(decisionPoint?.target_time)}</strong></div><div><span>Expected generation</span><strong>{decisionPoint ? mw(decisionPoint.p50_kw) : '—'}</strong></div><div><span>Likely generation range</span><strong>{decisionPoint ? `${mw(decisionPoint.p10_kw)} – ${mw(decisionPoint.p90_kw)}` : '—'}</strong></div><div><span>Forecast uncertainty</span><strong>{decisionPoint ? `${num(decisionPoint.forecast_uncertainty_pct,2)}%` : '—'}</strong></div></div></div></div><div className="flex gap-2 insight-actions"><BusyButton className="primary" busy={riskBusy} disabled={!upstreamReady} onClick={runRisk}><ShieldCheck size={15}/>Check operating risk</BusyButton><BusyButton className="secondary" busy={shapBusy} disabled={!decisionPoint} onClick={runShap}><Sparkles size={15}/>Explain this forecast</BusyButton></div></section>{shapResult&&<section className="card insights-card"><CardTitle title="What is influencing this forecast?" subtitle={`For ${formatDateTime(shapResult.target_time)} · Expected generation ${mw(shapResult.p50_kw)}`}/><div className="table-wrap insight-table"><table><thead><tr><th>Influencing factor</th><th>Current value</th><th>Effect on generation</th><th>What this means</th></tr></thead><tbody>{(shapResult.top_features||[]).map((r,i)=><tr key={i}><td><b>{friendlyFeature(r.feature)}</b></td><td>{friendlyFeatureValue(r.feature,r.value)}</td><td>{friendlyImpact(r.shap_value_kw)}</td><td>{friendlyDirection(r.shap_value_kw)}</td></tr>)}</tbody></table></div></section>}{riskResult&&<><div className="metric-grid insights-metrics"><Metric icon={ShieldCheck} label="Overall risk" value={num(riskResult.risk_score,2)} unit="/100" footer={String(riskResult.risk_level||'').toLowerCase()}/><Metric icon={Activity} label="Operating condition" value={friendlyCondition(riskResult.condition)} footer={`Generation-demand gap ${mw(riskResult.energy_gap_kw)}`}/><Metric icon={BatteryCharging} label="Battery-related risk" value={num(riskResult.risk_components?.battery_risk,2)} unit="/100" footer={`Battery level ${num(riskResult.battery_soc_pct)}%`}/><Metric icon={TrendingUp} label="Forecast uncertainty risk" value={num(riskResult.risk_components?.uncertainty_risk,2)} unit="/100" footer={`${num(riskResult.uncertainty_pct)}% forecast uncertainty`}/></div><section className="card insights-card"><CardTitle title="Why is the risk at this level?"/><div className="summary-numbers"><div><span>Supply-demand risk</span><strong>{num(riskResult.risk_components?.energy_risk,2)}</strong></div><div><span>Battery risk</span><strong>{num(riskResult.risk_components?.battery_risk,2)}</strong></div><div><span>Forecast uncertainty</span><strong>{num(riskResult.risk_components?.uncertainty_risk,2)}</strong></div><div><span>Backup readiness</span><strong>{num(riskResult.risk_components?.backup_risk,2)}</strong></div><div><span>Grid export constraint</span><strong>{num(riskResult.risk_components?.grid_risk,2)}</strong></div></div><div className="info-banner contained-info"><CircleHelp size={18}/><div><b>Main reasons</b><p>{(riskResult.risk_reasons||[]).join(' • ')}</p></div></div></section></>}</>}

      {page==='Risk & decisions'&&<><section className="card"><CardTitle title="Decision inputs" subtitle="These values are used to choose the most suitable operating action."/><div className="two-column"><div>{fieldInputs}</div><div className="info-banner"><CircleHelp size={19}/><div><b>How this page works</b><p>The selected forecast is compared with demand, battery level, backup capacity, and grid limits before a recommendation is produced.</p></div></div></div><BusyButton className="primary" busy={decisionBusy} disabled={!upstreamReady} onClick={runBase}><Zap size={15}/>Get recommendation</BusyButton></section><DecisionResult result={decisionResult}/><section className="card"><CardTitle title="Compare decision priorities" subtitle="See how the recommendation changes when cost, emissions, reliability, or a balanced approach is prioritized."/><BusyButton className="secondary" busy={modeBusy} disabled={!upstreamReady} onClick={runModes}>Compare priorities</BusyButton>{modeResult?.mode_results&&<div className="table-wrap"><table><thead><tr><th>Priority</th><th>Recommended actions</th><th>Battery reserve</th><th>Estimated cost</th><th>Emissions</th><th>Unserved energy</th></tr></thead><tbody>{modeResult.mode_results.map(r=><tr key={r.mode}><td><b>{friendlyMode(r.mode)}</b></td><td>{r.actions.map(friendlyAction).join(', ')||'No special action'}</td><td>{num(r.battery_reserve_pct,1)}%</td><td>{money(r.net_cost_inr)}</td><td>{num(r.co2_kg)} kg CO₂</td><td>{num(r.unserved_mwh,4)} MWh</td></tr>)}</tbody></table></div>}</section></>}

      {page==='What-If simulator'&&<><section className="card"><CardTitle title="What-If simulator" subtitle="Change only the conditions you want to test."/><div className="two-column"><div>{fieldInputs}</div><div className="settings-form"><label>Demand adjustment (%)<input type="number" value={whatIfDemandPct} onChange={e=>setWhatIfDemandPct(e.target.value)} placeholder="e.g. 30"/></label><label>Battery level (%)<input type="number" min="0" max="100" value={whatIfSoc} onChange={e=>setWhatIfSoc(e.target.value)} placeholder="leave blank = unchanged"/></label><Toggle label="Backup power available" checked={whatIfBackup ?? Boolean(current.backup_available)} onChange={setWhatIfBackup}/><Toggle label="Grid export available" checked={whatIfGrid ?? Boolean(current.grid_export_available)} onChange={setWhatIfGrid}/></div></div><BusyButton className="primary" busy={whatIfBusy} disabled={!upstreamReady} onClick={runWI}><FlaskConical size={15}/>Compare What-If scenario</BusyButton></section>{whatIfResult&&<div className="two-column"><DecisionResult result={whatIfResult.base}/><DecisionResult result={whatIfResult.what_if}/></div>}{whatIfResult?.comparison&&<section className="card"><CardTitle title="Before and after"/><div className="summary-numbers"><div><span>Current actions</span><strong>{whatIfResult.comparison.base_actions.map(friendlyAction).join(', ')||'None'}</strong></div><div><span>What-If actions</span><strong>{whatIfResult.comparison.what_if_actions.map(friendlyAction).join(', ')||'None'}</strong></div><div><span>Cost change</span><strong>{money(whatIfResult.comparison.cost_change_inr)}</strong></div></div></section>}</>}

      {page==='Digital twin'&&<><section className="card twin-card"><CardTitle title="72-hour operating simulation" subtitle="Follow battery level and operating actions hour by hour across the full forecast period."/><div className="two-column"><div>{fieldInputs}</div><div className="settings-form"><label>Forecast hours available<input value={`${horizonValues.length}/72`} readOnly/></label><label>Average forecast uncertainty<input value={`${num(horizonUncertainty,2)}%`} readOnly/></label><p className="footnote">All 72 expected-generation values are used in sequence.</p></div></div><BusyButton className="primary" busy={horizonBusy} onClick={run72}><Cable size={15}/>Run 72-hour simulation</BusyButton></section>{horizonResult&&<><div className="metric-grid"><Metric icon={BatteryCharging} label="Ending battery level" value={num(horizonResult.summary.ending_battery_soc_pct)} unit="%" footer="After all 72 hourly decisions"/><Metric icon={Activity} label="Estimated operating cost" value={money(horizonResult.summary.total_net_operational_cost_inr)} footer="72-hour total"/><Metric icon={Leaf} label="Backup emissions" value={num(horizonResult.summary.total_backup_co2_kg)} unit="kg CO₂" footer="72-hour total"/><Metric icon={ShieldCheck} label="Energy demand not served" value={num(horizonResult.summary.total_unserved_energy_mwh,4)} unit="MWh" footer="72-hour total"/></div><section className="card"><CardTitle title="Hourly operating plan"/><div className="table-wrap"><table><thead><tr><th>Time</th><th>Expected generation</th><th>Demand</th><th>Battery level after action</th><th>Condition</th><th>Action</th></tr></thead><tbody>{horizonResult.plan.map((r,i)=><tr key={i}><td>{formatDateTime(r.timestamp_hour)}</td><td>{mw(r.predicted_generation_kw)}</td><td>{mw(r.demand_kw)}</td><td>{num(r.soc_after_action_pct)}%</td><td>{friendlyCondition(r.condition)}</td><td>{String(r.actions||'').split(',').map(x=>friendlyAction(x.trim())).join(', ')}</td></tr>)}</tbody></table></div></section></>}</>}

      {page==='Impact & reports'&&<><section className="card"><CardTitle title="Compare multiple scenarios" subtitle="Test several changed operating states against the same starting conditions."/><div>{fieldInputs}</div>{scenarios.map(s=><div className="scenario-row" key={s.id}><input value={s.name} onChange={e=>updateScenario(s.id,'name',e.target.value)} placeholder="Scenario name"/><input type="number" value={s.demandPct} onChange={e=>updateScenario(s.id,'demandPct',e.target.value)} placeholder="Demand %"/><input type="number" value={s.socPct} onChange={e=>updateScenario(s.id,'socPct',e.target.value)} placeholder="Battery %"/><input type="number" value={s.generationMW} onChange={e=>updateScenario(s.id,'generationMW',e.target.value)} placeholder="Generation MW"/><select value={s.backup} onChange={e=>updateScenario(s.id,'backup',e.target.value)}><option value="same">Backup unchanged</option><option value="true">Backup available</option><option value="false">Backup unavailable</option></select><select value={s.grid} onChange={e=>updateScenario(s.id,'grid',e.target.value)}><option value="same">Grid unchanged</option><option value="true">Grid export available</option><option value="false">Grid export unavailable</option></select><button className="icon-button" onClick={()=>setScenarios(x=>x.filter(y=>y.id!==s.id))}><X size={15}/></button></div>)}<div className="flex gap-2"><button className="secondary" onClick={()=>setScenarios(x=>[...x,emptyScenario(x.length+1)])}>Add scenario</button><BusyButton className="primary" busy={scenarioBusy} disabled={!upstreamReady} onClick={runScenarioCompare}>Compare scenarios</BusyButton></div></section>{scenarioResult?.results&&<section className="card"><CardTitle title="Scenario results"/><div className="table-wrap"><table><thead><tr><th>Scenario</th><th>Condition</th><th>Recommended actions</th><th>Estimated cost</th><th>Emissions</th><th>Unserved energy</th></tr></thead><tbody>{scenarioResult.results.map((r,i)=><tr key={i}><td>{r.scenario_name}</td><td>{friendlyCondition(r.result.decision.condition)}</td><td>{r.result.decision.recommended_actions.map(a=>friendlyAction(a.action)).join(', ')||'None'}</td><td>{money(r.result.impact.net_operational_cost_inr)}</td><td>{num(r.result.impact.backup_co2_kg || r.result.impact.backup_co2_emissions_kg)} kg CO₂</td><td>{num(r.result.impact.unserved_energy_mwh,4)} MWh</td></tr>)}</tbody></table></div></section>}</>}

      {page==='Settings'&&<div className="settings-grid"><section className="card"><CardTitle title="Forecast preferences" subtitle="Choose how forecasts should feed into the rest of the workspace."/><div className="settings-form"><div className="decision-priority-field"><span className="field-label">Default decision priority</span><DecisionPriorityPicker value={mode} onChange={setMode}/></div><Toggle label="Use the first daylight forecast for decisions" checked={autoDaylight} onChange={setAutoDaylight}/><label>Current forecast starting point<input type="text" readOnly value={formatDateTime(forecastStart)}/></label><button className="secondary" onClick={runSelectedForecast}><RefreshCw size={15}/>Refresh 72-hour forecast</button></div></section><section className="card"><CardTitle title="Report preferences" subtitle="Choose your preferred download format."/><div className="settings-form"><label>Default export format<select value={defaultExportFormat} onChange={e=>setDefaultExportFormat(e.target.value)}><option value="pdf">PDF report</option><option value="excel">Excel spreadsheet</option><option value="csv">CSV file</option><option value="json">JSON data</option></select></label><button className="primary" onClick={()=>exportData(defaultExportFormat)}><Download size={15}/>Download current 72-hour forecast</button></div></section><section className="card"><CardTitle title="Reset workspace" subtitle="Clear temporary scenario choices without changing your forecast data."/><p className="settings-help">This resets What-If values, comparison scenarios, and decision preferences to their starting values.</p><button className="secondary" onClick={resetInteractiveInputs}>Reset temporary choices</button></section><section className="card"><CardTitle title="Selected plant"/><div className="summary-numbers"><div><span>Plant</span><strong>{data.plant.plant_label}</strong></div><div><span>Plant ID</span><strong>{plantId}</strong></div><div><span>Forecast length</span><strong>72 hours</strong></div></div></section></div>}
    </main>

    <footer className="app-footer"><span><Leaf size={13}/>Renewable Energy Copilot</span><span>Forecasting · Risk · Decisions · Simulation</span></footer>
    </div>
  </div>
}
