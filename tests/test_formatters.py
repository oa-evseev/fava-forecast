import pytest
from decimal import Decimal
import fava_forecast.formatters as fm


# -----------------------------
# fmt_amount
# -----------------------------

@pytest.mark.parametrize(
    "val,expected",
    [
        # positive, |val| < 0.1 → 3 significant digits (your new rule)
        (Decimal("0.001234"), "0.00123"),
        (Decimal("0.001237"), "0.00124"),
        (Decimal("0.01234"),  "0.0123"),
        (Decimal("0.01237"),  "0.0124"),
        (Decimal("0.1234"),   "0.12"),
        (Decimal("0.1274"),   "0.13"),
        # boundary (exactly 0.1 should follow standard 2-dec formatting)
        (Decimal("0.1"),      "0.10"),
    ],
)
def test_fmt_amount_small_abs_positive(val, expected):
    assert fm.fmt_amount(val) == expected


@pytest.mark.parametrize(
    "val,expected",
    [
        # negative, |val| < 0.1 → 3 significant digits (mirrors positive)
        (Decimal("-0.001234"), "-0.00123"),
        (Decimal("-0.001237"), "-0.00124"),
        (Decimal("-0.01234"),  "-0.0123"),
        (Decimal("-0.01237"),  "-0.0124"),
        (Decimal("-0.1234"),   "-0.12"),
        (Decimal("-0.1274"),   "-0.13"),
        # boundary at -0.1
        (Decimal("-0.1"),      "-0.10"),
    ],
)
def test_fmt_amount_small_abs_negative(val, expected):
    assert fm.fmt_amount(val) == expected


@pytest.mark.parametrize(
    "val,expected",
    [
        (Decimal("0"),         "0"),
        (Decimal("1234.5"),    "1 234.50"),   # thousand separators must be spaces
        (Decimal("-9876.01"),  "-9 876.01"),
    ],
)
def test_fmt_amount_thousands_and_zero(val, expected):
    assert fm.fmt_amount(val) == expected


# -----------------------------
# print_breakdown
# -----------------------------
def test_print_breakdown_with_rows_and_missing_rate(capsys):
    rows = [
        ("USD", Decimal("10"), Decimal("520"), Decimal("5200")),
        ("EUR", Decimal("5"), None, None),  # missing rate
    ]
    fm.print_breakdown(
        title="TEST",
        breakdown=rows,
        total_in_op=Decimal("5200"),
        op_cur="CRC",
        cur_width=3,
        amount_width=8,
        eq_gap=2,
        total_line_extra=10,
    )
    out = capsys.readouterr().out
    # Title and borders printed
    assert "TEST" in out
    # USD row has converted value
    assert "USD" in out and "5 200.00 CRC" in out
    # EUR row shows (no rate)
    assert "(no rate)" in out
    # TOTAL line present
    assert "TOTAL" in out and "5 200.00 CRC" in out


def test_print_breakdown_empty_rows(capsys):
    fm.print_breakdown(
        title="EMPTY",
        breakdown=[],
        total_in_op=Decimal("0"),
        op_cur="USD",
    )
    out = capsys.readouterr().out
    # Should print header and TOTAL even for empty input
    assert "EMPTY" in out
    assert "TOTAL" in out
    assert "USD" in out
