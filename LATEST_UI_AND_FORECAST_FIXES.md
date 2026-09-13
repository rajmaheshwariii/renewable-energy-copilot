# Latest UI and Forecast Fixes

## Risk & Decisions
- Replaced the native decision-priority dropdown with four clear priority cards.
- This prevents the browser dropdown from covering the section below it.
- The same control is used in Settings for consistency.

## AI Insights
- Removed the generic plain-language explanation box.
- Added a useful selected-forecast snapshot showing forecast time, expected generation, likely range, and uncertainty.
- Constrained insight tables, metrics, and explanations to their cards so text does not spill outside.
- Converted technical feature values and effects into easier-to-read labels and units.

## Upcoming-date forecasting
- The calendar can now select historical dates or upcoming dates.
- Upcoming planning is available through 30 days from the current date.
- A 72-hour forecast is generated from the selected date and time.
- For dates after the latest measured plant record, the latest measured plant state is used as the operating context and the selected date supplies the calendar/hour pattern.

## Validation
- Backend Python files compile successfully.
- Backend test suite: 4 tests passed.
- Direct future-date test returned 72 hourly forecast points successfully.
