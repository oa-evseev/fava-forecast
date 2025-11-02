# convert.py
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple

from .beancount_io import (
    beanquery_grouped_amounts,
    beanquery_run_lines,
    beanquery_table_body,
)

# Types
Row = Tuple[str, Decimal]  # (currency, amount)
BreakdownRow = Tuple[str, Decimal, Optional[Decimal], Optional[Decimal]]


def amounts_to_converted_breakdown(
    rows: Iterable[Row],
    rates: Dict[str, Decimal],
) -> Tuple[Decimal, List[BreakdownRow]]:
    """
    Convert a list of (currency, amount) using provided rates.
    Returns (total_in_op, breakdown), where breakdown rows are:
      (currency, amount_in_cur, rate_or_None, converted_or_None)
    """
    total = Decimal("0")
    breakdown: List[BreakdownRow] = []
    for cur, amt in rows:
        rate = rates.get(cur)
        conv = (amt * rate) if rate is not None else None
        if conv is not None:
            total += conv
        breakdown.append((cur, amt, rate, conv))
    return total, breakdown


def query_grouped_sum_to_total(
    journal_path: str,
    grouped_query: str,
    rates: Dict[str, Decimal],
) -> Decimal:
    """
    Execute a bean-query that returns grouped currency rows and
    sum them into operating currency using `rates`.

    Expected table body lines (after header removal):
      'USD     10.00 USD'
      'CRC 1_000.00 CRC'
    """
    lines = beanquery_run_lines(journal_path, grouped_query)
    body = beanquery_table_body(lines)
    rows = beanquery_grouped_amounts(body)  # [(cur, amount)]
    total, _ = amounts_to_converted_breakdown(rows, rates)
    return total
