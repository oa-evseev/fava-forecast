import datetime as dt
from decimal import Decimal
from pathlib import Path

import fava_forecast.budgets as b


# -----------------------------
# parse_budget_line
# -----------------------------
def test_parse_budget_line_ok_weekly():
    line = '2025-01-01 custom "budget" "Expenses:Food" "weekly" 7_00 CRC'
    item = b.parse_budget_line(line)
    assert item is not None
    assert item.start == dt.date(2025, 1, 1)
    assert item.account == "Expenses:Food"
    assert item.freq == "weekly"
    assert item.amount == Decimal("700")
    assert item.currency == "CRC"


def test_parse_budget_line_ok_monthly_decimal():
    line = '2025-02-10 custom "budget" "Expenses:House" "monthly" 1234.56 USD'
    item = b.parse_budget_line(line)
    assert item is not None
    assert item.start == dt.date(2025, 2, 10)
    assert item.account == "Expenses:House"
    assert item.freq == "monthly"
    assert item.amount == Decimal("1234.56")
    assert item.currency == "USD"


def test_parse_budget_line_nonmatch_returns_none():
    assert b.parse_budget_line("garbage line") is None


# -----------------------------
# load_budget_items
# -----------------------------
def test_load_budget_items_missing_file_returns_empty(tmp_path):
    path = tmp_path / "absent.bean"
    assert b.load_budget_items(str(path)) == []


def test_load_budget_items_mixed_lines(tmp_path):
    path = tmp_path / "budgets.bean"
    path.write_text(
        "\n".join(
            [
                '2025-01-01 custom "budget" "A" "weekly" 700 CRC',
                "not a budget",
                '2025-01-10 custom "budget" "B" "monthly" 300 USD',
            ]
        ),
        encoding="utf-8",
    )
    items = b.load_budget_items(str(path))
    assert len(items) == 2
    assert items[0].account == "A"
    assert items[1].account == "B"


# -----------------------------
# _planned_amount_in_window (internal)
# -----------------------------
def test_planned_amount_zero_if_window_ends_before_start():
    it = b.BudgetItem(
        start=dt.date(2025, 1, 10),
        account="X",
        freq="weekly",
        amount=Decimal("700"),
        currency="CRC",
    )
    amt = b._planned_amount_in_window(it, dt.date(2025, 1, 1), dt.date(2025, 1, 5))
    assert amt == Decimal("0")


def test_planned_amount_partial_window_monthly():
    it = b.BudgetItem(
        start=dt.date(2025, 1, 1),
        account="X",
        freq="monthly",
        amount=Decimal("300"),
        currency="CRC",
    )
    # 10 days within window
    start, end = dt.date(2025, 1, 5), dt.date(2025, 1, 15)
    amt = b._planned_amount_in_window(it, start, end)
    # expected = 300 / 30.4375 * 10
    expected = (Decimal("300") / b.FREQ_DAYS["monthly"]) * Decimal("10")
    assert amt == expected


def test_planned_amount_respects_budget_start():
    it = b.BudgetItem(
        start=dt.date(2025, 1, 20),
        account="X",
        freq="weekly",
        amount=Decimal("700"),
        currency="CRC",
    )
    # window overlaps: only from Jan-20 to Jan-25 (5 days)
    start, end = dt.date(2025, 1, 15), dt.date(2025, 1, 25)
    amt = b._planned_amount_in_window(it, start, end)
    expected = (Decimal("700") / b.FREQ_DAYS["weekly"]) * Decimal("5")
    assert amt == expected


