# beancount_io.py
import re
import subprocess
from decimal import Decimal


def run_bean_query(journal_path: str, query: str) -> Decimal:
    """Run bean-query and parse a single number from the last line."""
    cmd = ["bean-query", journal_path, query]
    out = subprocess.check_output(cmd, text=True)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    last = lines[-1]
    m = re.search(r"([-+]?\d[\d_,]*(?:\.\d+)?)", last)
    if not m:
        raise RuntimeError(f"bean-query parse error: {last}")
    num = m.group(1).replace(",", "").replace("_", "")
    return Decimal(num)


def run_bean_query_rows(journal_path: str, query: str):
    """Return list of lines from bean-query (non-JSON)."""
    cmd = ["bean-query", journal_path, query]
    out = subprocess.check_output(cmd, text=True)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    # drop headers/separators
    data = [
        ln
        for ln in lines
        if not set(ln).issubset(set("─=|+- "))
        and not ln.lower().startswith(("currency", "sum"))
    ]
    return data


def parse_grouped_amounts(lines):
    """Parse rows like:
       'curr    sum(position)'
       'CRC     364942.23 CRC'
       'USD     331.29 USD'
    Return: list of (currency, Decimal amount) without conversion.
    """
    out = []
    for ln in lines:
        if ln.lower().startswith("curr"):
            continue
        m = re.match(r"^([A-Z]{2,6})\s+([-+]?\d[\d_,]*(?:\.\d+)?)\s+[A-Z]{2,6}$", ln)
        if not m:
            continue
        cur, amount = m.groups()
        amount = Decimal(amount.replace(",", "").replace("_", ""))
        out.append((cur, amount))
    return out

