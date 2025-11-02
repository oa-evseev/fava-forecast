# beancount_io.py
import re
import subprocess
from decimal import Decimal
from typing import Iterable, List, Tuple

from .errors import BeanQueryError

# Regexes
_RE_NUMBER = re.compile(r"([-+]?\d[\d_,]*(?:\.\d+)?)")
_RE_GROUPED_ROW = re.compile(r"^([A-Z]{2,6})\s+([-+]?\d[\d_,]*(?:\.\d+)?)\s+[A-Z]{2,6}$")
_TABLE_TRASH_CHARS = set("─=|+- ")


def beanquery_run_lines(journal_path: str, query: str) -> List[str]:
    """
    Execute bean-query and return non-empty, stripped output lines.
    """
    cmd = ["bean-query", journal_path, query]
    out = subprocess.check_output(cmd, text=True)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def beanquery_last_scalar(lines: Iterable[str]) -> Decimal:
    """
    Parse a single numeric scalar from the last non-empty line.
    """
    try:
        last = list(lines)[-1]
    except IndexError:
        raise BeanQueryError("bean-query returned no lines")

    m = _RE_NUMBER.search(last)
    if not m:
        raise BeanQueryError(f"bean-query parse error: {last}")

    num = m.group(1).replace(",", "").replace("_", "")
    return Decimal(num)


def beanquery_table_body(lines: Iterable[str]) -> List[str]:
    """
    Drop table headers/separators from bean-query tabular output.
    """
    body = []
    for ln in lines:
        if set(ln).issubset(_TABLE_TRASH_CHARS):
            continue
        if ln.lower().startswith(("currency", "sum")):
            continue
        body.append(ln)
    return body


def beanquery_grouped_amounts(lines: Iterable[str]) -> List[Tuple[str, Decimal]]:
    """
    Parse lines of form:
      'CURR    364942.23 CURR'
    Return list of (currency, Decimal amount).
    """
    out: List[Tuple[str, Decimal]] = []
    for ln in lines:
        if ln.lower().startswith("curr"):
            continue
        m = _RE_GROUPED_ROW.match(ln)
        if not m:
            continue
        cur, amount = m.groups()
        amt = Decimal(amount.replace(",", "").replace("_", ""))
        out.append((cur, amt))
    return out


# --- Backwards-compatible helpers (thin wrappers) --------------------------------

def run_bean_query(journal_path: str, query: str) -> Decimal:
    """
    Legacy: execute bean-query and parse a single number from the last line.
    """
    lines = beanquery_run_lines(journal_path, query)
    return beanquery_last_scalar(lines)


def run_bean_query_rows(journal_path: str, query: str):
    """
    Legacy: execute bean-query and return cleaned table body (no headers/separators).
    """
    lines = beanquery_run_lines(journal_path, query)
    return beanquery_table_body(lines)


def parse_grouped_amounts(lines):
    """
    Legacy: wrapper for beanquery_grouped_amounts.
    """
    return beanquery_grouped_amounts(lines)
