# formatters.py
from decimal import Decimal, ROUND_HALF_UP


def _fmt_amount(val: Decimal) -> str:
    if val == 0:
        return "0"
    absval = abs(val)
    if absval < Decimal("0.01"):
        digits = f"{val:.3g}"
    else:
        digits = f"{val.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return digits.replace(",", " ")


def print_breakdown(
    title: str,
    breakdown,
    total_in_op: Decimal,
    op_cur: str,
    *,
    cur_width: int = 5,
    amount_width: int = 15,
    gap_after_amount: int = 2,
    eq_gap: int = 3,
    total_line_extra: int = 21,
):
    # compute left width till "="
    left_width = max(
        len(f"{cur:>{cur_width}}  {_fmt_amount(amt):>{amount_width}} {cur:<{cur_width}}")
        for cur, amt, _, _ in breakdown
    )
    eq_col = left_width + eq_gap
    line = "-" * (eq_col + total_line_extra)
    border = "=" * (eq_col + total_line_extra)

    print(border)
    print(title)
    print(border)
    for cur, amt, rate, conv in breakdown:
        left = f"{cur:>{cur_width}}  {_fmt_amount(amt):>{amount_width}} {cur:<{cur_width}}"
        if rate is None:
            print(f"{left:<{eq_col}}= (no rate)")
        else:
            right_val = _fmt_amount(conv.quantize(Decimal('0.01'))) if conv is not None else "-"
            print(f"{left:<{eq_col}}= {right_val:>15} {op_cur}")

    total_fmt = _fmt_amount(total_in_op.quantize(Decimal('0.01')))
    print(line)
    print(f"{'TOTAL':<{eq_col-1}}-> {total_fmt:>15} {op_cur}")
    print(border)
    print()

