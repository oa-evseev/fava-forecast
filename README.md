# fava-forecast

**Fava extension for budget and cash-flow forecasting based on Beancount data.**

---

## Overview

`fava-forecast` analyses Beancount journals and budget files to project your future financial balance.
It combines current assets, liabilities, planned income, expenses, and recurring budgets to calculate the expected balance by a target date.

You can run it standalone via command line or integrate it as a [Fava](https://beancount.github.io/fava/) extension.

---

## Features

- Reads data directly from your Beancount journal.
- Evaluates:
  - Current **Assets** and **Liabilities**
  - **Planned Income** and **Planned Expenses** (tagged `#planned`)
  - **Budgeted Expenses** from `budgets.bean`
- Supports automatic **currency conversion** using `prices.bean`.
- Provides detailed per-currency breakdowns (`--verbose`).
- Works with any operating currency configured in your Beancount file.
- Integrated into Fava as a custom report tab.

---

## Installation

```bash
git clone https://github.com/oa-evseev/fava-forecast.git
cd fava-forecast
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Dependencies

- `beancount >= 3.2.0`
- `beanquery >= 0.2.0`
- Python ≥ 3.9

---

## Usage (CLI)

```bash
python -m fava_forecast.cli \
  --journal examples/main.bean \
  --budgets examples/budgets.bean \
  --prices examples/prices.bean \
  --until 2025-12-31 \
  [--today YYYY-MM-DD] \
  [--currency USD] \
  [--verbose]
```

### Example output

```bash
Operating currency: CRC
Today: 2025-10-27  Until(salary): 2025-11-15
Assets:                           2 345 600.00 CRC
Liabilities:                        320 000.00 CRC
Net now (Assets - Liabilities):   2 025 600.00 CRC
Planned income in range:            450 000.00 CRC
Planned expenses in range:          120 000.00 CRC
Planned budget expenses:            180 000.00 CRC
————————————————————————————————————————————————————————————————————
Forecast end balance:             2 175 600.00 CRC   [OK ✅]
```

---

## Fava integration

Add the following line to your main Beancount file:

```beancount
2025-01-01 custom "fava-extension" "fava_forecast.fava_ext" "currency=CRC"
```

Then start Fava pointing to your ledger:

```bash
fava /path/to/main.bean -p 5001
```

A new tab **Budget Forecast** will appear in the Fava menu.

Default files `budgets.bean` and `prices.bean` are automatically detected in the same directory as your main journal.

You can override parameters in the browser using query strings, for example:

```
http://127.0.0.1:5001/your-ledger/extension/budget-forecast/?until=2026-06-30&currency=USD
```

---

## Additional features

- Displays **BeanQuery warnings and errors** directly in Fava under the forecast table.
- Detects **planned entries in the past** from `future.bean` and lists them for review.
- Works seamlessly with an optional `accounts.bean` file to ensure all accounts are resolved.

---

## Project structure

```
src/fava_forecast/
    beancount_io.py   # Beancount / BeanQuery I/O helpers
    budgets.py        # Budget parsing and forecast logic
    cli.py            # Standalone CLI interface
    config.py         # Option parsing and currency detection
    convert.py        # Currency conversions and aggregation
    dateutils.py      # Date and period helpers
    formatters.py     # Console and HTML formatters
    fava_ext.py       # Full Fava extension integration
```

---

## Planned roadmap

- [x] Add configurable parameters via the Fava web UI
- [ ] Add interactive charts and trend visualisation
- [ ] Support for multiple forecast profiles (optimistic / base / pessimistic)
- [ ] Export forecast results as CSV or JSON
- [ ] Improve caching and performance for large ledgers

---

© 2025 Oleg Evseev
Licensed under the MIT License.
