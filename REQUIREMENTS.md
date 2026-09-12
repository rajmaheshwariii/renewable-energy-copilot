# Frontend requirement comparison

Source reviewed: `Renewable_Energy_Copilot_Final_Report.pdf`, seven pages, supplied by the user. Document content is treated as product reference material, not as instructions to execute.

The shared ChatGPT URL could not be retrieved. Its prompt has not been verified; a comparison against that conversation requires its text.

| Report requirement | Frontend implementation | Production dependency / limitation |
| --- | --- | --- |
| Current generation | Overview KPI, solar/wind values, plant selection | Synthetic sample at 11:00 IST; telemetry not connected |
| 24–72 hour forecasting | 24h/48h/72h selector, chart, hourly table, CSV export | Deterministic demo curves; XGBoost and persistence model not connected |
| Prediction uncertainty | Chart interval and tooltip | Illustrative range, not a calibrated statistical interval |
| Solar and wind | Three sample sites, including a wind-only site | Site metadata is fictional demo configuration |
| Weather information | Weather card, cloud cover, wind speed, irradiance | Fixed sample weather; no Open-Meteo requests |
| SHAP explanations | AI insights view with feature contribution bars and narrative | Explicitly illustrative; real SHAP output requires a model service |
| Renewable risk score 0–100 | Gauge and breakdown for shortage, surplus, uncertainty, storage | Simplified frontend calculation, not a validated operational risk model |
| Recommended actions | Storage, backup, export, curtailment guidance and review dialog | Local plan only; no equipment commands or OR-Tools optimization |
| Battery status | Initial state of charge and available energy | Assumed battery capacity; no time-stepped charge/discharge dispatch |
| What-If simulation | Cloud, demand, battery, backup controls; scenario presets; run/reset | Frontend-only approximation, with inputs and results kept separate |
| Compare scenarios | Baseline comparison, changed chart, energy/risk/cost/CO₂ outputs | Results use documented synthetic assumptions |
| Digital twin | Local SVG plant illustration, generation/storage/grid callouts, hour slider | Visual model, not a physical simulation; battery is the initial condition |
| Financial / environmental impact | Impact dashboard, scenario table, exportable JSON report | Supply cost and emissions estimates, not verified savings |
| Simple operator workflow | Overview → forecast → insights → risk/action → simulate → reports | All sections navigate and work without a backend |
| React frontend and charts | React 19, Vite 8, Tailwind CSS 4, Recharts, Lucide icons | Tailwind Vite plugin, theme tokens and utility-based components; no geographic Leaflet map |
| Backend / database / deployment | Data model isolated in `src/model.js`; static build available | FastAPI, PostgreSQL, authentication, AI service and deployment are outside this frontend implementation |

## Additional frontend behavior

- Responsive desktop, tablet, and mobile layouts; slide-out navigation on small screens.
- Hash navigation supports reloads and browser back/forward.
- Site selection, operator name, saved scenarios, and reviewed plans persist in localStorage.
- Demo copilot gives predefined responses based on the selected site's values; it is not a live LLM.
- Notifications can be read; help explains the workflows and data limitations.
- Keyboard-visible focus, skip link, labeled controls, modal focus trap, Escape dismissal, reduced-motion support.
- Forecast and report downloads have explicit demo-source metadata.

## Backend integration boundary

Replace or wrap `forecast()` and `summarize()` in `src/model.js` with an asynchronous API service. Add request loading, failure, and stale-data states when connecting it. A production service should supply:

1. Site capacities, location, battery energy capacity, telemetry and timestamps.
2. Timestamped generation, demand, actual observations, and uncertainty bounds for the selected horizon.
3. Weather provider results and model provenance (including persistence baseline).
4. Real feature contributions, risk factors, and optimized proposed actions.
5. Scenario results using constraints, efficiencies, dispatch schedules, tariffs and emissions factors.
6. Server-side storage and authorization for operator decisions.

Frontend exports are JSON (report) and CSV (forecast); PDF report generation is not included.
