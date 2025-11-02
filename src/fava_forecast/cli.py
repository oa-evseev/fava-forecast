# cli.py
import argparse
import datetime
from decimal import Decimal
from typing import List, Tuple

from .beancount_io import (
    beanquery_grouped_amounts,
    beanquery_run_lines,
    beanquery_table_body,
)
from .budgets import compute_budget_planned_expenses
from .config import detect_operating_currency_from_journal
from .convert import amounts_to_converted_breakdown
from .formatters import print_breakdown, fmt_amount
from .rates import load_prices_to_op


Row = Tuple[str, Decimal]  # (currency, amount)


# -----------------------------
# Query builders
# -----------------------------
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


def q_planned_income(today: datetime.date, until: datetime.date) -> str:
    return (
        "SELECT currency, sum(position) "
        "WHERE account ~ '^Income' "
        f"AND date >= {today.isoformat()} AND date < {until.isoformat()} "
        "AND 'planned' IN tags GROUP BY currency"
    )


def q_planned_expenses(today: datetime.date, until: datetime.date) -> str:
    return (
        "SELECT currency, sum(position) "
        "WHERE account ~ '^Expenses' "
        f"AND date >= {today.isoformat()} AND date < {until.isoformat()} "
        "AND 'planned' IN tags GROUP BY currency"
    )


# -----------------------------
# Helpers
# -----------------------------
def run_grouped_rows(journal_path: str, query: str) -> List[Row]:
    lines = beanquery_run_lines(journal_path, query)
    body = beanquery_table_body(lines)
    return beanquery_grouped_amounts(body)


# -----------------------------
# CLI
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Forecast runway to salary using Beancount + budgets")
    ap.add_argument("--journal", required=True, help="Path to main.bean")
    ap.add_argument("--budgets", required=True, help="Path to budgets.bean")
    ap.add_argument("--prices", required=True, help="Path to prices.bean")
    ap.add_argument("--until", required=True, help="Salary date YYYY-MM-DD (exclusive)")
    ap.add_argument("--today", default=None, help="Override today YYYY-MM-DD (optional)")
    ap.add_argument("--currency", default="CRC", help="Override operating currency (default: 'CRC')")
    ap.add_argument("--verbose", action="store_true", help="Print per-currency breakdowns")
    args = ap.parse_args()

    until = datetime.date.fromisoformat(args.until)
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()

    op_currency = args.currency
    if op_currency == "CRC":
        op_currency = detect_operating_currency_from_journal(args.journal, default_cur="CRC")

    rates = load_prices_to_op(args.prices, op_currency, today)

    print(f"Operating currency: {op_currency}")
    print(f"Today: {today}  Until(salary): {until}")

    # ASSETS
    rows_assets = run_grouped_rows(args.journal, q_assets(until))
    assets_total, assets_br = amounts_to_converted_breakdown(rows_assets, rates)

    # LIABILITIES
    rows_liabs = run_grouped_rows(args.journal, q_liabs(until))
    liabs_total, liabs_br = amounts_to_converted_breakdown(rows_liabs, rates)

    # PLANNED INCOME
    rows_pin = run_grouped_rows(args.journal, q_planned_income(today, until))
    rows_pin = [(cur, -amt) for (cur, amt) in rows_pin]
    planned_income, pin_br = amounts_to_converted_breakdown(rows_pin, rates)

    # PLANNED EXPENSES
    rows_pexp = run_grouped_rows(args.journal, q_planned_expenses(today, until))
    planned_exp, pexp_br = amounts_to_converted_breakdown(rows_pexp, rates)

    # BUDGETED EXPENSES
    planned_budget_exp, budg_br = compute_budget_planned_expenses(
        args.budgets, today, until, rates, op_currency
    )

    net_now = assets_total + liabs_total
    total_future_exp = planned_exp + planned_budget_exp
    forecast_end = (net_now + planned_income - total_future_exp).quantize(Decimal("0.01"))

    if args.verbose:
        print_breakdown("ASSETS breakdown:", assets_br, assets_total, op_currency)
        print_breakdown("LIABILITIES breakdown:", liabs_br, liabs_total, op_currency)
        print_breakdown("PLANNED INCOME breakdown:", pin_br, planned_income, op_currency)
        print_breakdown("PLANNED EXPENSES breakdown:", pexp_br, planned_exp, op_currency)
        print_breakdown("BUDGETED EXPENSES breakdown (forecast):", budg_br, planned_budget_exp, op_currency)

    print(f"Assets:                         {fmt_amount(assets_total):>15} {op_currency}")
    print(f"Liabilities:                    {fmt_amount(-liabs_total):>15} {op_currency}")
    print(f"Net now (Assets - Liabilities): {fmt_amount(net_now):>15} {op_currency}")
    print(f"Planned income in range:        {fmt_amount(planned_income):>15} {op_currency}")
    print(f"Planned expenses in range:      {fmt_amount(planned_exp):>15} {op_currency}")
    print(f"Planned budget expenses:        {fmt_amount(planned_budget_exp):>15} {op_currency}")
    print("—" * 60)
    sign = "OK ✅" if forecast_end >= 0 else "DEFICIT ❌"
    print(f"Forecast end balance:           {fmt_amount(forecast_end):>15} {op_currency}   [{sign}]")


if __name__ == "__main__":
    main()
