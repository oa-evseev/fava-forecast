# budgets.py
import datetime
import os
import re
from decimal import Decimal


def compute_budget_planned_expenses(
    budgets_path: str,
    today: datetime.date,
    until: datetime.date,
    rates: dict,  # cur -> rate in operating currency
    op_cur: str,
):
    """
    Read custom "budget" from budgets.bean and estimate future expenses (today..until).
    Method: distribute budget evenly per day across frequency period.
    Support: weekly=7, monthly≈30.4375, quarterly≈91.3125, yearly≈365.25.

    Returns: (total_in_op, breakdown)
      breakdown: [(currency, Decimal_amount_in_cur, rate_or_None, converted_or_None)]
    """
    if not os.path.exists(budgets_path):
        return Decimal("0"), []

    period_days = {
        "weekly":    Decimal("7"),
        "monthly":   Decimal("30.4375"),
        "quarterly": Decimal("91.3125"),
        "yearly":    Decimal("365.25"),
    }

    rx = re.compile(
        r"^(\d{4}-\d{2}-\d{2})\s+custom\s+\"budget\"\s+\"([^\"]+)\"\s+\"(weekly|monthly|quarterly|yearly)\"\s+([\d_]+(?:\.\d+)?)\s+([A-Z]{3,6})\s*$"
    )

    by_currency = {}

    with open(budgets_path, "r", encoding="utf-8") as f:
        for line in f:
            m = rx.match(line.strip())
            if not m:
                continue
            start_s, account, freq, amt_s, cur = m.groups()
            start = datetime.date.fromisoformat(start_s)
            amt = Decimal(amt_s.replace("_", ""))

            start_calc = max(today, start)
            if until <= start_calc:
                continue

            days = Decimal(str((until - start_calc).days))
            pd = period_days[freq]
            daily = (amt / pd)
            planned = (daily * days)

            by_currency[cur] = by_currency.get(cur, Decimal("0")) + planned

    total = Decimal("0")
    breakdown = []
    for cur, amt in by_currency.items():
        rate = rates.get(cur)
        conv = (amt * rate) if rate is not None else None
        if conv is not None:
            total += conv
        breakdown.append((cur, amt, rate, conv))

    return total, breakdown

