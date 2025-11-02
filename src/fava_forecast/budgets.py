# budgets.py
import datetime
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Optional, Tuple


# -------------------------------
# Data model
# -------------------------------
@dataclass(frozen=True)
class BudgetItem:
    start: datetime.date
    account: str
    freq: str                # one of: weekly, monthly, quarterly, yearly
    amount: Decimal
    currency: str


# -------------------------------
# Constants
# -------------------------------
# Average lengths in days (Decimal for stable division)
FREQ_DAYS: Dict[str, Decimal] = {
    "weekly":    Decimal("7"),
    "monthly":   Decimal("30.4375"),
    "quarterly": Decimal("91.3125"),
    "yearly":    Decimal("365.25"),
}

_RX_BUDGET = re.compile(
    r'^(\d{4}-\d{2}-\d{2})\s+custom\s+"budget"\s+"([^"]+)"\s+"'
    r'(weekly|monthly|quarterly|yearly)"\s+([\d_]+(?:\.\d+)?)\s+([A-Z]{3,6})\s*$'
)


# -------------------------------
# Parsing
# -------------------------------
def parse_budget_line(line: str) -> Optional[BudgetItem]:
    """
    Parse a single budgets.bean line into BudgetItem.
    Returns None if line doesn't match the custom 'budget' format.
    """
    m = _RX_BUDGET.match(line.strip())
    if not m:
        return None
    start_s, account, freq, amt_s, cur = m.groups()
    start = datetime.date.fromisoformat(start_s)
    amount = Decimal(amt_s.replace("_", ""))
    return BudgetItem(start=start, account=account, freq=str(freq), amount=amount, currency=cur)


def load_budget_items(path: str) -> List[BudgetItem]:
    """
    Load all budget items from a budgets.bean file.
    Missing file -> empty list.
    """
    if not os.path.exists(path):
        return []
    items: List[BudgetItem] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            bi = parse_budget_line(line)
            if bi is not None:
                items.append(bi)
    return items


# -------------------------------
# Forecast core
# -------------------------------
def _planned_amount_in_window(item: BudgetItem, start_incl: datetime.date, end_excl: datetime.date) -> Decimal:
    """
    Evenly spread the budget amount across its period, and compute the part
    that falls into [start_incl, end_excl).

    If the window ends on or before the effective start date — returns 0.
    """
    # budgets start no earlier than their own start date
    effective_start = max(start_incl, item.start)
    if end_excl <= effective_start:
        return Decimal("0")

    days = Decimal(str((end_excl - effective_start).days))
    pd = FREQ_DAYS[item.freq]
    daily = item.amount / pd
    return daily * days


def _sum_by_currency(items: Iterable[BudgetItem], today: datetime.date, until: datetime.date) -> Dict[str, Decimal]:
    """
    Aggregate planned amounts per currency within [today, until).
    """
    by_cur: Dict[str, Decimal] = {}
    for it in items:
        planned = _planned_amount_in_window(it, today, until)
        if planned == 0:
            continue
        by_cur[it.currency] = by_cur.get(it.currency, Decimal("0")) + planned
    return by_cur


def _convert_breakdown(by_currency: Dict[str, Decimal], rates: Dict[str, Decimal]) -> Tuple[Decimal, List[Tuple[str, Decimal, Optional[Decimal], Optional[Decimal]]]]:
    """
    Convert aggregated amounts per currency using provided rates mapping.
    Returns total in op currency and a breakdown list:
      [(currency, amount_in_cur, rate_or_None, converted_or_None)]
    """
    total = Decimal("0")
    breakdown: List[Tuple[str, Decimal, Optional[Decimal], Optional[Decimal]]] = []
    for cur, amt in by_currency.items():
        rate = rates.get(cur)
        conv = (amt * rate) if rate is not None else None
        if conv is not None:
            total += conv
        breakdown.append((cur, amt, rate, conv))
    return total, breakdown


# -------------------------------
# Public API (kept name to avoid ripples)
# -------------------------------
def compute_budget_planned_expenses(
    budgets_path: str,
    today: datetime.date,
    until: datetime.date,
    rates: Dict[str, Decimal],   # currency -> rate in operating currency
    op_cur: str,                 # kept for signature compatibility; not used here
) -> Tuple[Decimal, List[Tuple[str, Decimal, Optional[Decimal], Optional[Decimal]]]]:
    """
    Read custom 'budget' entries from budgets.bean and estimate future expenses for [today, until).
    Method: evenly distribute each budget over its frequency period and sum the slice in the window.

    Returns:
      total_in_op (Decimal),
      breakdown list: [(currency, amount_in_cur, rate_or_None, converted_or_None)]
    """
    items = load_budget_items(budgets_path)
    by_currency = _sum_by_currency(items, today, until)
    total_in_op, breakdown = _convert_breakdown(by_currency, rates)
    return total_in_op, breakdown
