# cli.py
import argparse
import datetime
from decimal import Decimal, ROUND_HALF_UP

from .beancount_io import run_bean_query_rows, parse_grouped_amounts
from .budgets import compute_budget_planned_expenses
from .convert import convert_breakdown
from .formatters import fmt_amount, print_breakdown
from .rates import load_prices_to_op
from .config import detect_operating_currency_from_journal


def main():
    ap = argparse.ArgumentParser(description="Forecast runway to salary using Beancount + budgets")
    ap.add_argument("--journal", required=True, help="Path to main.bean")
    ap.add_argument("--budgets", required=True, help="Path to budgets.bean")
    ap.add_argument("--prices", required=True, help="Path to prices.bean")
    ap.add_argument("--until", required=True, help="Salary date YYYY-MM-DD (exclusive)")
    ap.add_argument("--today", default=None, help="Override today YYYY-MM-DD (optional)")
    ap.add_argument("--currency", default="CRC", help="Override operation currency (optional, default='CRC')")
    ap.add_argument("--verbose", action="store_true", help="Enable printing detailed report by currencies (default: False)")
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
    q_assets = (
        f"SELECT currency, sum(position) WHERE account ~ '^Assets' "
        f"AND date < {until.isoformat()} AND 'planned' NOT IN tags GROUP BY currency"
    )
    rows_assets = parse_grouped_amounts(run_bean_query_rows(args.journal, q_assets))
    assets_total, assets_br = convert_breakdown(rows_assets, rates, op_currency)

    # LIABILITIES
    q_liabs = (
        f"SELECT currency, sum(position) WHERE account ~ '^Liabilities' "
        f"AND date < {until.isoformat()} AND 'planned' NOT IN tags GROUP BY currency"
    )
    rows_liabs = parse_grouped_amounts(run_bean_query_rows(args.journal, q_liabs))
    liabs_total, liabs_br = convert_breakdown(rows_liabs, rates, op_currency)

    # PLANNED INCOME
    q_planned_income = (
        f"SELECT currency, sum(position) "
        f"WHERE account ~ '^Income' "
        f"AND date >= {today.isoformat()} AND date < {until.isoformat()} "
        f"AND 'planned' IN tags GROUP BY currency"
    )
    rows_pin = parse_grouped_amounts(run_bean_query_rows(args.journal, q_planned_income))
    rows_pin = [(cur, -amt) for (cur, amt) in rows_pin]  # Income is negative; flip sign
    planned_income, pin_br = convert_breakdown(rows_pin, rates, op_currency)

    # PLANNED EXPENSES
    q_planned_exp = (
        f"SELECT currency, sum(position) "
        f"WHERE account ~ '^Expenses' "
        f"AND date >= {today.isoformat()} AND date < {until.isoformat()} "
        f"AND 'planned' IN tags GROUP BY currency"
    )
    rows_pexp = parse_grouped_amounts(run_bean_query_rows(args.journal, q_planned_exp))
    planned_exp, pexp_br = convert_breakdown(rows_pexp, rates, op_currency)

    # BUDGETED EXPENSES
    planned_budget_exp, budg_br = compute_budget_planned_expenses(
        args.budgets, today, until, rates, op_currency
    )

    net_now = assets_total + liabs_total
    total_future_exp = planned_exp + planned_budget_exp
    forecast_end = (net_now + planned_income - total_future_exp).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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

