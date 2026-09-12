# Renewable Energy Copilot

A responsive renewable-energy operations frontend, built from the supplied project report. Includes forecasting, explainability, operational risk, action review, What-If simulation, a virtual plant, and scenario comparison.

## Run locally

```powershell
npm.cmd install
npm.cmd run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`). On systems without PowerShell script restrictions, `npm` can be used instead of `npm.cmd`.

```powershell
npm.cmd run build
npm.cmd run preview
```

The production output is in `dist/`. Hash-based navigation works on ordinary static hosting without rewrite rules.

## Validation

```powershell
npm.cmd run lint
npm.cmd test
npm.cmd run test:e2e
```

Browser tests use the installed Chrome browser via Playwright. Install Chrome if unavailable, or adapt `channel` in `playwright.config.mjs` to a browser available on your machine. Model tests check capacity/interval bounds, hourly totals, cloud sensitivity, and demand/storage effects. Browser tests cover navigation, forecast horizons, site selection, downloads, simulations, persistence, action plans, copilot, notifications, and narrow-screen overflow.

## What works

- Three demo sites with 24-, 48-, and 72-hour generation forecasts and chart series toggles.
- Hourly forecast table and CSV download.
- Risk gauge, explanation cards, and locally saved operator plans.
- Cloud, demand, battery and backup scenario inputs, presets, baseline comparisons, and saved results.
- Virtual plant with a selectable forecast hour.
- Impact dashboard and JSON report exports.
- Demo copilot, notifications, help, operator profile, and local preference persistence.
- Mobile navigation, accessible dialogs, focus states, and reduced-motion support.

## Data and scope

All operating data is synthetic. Forecasts, uncertainty, risk, explanation contributions, weather, costs and emissions are illustrative. No live AI, model, authentication, telemetry, database, optimization, or equipment control is connected. Saving a plan only stores it in this browser. Demo copilot responses are rule-based and clearly labeled.

Simulation assumptions are documented in the Impact & reports view and included in JSON exports. Battery discharge losses and charging schedules are not modeled. Cost is an estimated cost of filling the remaining supply gap, not a savings claim.

The frontend uses React, Tailwind CSS 4 through `@tailwindcss/vite`, Recharts, and Lucide. The plant illustration is a local SVG; Google Fonts are optional with sans-serif fallbacks. No image service is required.

## Tailwind styling

Tailwind is already installed and configured; no separate initialization command is needed. `src/index.css` imports Tailwind and defines the forest, brand, canvas, ink, and sage theme colors, plus sans and heading fonts. Use utilities such as `bg-brand`, `text-ink`, `font-heading`, `flex`, and responsive variants in JSX.

`src/App.css` contains reusable components in `@layer components`, with Tailwind `@apply` for shared layouts. Custom illustration, chart, and fine-grained responsive styles stay in CSS. The layer order allows JSX utilities to override component defaults. Tailwind scans `src/` so temporary tools and test artifacts are excluded.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the report comparison and integration checklist. The shared ChatGPT conversation could not be retrieved, so its contents are not included in the comparison.

## Structure

- `src/App.jsx`: workspace views, state, navigation, and interactive controls.
- `src/model.js`: demo sites, deterministic forecasts, simulation calculations, and exports.
- `src/App.css`: Tailwind component styles, responsive rules, and custom visuals.
- `src/index.css`: Tailwind entry point, theme tokens, typography, and base styles.
- `tests/`: model and browser workflow checks.

Local preferences use the `renewable-*` localStorage keys. Clearing browser site data removes them. There is no server-side account or cross-device synchronization.
