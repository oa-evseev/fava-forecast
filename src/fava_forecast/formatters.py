# formatters.py
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Tuple, Optional

BreakdownRow = Tuple[str, Decimal, Optional[Decimal], Optional[Decimal]]


def fmt_amount(val: Decimal) -> str:
    """
    Human-friendly decimal formatting:
      - 0 -> "0"
      - |val| < 1 -> 3 significant digits
      - otherwise -> 2 decimals with thousand separators (spaces)
    """
    if val == 0:
        return "0"
    if abs(val) < Decimal("0.1"):
        return f"{val:.3g}"
    return f"{val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}".replace(",", " ")


def print_breakdown(
    title: str,
    breakdown: Iterable[BreakdownRow],
    total_in_op: Decimal,
    op_cur: str,
    *,
    cur_width: int = 5,
    amount_width: int = 15,
    eq_gap: int = 3,
    total_line_extra: int = 21,
) -> None:
    """
    Pretty-print a currency breakdown:
      (CUR, amount_in_cur, rate_or_None, converted_or_None)
    """
    rows: List[BreakdownRow] = list(breakdown)

    # Compute left column width safely (empty breakdown -> minimal width)
    if rows:
        left_width = max(
            len(f"{cur:>{cur_width}}  {fmt_amount(amt):>{amount_width}} {cur:<{cur_width}}")
            for cur, amt, _, _ in rows
        )
    else:
        left_width = cur_width + 2 + amount_width + 1 + cur_width

    eq_col = left_width + eq_gap
    line = "-" * (eq_col + total_line_extra)
    border = "=" * (eq_col + total_line_extra)

    print(border)
    print(title)
    print(border)

    for cur, amt, rate, conv in rows:
        left = f"{cur:>{cur_width}}  {fmt_amount(amt):>{amount_width}} {cur:<{cur_width}}"
        if rate is None or conv is None:
            print(f"{left:<{eq_col}}= (no rate)")
        else:
            right_val = fmt_amount(conv.quantize(Decimal("0.01")))
            print(f"{left:<{eq_col}}= {right_val:>15} {op_cur}")

    total_fmt = fmt_amount(total_in_op.quantize(Decimal("0.01")))
    print(line)
    print(f"{'TOTAL':<{eq_col-1}}-> {total_fmt:>15} {op_cur}")
    print(border)
    print()
