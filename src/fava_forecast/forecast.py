# forecast.py
import datetime
import tempfile
from pathlib import Path
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
# Internal query builders
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


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------
def run_grouped_rows(journal_path: str, query: str, messages: list[dict[str, str]] | None = None) -> List[Row]:
    try:
        lines, warns = beanquery_run_lines(journal_path, query)
        if messages is not None:
            for w in warns:
                messages.append(
                    {
                        "level": "warning",
                        "code": "beanquery-warning",
                        "text": w,
                    }
                )
        body = beanquery_table_body(lines)
        return beanquery_grouped_amounts(body)
    except Exception as exc:
        if messages is not None:
            messages.append(
                {
                    "level": "warning",
                    "code": "beanquery-error",
                    "text": f"Beanquery failed for {journal_path} and query '{query}': {exc}",
                }
            )
        return []


def _extract_account_decls(accounts_path: str) -> str:
    """
    Read accounts file and return only declaration lines that help beanquery
    understand accounts and commodities.
    """
    p = Path(accounts_path)
    if not p.exists():
        return ""
    decls: List[str] = []
    text = p.read_text(encoding="utf-8")
    for line in text.splitlines():
        line_strip = line.strip()
        # keep open declarations
        if line_strip.startswith(tuple(str(y) for y in range(1))):
            # this is too weird :) instead, just test keywords
            pass
        # simplest robust check:
        if " open " in f" {line_strip} ":
            decls.append(line)
            continue
        if " commodity " in f" {line_strip} ":
            decls.append(line)
            continue
        if line_strip.startswith("option "):
            decls.append(line)
            continue
    return "\n".join(decls)


def _build_enriched_future(future_path: str, accounts_path: str) -> str:
    """
    Build a temp file that contains account/commodity declarations
    followed by the original future journal.
    Returns path to the temp file.
    """
    decls = _extract_account_decls(accounts_path)
    future_txt = Path(future_path).read_text(encoding="utf-8")
    combined = decls + "\n" + future_txt if decls else future_txt

    tmp = tempfile.NamedTemporaryFile("w+", suffix=".bean", delete=False)
    tmp.write(combined)
    tmp.flush()
    tmp.close()
    return tmp.name


def run_grouped_rows_all(
    journals: List[str],
    query: str,
    messages: List[Dict[str, str]],
) -> List[Row]:
    acc: dict[str, Decimal] = {}
    for j in journals:
        rows = run_grouped_rows(j, query, messages)
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
    accounts: str | None = None,
) -> Dict[str, Any]:
    """Core forecasting logic used by both CLI and Fava extension."""
    until_date = datetime.date.fromisoformat(until)
    today_date = datetime.date.fromisoformat(today) if today else datetime.date.today()

    messages: List[Dict[str, str]] = []

    op_currency = currency
    if op_currency == "CRC":
        op_currency = detect_operating_currency_from_journal(journal, default_cur="CRC")

    rates = load_prices_to_op(prices, op_currency, today_date)

    # assets / liabilities from main journal
    rows_assets = run_grouped_rows(journal, q_assets(until_date), messages)
    assets_total, assets_br = amounts_to_converted_breakdown(rows_assets, rates)

    rows_liabs = run_grouped_rows(journal, q_liabs(until_date), messages)
    liabs_total, liabs_br = amounts_to_converted_breakdown(rows_liabs, rates)

    # decide what to use for future
    journals = [journal]
    enriched_future_path: str | None = None

    if future_journal:
        if accounts:
            # build enriched future journal so beanquery knows accounts
            enriched_future_path = _build_enriched_future(future_journal, accounts)
            journals.append(enriched_future_path)
        else:
            messages.append(
                {
                    "level": "warning",
                    "code": "future-missing-accounts",
                    "text": "Future journal was provided, but accounts file is missing; future entries were not included.",
                }
            )

    # future income / expenses
    rows_pin = run_grouped_rows_all(journals, q_future_income(today_date, until_date), messages)
    # income is credit -> invert
    rows_pin = [(cur, -amt) for (cur, amt) in rows_pin]
    planned_income, pin_br = amounts_to_converted_breakdown(rows_pin, rates)

    rows_pexp = run_grouped_rows_all(journals, q_future_expenses(today_date, until_date), messages)
    planned_exp, pexp_br = amounts_to_converted_breakdown(rows_pexp, rates)

    # budgets
    planned_budget_exp, budg_br = compute_budget_planned_expenses(
        budgets, today_date, until_date, rates, op_currency
    )

    # totals
    net_now = assets_total + liabs_total
    total_future_exp = planned_exp + planned_budget_exp
    forecast_end = (net_now + planned_income - total_future_exp).quantize(Decimal("0.01"))

    # past future rows (only if we actually enriched and used future)
    past_future_rows: List[str] = []
    if future_journal and accounts:
        q_past = (
            "SELECT date, narration, account, position "
            f"WHERE date < {today_date.isoformat()} "
        )
        try:
            past_future_rows, past_warns = beanquery_run_lines(enriched_future_path or future_journal, q_past)

            # also surface warnings from this query
            for w in past_warns:
                messages.append(
                    {
                        "level": "warning",
                        "code": "beanquery-warning",
                        "text": w,
                    }
                )
        except Exception as exc:
            messages.append(
                {
                    "level": "warning",
                    "code": "future-past-query-failed",
                    "text": f"Failed to load past planned entries from future journal: {exc}",
                }
            )
        else:
            if past_future_rows:
                messages.append(
                    {
                        "level": "info",
                        "code": "future-past-entries",
                        "text": "There are planned entries dated before the forecast start. Please move them to the main ledger.",
                    }
                )

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
        "messages": messages,
    }
