# fava_ext.py
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional

from flask import request
from fava.ext import FavaExtensionBase

from .forecast import run_forecast
from .formatters import fmt_amount
from .rates import load_prices_to_op


def _parse_config(config: Optional[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not config:
        return out
    for part in config.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


class BudgetForecast(FavaExtensionBase):
    """
    Fava extension that renders a summary forecast and optional breakdowns.
    Template receives only `ledger` and `extension`.
    """

    name = "budget-forecast"
    report_title = "Budget Forecast"

    def __init__(self, ledger, config: Optional[str] = None) -> None:
        # ⚠️ Not calling super() with config — Fava will try to eval() the line
        super().__init__(ledger, None)
        self._cfg = _parse_config(config)
        self._cache_key = None
        self._cache_data = None

    # Exposed helper for formatting numbers in the template
    def fmt(self, x: Decimal) -> str:
        return fmt_amount(x)

    # Main data builder consumed by the template
    def data(self) -> Dict[str, Any]:
        # Resolve journal path and base dir
        journal_path = getattr(self.ledger, "beancount_file_path", None) or self.ledger.options.get("filename")
        base_dir = Path(str(journal_path)).resolve().parent

        # Query params
        q = request.args
        today_param = q.get("today")
        until_param = q.get("until")
        currency_param = q.get("currency", self._cfg.get("currency", "CRC"))
        verbose = q.get("verbose") in {"1", "true", "True", "yes", "on"}

        today = today_param or dt.date.today().isoformat()
        default_until = (dt.date.fromisoformat(today) + dt.timedelta(days=14)).isoformat()
        until = until_param or default_until

        today_date = dt.date.fromisoformat(today)

        quick_until = {
            "1w": (today_date + dt.timedelta(days=7)).isoformat(),
            "2w": (today_date + dt.timedelta(days=14)).isoformat(),
            "1m": (today_date + dt.timedelta(days=30)).isoformat(),
            "3m": (today_date + dt.timedelta(days=90)).isoformat(),
            "6m": (today_date + dt.timedelta(days=182)).isoformat(),
            "1y": (today_date + dt.timedelta(days=365)).isoformat(),
        }

        budgets = q.get("budgets", self._cfg.get("budgets", "")) or str(base_dir / "budgets.bean")
        prices  = q.get("prices",  self._cfg.get("prices",  "")) or str(base_dir / "prices.bean")
        future = q.get("future", self._cfg.get("future", "")) or str(base_dir / "future.bean")
        accounts = q.get("accounts", self._cfg.get("accounts", "")) or str(base_dir / "accounts.bean")

        # load available currencies from prices file for the selector
        try:
            rates_raw = load_prices_to_op(prices, currency_param, dt.date.fromisoformat(today))
            available_currencies = sorted(rates_raw.keys())
        except Exception:
            # if prices missing / broken — fallback to current currency only
            available_currencies = [currency_param]

        # Param-based cache
        cache_key = (
            str(journal_path),
            today,
            until,
            currency_param,
            budgets,
            prices,
            future,
            accounts,
            verbose,
        )
        if getattr(self, "_cache_key", None) == cache_key and getattr(self, "_cache_data", None) is not None:
            return self._cache_data  # type: ignore[return-value]

        core = run_forecast(
            journal=str(journal_path),
            budgets=str(budgets),
            prices=str(prices),
            until=until,
            today=today,
            currency=currency_param,
            verbose=verbose,
            future_journal=str(future),
            accounts=str(accounts),
        )

        cur = core["op_currency"]
        assets_total, assets_br = core["assets"]
        liabs_total, liabs_br = core["liabs"]
        planned_income, pin_br = core["planned_income"]
        planned_exp, pexp_br = core["planned_expenses"]
        planned_budget_exp, budg_br = core["planned_budget_exp"]
        past_future = core["past_future"]

        result = {
            "currencies": available_currencies,
            "operating_currency": cur,
            "today": core["today"],
            "until": core["until"],
            "quick_until": quick_until,
            "verbose": verbose,
            "paths": {"budgets": budgets, "prices": prices, "future": future, "accounts": accounts},
            "past_future": past_future,
            "messages": core.get("messages", []),
            "summary": {
                "assets": assets_total,
                "liabs": liabs_total,
                "net_now": core["net_now"],
                "planned_income": planned_income,
                "planned_expenses": planned_exp,
                "planned_budget_expenses": planned_budget_exp,
                "forecast_end": core["forecast_end"],
                "ok": core["ok"],
            },
            "breakdowns": {
                "assets": assets_br,
                "liabs": liabs_br,
                "planned_income": pin_br,
                "planned_expenses": pexp_br,
                "planned_budget_expenses": budg_br,
            },
        }

        self._cache_key = cache_key
        self._cache_data = result
        return result



# Required entry point for Fava
Extension = BudgetForecast
