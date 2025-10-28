# fava-forecast

**Fava extension for budget and cash-flow forecasting based on Beancount data.**

---

## Overview

`fava-forecast` analyses Beancount journals and budget files to project your future financial balance.  
It combines current assets, liabilities, planned income, expenses, and recurring budgets to calculate the expected balance by a target date.

You can run it standalone via command line or later integrate it as a [Fava](https://beancount.github.io/fava/) extension.

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
- Modular structure, ready for integration into Fava.

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
——————————————————————————————————————————————————————
Forecast end balance:             2 175 600.00 CRC   [OK ✅]
```

---

## Project structure

```
src/fava_forecast/
    beancount_io.py   # bean-query wrappers
    budgets.py        # budget parsing and forecast logic
    cli.py            # CLI interface
    config.py         # constants and currency detection
    convert.py        # conversions and aggregation
    dateutils.py      # date helpers
    formatters.py     # pretty console output
    fava_ext.py       # placeholder for Fava integration
```

---

## Planned roadmap

- [ ] Add web interface in Fava (custom report tab)
- [ ] Interactive charts for balance projection
- [ ] Support for multiple forecast scenarios
- [ ] Optional CSV/JSON export

---

© 2025 Oleg Evseev  
Licensed under the MIT License.
