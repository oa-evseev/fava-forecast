# convert.py
from decimal import Decimal


def convert_breakdown(rows, rates: dict, op_cur: str):
    """
    rows: [(cur, amount)]
    rates: dict cur->rate_in_op
    return: (total_in_op, breakdown_list)
      breakdown_list: [(cur, amount, rate_or_None, converted_or_None)]
    """
    total = Decimal("0")
    breakdown = []
    for cur, amt in rows:
        rate = rates.get(cur)
        converted = (amt * rate) if rate is not None else None
        if converted is not None:
            total += converted
        breakdown.append((cur, amt, rate, converted))
    return total, breakdown


def sum_to_op_currency(journal_path: str, query_grouped: str, rates: dict, op_cur: str) -> Decimal:
    """
    Process bean-query result like:
      CRC    364942.23 CRC
      USD    331.29 USD
    Convert everything into op_cur using rates.
    """
    import re
    from decimal import Decimal
    from .beancount_io import run_bean_query_rows

    rows = run_bean_query_rows(journal_path, query_grouped)

    total = Decimal("0")
    for ln in rows:
        if ln.lower().startswith("cur"):
            continue
        m = re.match(r"^([A-Z]{2,6})\s+([-+]?\d[\d_,]*(?:\.\d+)?)\s+[A-Z]{2,6}$", ln)
        if not m:
            continue
        cur, amount = m.groups()
        amount = Decimal(amount.replace(",", "").replace("_", ""))
        rate = rates.get(cur)
        if rate is None:
            print(f"⚠ no rate for {cur}")
            continue
        total += amount * rate
    return total

