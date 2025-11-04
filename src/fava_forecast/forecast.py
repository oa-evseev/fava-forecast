# forecast.py
import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from .beancount_io import (
    beanquery_grouped_amounts,
    beanquery_run_lines,
    beanquery_table_body,
)
from .budgets import compute_budget_planned_expenses
from .config import detect_operating_currency_from_journal
from .convert import amounts_to_converted_breakdown
from .rates import load_prices_to_op


Row = Tuple[str, Decimal]  # (currency, amount)

# ----------------------------------------------------------------
# Internal query builders and helpers — unchanged
# ----------------------------------------------------------------
def q_assets(until: datetime.date) -> str:
    return (
        "SELECT currency, sum(position) "
        f"WHERE account ~ '^Assets' AND date < {until.isoformat()} "
        "AND 'planned' NOT IN tags GROUP BY currency"
    )


def q_liabs(until: datetime.date) -> str:
    return (
        "SELECT currency, sum(position) "
        f"WHERE account ~ '^Liabilities' AND date < {until.isoformat()} "
        "AND 'planned' NOT IN tags GROUP BY currency"
    )

def q_future_income(today: datetime.date, until: datetime.date) -> str:
    return (
        "SELECT currency, sum(position) "
        "WHERE account ~ '^Income' "
        f"AND date >= {today.isoformat()} AND date < {until.isoformat()} "
        "GROUP BY currency"
    )


def q_future_expenses(today: datetime.date, until: datetime.date) -> str:
    return (
        "SELECT currency, sum(position) "
        "WHERE account ~ '^Expenses' "
        f"AND date >= {today.isoformat()} AND date < {until.isoformat()} "
        "GROUP BY currency"
    )

def run_grouped_rows(journal_path: str, query: str) -> List[Row]:
    lines = beanquery_run_lines(journal_path, query)
    body = beanquery_table_body(lines)
    return beanquery_grouped_amounts(body)

def run_grouped_rows_all(journals: List[str], query: str) -> List[Row]:
    acc: dict[str, Decimal] = {}
    for j in journals:
        rows = run_grouped_rows(j, query)
        for cur, amt in rows:
            acc[cur] = acc.get(cur, Decimal("0")) + amt
    return list(acc.items())



# ----------------------------------------------------------------
# Core forecast logic
# ----------------------------------------------------------------
def run_forecast(
    journal: str,
    budgets: str,
    prices: str,
    until: str,
    today: str | None = None,
    currency: str = "CRC",
    verbose: bool = False,
    future_journal: str | None = None,
) -> Dict[str, Any]:
    """Core forecasting logic used by both CLI and Fava extension."""
    until_date = datetime.date.fromisoformat(until)
    today_date = datetime.date.fromisoformat(today) if today else datetime.date.today()

    op_currency = currency
    if op_currency == "CRC":
        op_currency = detect_operating_currency_from_journal(journal, default_cur="CRC")

    rates = load_prices_to_op(prices, op_currency, today_date)

    # assets / liabilities
    rows_assets = run_grouped_rows(journal, q_assets(until_date))
    assets_total, assets_br = amounts_to_converted_breakdown(rows_assets, rates)

    rows_liabs = run_grouped_rows(journal, q_liabs(until_date))
    liabs_total, liabs_br = amounts_to_converted_breakdown(rows_liabs, rates)

    # income / expenses
    journals = [journal]
    if future_journal:
        journals.append(future_journal)

    rows_pin = run_grouped_rows_all(journals, q_future_income(today_date, until_date))
    rows_pin = [(cur, -amt) for (cur, amt) in rows_pin]
    planned_income, pin_br = amounts_to_converted_breakdown(rows_pin, rates)

    rows_pexp = run_grouped_rows_all(journals, q_future_expenses(today_date, until_date))
    planned_exp, pexp_br = amounts_to_converted_breakdown(rows_pexp, rates)

    # budgets
    planned_budget_exp, budg_br = compute_budget_planned_expenses(
        budgets, today_date, until_date, rates, op_currency
    )

    # totals
    net_now = assets_total + liabs_total
    total_future_exp = planned_exp + planned_budget_exp
    forecast_end = (net_now + planned_income - total_future_exp).quantize(Decimal("0.01"))

    # past future rows
    past_future_rows = []
    if future_journal:
        q_past = (
            "SELECT date, narration, payee, account, position "
            f"WHERE date < {today_date.isoformat()} "
        )
        past_future_rows = beanquery_run_lines(future_journal, q_past)

    return {
        "op_currency": op_currency,
        "today": today_date,
        "until": until_date,
        "assets": (assets_total, assets_br),
        "liabs": (liabs_total, liabs_br),
        "planned_income": (planned_income, pin_br),
        "planned_expenses": (planned_exp, pexp_br),
        "planned_budget_exp": (planned_budget_exp, budg_br),
        "net_now": net_now,
        "forecast_end": forecast_end,
        "ok": forecast_end >= 0,
        "verbose": verbose,
        "past_future": past_future_rows,
    }

