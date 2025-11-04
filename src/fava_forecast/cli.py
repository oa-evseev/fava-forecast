# cli.py
import argparse
import datetime
from .config import detect_operating_currency_from_journal
from .rates import load_prices_to_op
from .forecast import run_forecast
from .formatters import print_breakdown, fmt_amount

# ----------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Forecast runway to salary using Beancount + budgets")
    ap.add_argument("--journal", required=True, help="Path to main.bean")
    ap.add_argument("--budgets", required=True, help="Path to budgets.bean")
    ap.add_argument("--prices", required=True, help="Path to prices.bean")
    ap.add_argument("--until", required=True, help="Salary date YYYY-MM-DD (exclusive)")
    ap.add_argument("--today", default=None, help="Override today YYYY-MM-DD (optional)")
    ap.add_argument("--future", default=None, help="Path to future.bean")
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

    data = run_forecast(
        journal=args.journal,
        budgets=args.budgets,
        prices=args.prices,
        until=args.until,
        today=args.today,
        currency=args.currency,
        verbose=args.verbose,
        future_journal=args.future,
    )

    if data.get("past_future"):
        print("\nWARNING: the following planned entries are in the past, move them to your main ledger:")
        for line in data["past_future"]:
            print(f"  {line}")
        print()

    op_currency = data["op_currency"]
    if args.verbose:
        print_breakdown("ASSETS breakdown:", data["assets"][1], data["assets"][0], op_currency)
        print_breakdown("LIABILITIES breakdown:", data["liabs"][1], data["liabs"][0], op_currency)
        print_breakdown("PLANNED INCOME breakdown:", data["planned_income"][1], data["planned_income"][0], op_currency)
        print_breakdown("PLANNED EXPENSES breakdown:", data["planned_expenses"][1], data["planned_expenses"][0], op_currency)
        print_breakdown("BUDGETED EXPENSES breakdown (forecast):", data["planned_budget_exp"][1], data["planned_budget_exp"][0], op_currency)

    print(f"Assets:                         {fmt_amount(data['assets'][0]):>15} {op_currency}")
    print(f"Liabilities:                    {fmt_amount(-data['liabs'][0]):>15} {op_currency}")
    print(f"Net now (Assets - Liabilities): {fmt_amount(data['net_now']):>15} {op_currency}")
    print(f"Planned income in range:        {fmt_amount(data['planned_income'][0]):>15} {op_currency}")
    print(f"Planned expenses in range:      {fmt_amount(data['planned_expenses'][0]):>15} {op_currency}")
    print(f"Planned budget expenses:        {fmt_amount(data['planned_budget_exp'][0]):>15} {op_currency}")
    print("—" * 60)
    sign = "OK ✅" if data["ok"] else "DEFICIT ❌"
    print(f"Forecast end balance:           {fmt_amount(data['forecast_end']):>15} {op_currency}   [{sign}]")


if __name__ == "__main__":
    main()