# -----------------------------
# _sum_by_currency (internal)
# -----------------------------
def test_sum_by_currency_aggregates_and_skips_zeros():
    items = [
        b.BudgetItem(dt.date(2025, 1, 1), "A", "weekly", Decimal("700"), "CRC"),
        b.BudgetItem(dt.date(2025, 2, 1), "B", "weekly", Decimal("0"), "CRC"),
        b.BudgetItem(dt.date(2025, 1, 1), "C", "monthly", Decimal("300"), "USD"),
    ]
    today, until = dt.date(2025, 1, 1), dt.date(2025, 1, 8)  # 7 days
    by_cur = b._sum_by_currency(items, today, until)
    # CRC: 700/7 * 7 = 700 ; USD: 300/30.4375 * 7
    assert by_cur["CRC"] == Decimal("700")
    assert by_cur["USD"] == (Decimal("300") / b.FREQ_DAYS["monthly"]) * Decimal("7")


# -----------------------------
# _convert_breakdown (internal)
# -----------------------------
def test_convert_breakdown_handles_missing_rates_and_sums_total():
    by_cur = {
        "CRC": Decimal("700"),
        "USD": Decimal("100"),
        "EUR": Decimal("50"),
    }
    rates = {
        "CRC": Decimal("1"),
        "USD": Decimal("500"),   # 1 USD = 500 CRC
        # EUR rate missing -> None
    }
    total, br = b._convert_breakdown(by_cur, rates)
    # total = 700*1 + 100*500 ; EUR excluded
    assert total == Decimal("700") + (Decimal("100") * Decimal("500"))
    # breakdown rows contain (cur, amt, rate_or_None, conv_or_None)
    row_crc = [x for x in br if x[0] == "CRC"][0]
    row_usd = [x for x in br if x[0] == "USD"][0]
    row_eur = [x for x in br if x[0] == "EUR"][0]
    assert row_crc[2] == Decimal("1") and row_crc[3] == Decimal("700")
    assert row_usd[2] == Decimal("500") and row_usd[3] == Decimal("50000")
    assert row_eur[2] is None and row_eur[3] is None


# -----------------------------
# compute_budget_planned_expenses (public)
# -----------------------------
def test_compute_budget_planned_expenses_end_to_end(tmp_path):
    p: Path = tmp_path / "budgets.bean"
    p.write_text(
        "\n".join(
            [
                '2025-01-01 custom "budget" "Food" "weekly" 700 CRC',
                '2025-01-10 custom "budget" "Rent" "monthly" 300 USD',
                "garbage",
                '2025-01-20 custom "budget" "Gym" "weekly" 14 EUR',
            ]
        ),
        encoding="utf-8",
    )
    today = dt.date(2025, 1, 15)
    until = dt.date(2025, 1, 29)  # 14 days window

    # Manually compute expected per-currency:
    # CRC: weekly 700 => daily 100 ; effective from 2025-01-15 -> 14 days => 1400
    crc_amt = Decimal("700") / b.FREQ_DAYS["weekly"] * Decimal("14")  # 100 * 14 = 1400
    # USD: monthly 300 => daily 300/30.4375 ; window 14 days => amt_usd
    usd_amt = Decimal("300") / b.FREQ_DAYS["monthly"] * Decimal("14")
    # EUR: weekly 14 starts at 2025-01-20; window overlap 9 days (20..29) => 14/7 * 9 = 18
    eur_amt = Decimal("14") / b.FREQ_DAYS["weekly"] * Decimal("9")

    rates = {"CRC": Decimal("1"), "USD": Decimal("520"), "EUR": Decimal("600")}
    total, br = b.compute_budget_planned_expenses(str(p), today, until, rates, "CRC")

    # total = CRC(1400)*1 + USD_amt*520 + EUR_amt*600
    expected_total = crc_amt * Decimal("1") + usd_amt * Decimal("520") + eur_amt * Decimal("600")
    assert total == expected_total

    # breakdown contains rows for three currencies
    got = {row[0]: row for row in br}
    assert got["CRC"][1] == crc_amt and got["CRC"][2] == Decimal("1")
    assert got["USD"][1] == usd_amt and got["USD"][2] == Decimal("520")
    assert got["EUR"][1] == eur_amt and got["EUR"][2] == Decimal("600")
