# beancount_io.py
import os
import re
import subprocess
from decimal import Decimal
from typing import List, Tuple


Row = Tuple[str, Decimal]  # (currency, amount)


# ----------------------------------------------------------------
# Core bean-query runners
# ----------------------------------------------------------------
def beanquery_run_lines(journal_path: str, query: str) -> List[str]:
    """
    Run `bean-query` on the given journal and return all non-empty lines.
    Raises RuntimeError on failure or parse issues.
    """
    if not os.path.exists(journal_path):
        raise FileNotFoundError(f"Journal file not found: {journal_path}")

    cmd = ["bean-query", journal_path, query]
    try:
        output = subprocess.check_output(cmd, text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"bean-query failed: {e}") from e

    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    return lines


def beanquery_table_body(lines: List[str]) -> List[str]:
    """
    Strip headers, separators, and totals from bean-query output.
    Keeps only table body lines with data like:
      'USD     10.00 USD'
    """
    if not lines:
        return []

    body: List[str] = []
    for ln in lines:
        # Skip decorative/separator lines
        if set(ln).issubset(set("─=|+- ")):
            continue
        # Skip header or summary lines
        if ln.lower().startswith(("currency", "sum", "total")):
            continue
        body.append(ln)
    return body


# ----------------------------------------------------------------
# Parsing helpers
# ----------------------------------------------------------------
def beanquery_grouped_amounts(body_lines: List[str]) -> List[Row]:
    """
    Parse grouped currency summary lines (after table cleanup).

    Input example:
      ['USD     10.00 USD', 'CRC  1_000.00 CRC']
    Output:
      [('USD', Decimal('10.00')), ('CRC', Decimal('1000.00'))]
    """
    out: List[Row] = []
    rx = re.compile(r"^([A-Z]{2,6})\s+([-+]?\d[\d_,]*(?:\.\d+)?)\s+[A-Z]{2,6}$")

    for ln in body_lines:
        m = rx.match(ln.strip())
        if not m:
            continue
        cur, amt = m.groups()
        amt_dec = Decimal(amt.replace(",", "").replace("_", ""))
        out.append((cur, amt_dec))
    return out


# ----------------------------------------------------------------
# Combined convenience function
# ----------------------------------------------------------------
def beanquery_grouped_amounts_from_journal(journal_path: str, query: str) -> List[Row]:
    """
    Run a grouped bean-query and return parsed (currency, amount) pairs.

    Essentially combines:
      beanquery_run_lines → beanquery_table_body → beanquery_grouped_amounts
    """
    lines = beanquery_run_lines(journal_path, query)
    body = beanquery_table_body(lines)
    return beanquery_grouped_amounts(body)
