# rates.py
import datetime
import os
import re
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

from .errors import PriceParseError


# ----------------------------------------------------------------
# Data types
# ----------------------------------------------------------------
RatePairs = List[Tuple[datetime.date, Decimal]]  # e.g. [("2025-01-01", Decimal("0.85"))]
RatesDict = Dict[str, RatePairs]


# ----------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------
def _parse_price_line(line: str) -> Optional[Tuple[datetime.date, str, Decimal, str]]:
    """
    Parse a single line from prices.bean.
    Example:
        2025-01-01 price USD 530.10 CRC
    Returns: (date, base, value, quote) or None if not matched.
    """
    rx = re.compile(
        r"^(\d{4}-\d{2}-\d{2})\s+price\s+([A-Z0-9]{2,6})\s+([\d_]+(?:\.\d+)?)\s+([A-Z]{3,5})"
    )
    m = rx.match(line.strip())
    if not m:
        return None
    date_str, base, amount_str, quote = m.groups()
    try:
        date = datetime.date.fromisoformat(date_str)
        value = Decimal(amount_str.replace("_", ""))
    except Exception as e:
        raise PriceParseError(f"Invalid price line: {line}") from e
    return date, base, value, quote


def _select_last_rate(pairs: RatePairs, today: datetime.date) -> Optional[Decimal]:
    """
    Select the latest rate whose date <= today.
    """
    valid = [v for (d, v) in pairs if d <= today]
    if not valid:
        return None
    # dates are already comparable — pick the last
    pairs_sorted = sorted(pairs, key=lambda x: x[0])
    for d, val in reversed(pairs_sorted):
        if d <= today:
            return val
    return None


# ----------------------------------------------------------------
# Main API
# ----------------------------------------------------------------
def load_prices_to_op(
    prices_path: str,
    op_currency: str,
    today: datetime.date,
) -> Dict[str, Decimal]:
    """
    Read prices.bean and return mapping: {currency: rate_in_op_currency}.

    Supports:
      * Direct pairs  X -> op_currency
      * Indirect pairs X -> USD -> op_currency (one-hop chain)

    If prices file missing → returns empty dict.
    """
    if not os.path.exists(prices_path):
        return {}

    direct: RatesDict = {}
    via_usd: RatesDict = {}
    usd_to_op: RatePairs = []

    with open(prices_path, "r", encoding="utf-8") as f:
        for line in f:
            parsed = _parse_price_line(line)
            if not parsed:
                continue
            date, base, value, quote = parsed

            if quote == op_currency:
                direct.setdefault(base, []).append((date, value))
            elif quote == "USD":
                via_usd.setdefault(base, []).append((date, value))
            elif base == "USD" and quote == op_currency:
                usd_to_op.append((date, value))

    result: Dict[str, Decimal] = {op_currency: Decimal("1")}

    # direct conversions
    for cur, pairs in direct.items():
        rate = _select_last_rate(pairs, today)
        if rate is not None:
            result[cur] = rate

    # indirect through USD
    usd_rate = _select_last_rate(usd_to_op, today)
    if usd_rate is not None:
        for cur, pairs in via_usd.items():
            cur_to_usd = _select_last_rate(pairs, today)
            if cur_to_usd is not None:
                result[cur] = cur_to_usd * usd_rate

    return result
