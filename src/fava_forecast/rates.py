# rates.py
import datetime
import os
from decimal import Decimal


def load_prices_to_op(prices_path: str, op_cur: str, today: datetime.date):
    """
    Read prices.bean and build mapping rate[currency] -> Decimal in op_cur.
    Take LAST price <= today. Direct pairs X -> op_cur. Simple chains X->USD->op_cur for USD.
    """
    import re

    rates_direct = {}  # (cur) -> [(date, rate)]
    rates_usd = {}     # (cur) -> [(date, rate)]  # for cases like ETH USD
    usd_to_op = []     # [(date, rate)]           # USD -> op_cur

    if not os.path.exists(prices_path):
        return {}

    rx = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+price\s+([A-Z0-9]{2,6})\s+([\d_]+(?:\.\d+)?)\s+([A-Z]{3,5})")
    with open(prices_path, "r", encoding="utf-8") as f:
        for line in f:
            m = rx.match(line.strip())
            if not m:
                continue
            d, base, amt, quote = m.groups()
            d = datetime.date.fromisoformat(d)
            val = Decimal(amt.replace("_", ""))
            if quote == op_cur:
                rates_direct.setdefault(base, []).append((d, val))
            if quote == "USD":
                rates_usd.setdefault(base, []).append((d, val))
            if base == "USD" and quote == op_cur:
                usd_to_op.append((d, val))

    def last_rate(pairs):
        cand = [(d, v) for (d, v) in pairs if d <= today]
        if not cand:
            return None
        return sorted(cand, key=lambda x: x[0])[-1][1]

    rate = {}
    rate[op_cur] = Decimal("1")

    for cur, pairs in rates_direct.items():
        r = last_rate(pairs)
        if r is not None:
            rate[cur] = r

    usd2op = last_rate(usd_to_op)
    if usd2op is not None:
        for cur, pairs in rates_usd.items():
            r = last_rate(pairs)
            if r is not None:
                rate[cur] = (r * usd2op)

    return rate

