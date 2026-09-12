# AI Powered Renewable Generation Forecasting Platform

This module converts renewable generation forecast and
risk output into operational actions.

## Added functionality

### 1. Explainable recommendations
Every decision includes:
- condition
- action(s)
- power allocated to each action
- dynamic reserve SOC
- confidence score
- urgency
- human-readable reasons

### 2. Multi-hour battery planning
`horizon_planner.py` plans a sequence of hourly actions and updates battery SOC
after every hour. It also detects future peak demand and can preserve battery
for an expected future shortage.

### 3. Price-aware dispatch
The engine can preserve battery for a more expensive future period or export
surplus when immediate export is economically attractive.

### 4. Dynamic battery reserve
Battery minimum reserve is not fixed. It changes with:
- Member 2 risk score
- forecast uncertainty
- expected future peak shortage
- optimization mode

### 5. Optimization modes
Supported:
- `lowest_cost`
- `lowest_co2`
- `maximum_reliability`
- `balanced`

### Additional features
- battery health derating
- battery degradation cost
- action confidence + urgency
- peak demand detection
- before/after What-If comparison
- multiple What-If scenarios
- automatic comparison of optimization modes

## Project files

- `decision_engine.py` — core explainable decision logic
- `impact_calculator.py` — cost, degradation, revenue and CO2
- `what_if_simulator.py` — direct slider/toggle What-If engine
- `horizon_planner.py` — 6/12/24-hour sequential planning
- `mode_optimizer.py` — compare cost/CO2/reliability policies
- `main.py` — end-to-end demonstration
- `tests.py` — basic functional tests
- `member3_operational_dataset.csv` — operational layer
- `ml_hourly_training_dataset.csv` — Model aligned hourly dataset


## Run

```bash
python main.py
```

Run tests:

```bash
python tests.py
```

The values for backup cost, battery degradation and CO2 are prototype
assumptions and should be displayed as simulated/estimated values.
