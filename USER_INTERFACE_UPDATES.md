# User-facing update summary

This build keeps the final renewable generation forecast at 72 hours and updates the dashboard for clearer everyday use.

## Main changes
- Added a date-and-time selector for starting a 72-hour forecast.
- Replaced visible P10/P50/P90 wording with Lower estimate / Expected generation / Upper estimate.
- Replaced raw technical feature names in forecast explanations with plain-language labels.
- Removed backend status text, notification icon, dataset row-count/date-range clutter, prototype wording, and technical model/method explanations from the UI.
- Simplified the profile indicator so it is visually subtle.
- Fixed the Energy workspace dropdown and added useful quick navigation.
- Replaced technical Settings content with forecast, report, and workspace preferences.
- Added export choices for PDF, Excel (.xls), CSV, and JSON with descriptive filenames.
- Kept the Digital Twin simulation at a full 72 hours.
- Improved optimization-mode behavior so cost/emissions/balanced/reliability priorities can produce different battery-reserve decisions.

## Run
Backend:

```powershell
cd backend
python -m uvicorn server:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173`.
