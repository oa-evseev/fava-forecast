import os
import pytest
from decimal import Decimal

import fava_forecast.beancount_io as io


# -----------------------------
# beanquery_run_lines
# -----------------------------
def test_run_lines_ok_trims_and_filters(monkeypatch, tmp_path):
    j = tmp_path / "main.bean"
    j.write_text("", encoding="utf-8")

    out = "\n  Currency  Sum  \n\nUSD 10.00 USD\n  \nCRC  1_000.00 CRC\n"
    monkeypatch.setattr(io.subprocess, "check_output", lambda cmd, text=True: out)

    lines = io.beanquery_run_lines(str(j), "SELECT 1")
    assert lines == ["Currency  Sum", "USD 10.00 USD", "CRC  1_000.00 CRC"]


def test_run_lines_missing_journal_raises():
    with pytest.raises(FileNotFoundError):
        io.beanquery_run_lines("nope.bean", "Q")


def test_run_lines_subprocess_error_raises(monkeypatch, tmp_path):
    j = tmp_path / "main.bean"
    j.write_text("", encoding="utf-8")

    class E(io.subprocess.CalledProcessError):
        def __init__(self): super().__init__(1, "bean-query")

    def boom(cmd, text=True): raise E()

    monkeypatch.setattr(io.subprocess, "check_output", boom)
    with pytest.raises(RuntimeError):
        io.beanquery_run_lines(str(j), "Q")


# -----------------------------
# beanquery_table_body
# -----------------------------
def test_table_body_filters_headers_separators_and_totals():
    lines = [
        "Currency  Sum",
        "──────────────",
        "USD     10.00 USD",
        "CRC 1_000.00 CRC",
        "=====+-----",
        "total  123",
        "Sum    123",
    ]
    body = io.beanquery_table_body(lines)
    assert body == ["USD     10.00 USD", "CRC 1_000.00 CRC"]


def test_table_body_empty_input():
    assert io.beanquery_table_body([]) == []


# -----------------------------
# beanquery_grouped_amounts
# -----------------------------
def test_grouped_amounts_parses_valid_and_skips_invalid():
    body = [
        "USD     10.00 USD",
        "CRC 1_000.00 CRC",
        "EUR -9,876.01 EUR",
        "BAD not_a_number USD",  # skip
        "GBP  12.3",             # skip
    ]
    rows = io.beanquery_grouped_amounts(body)
    assert rows == [
        ("USD", Decimal("10.00")),
        ("CRC", Decimal("1000.00")),
        ("EUR", Decimal("-9876.01")),
    ]


# -----------------------------
# beanquery_grouped_amounts_from_journal
# -----------------------------
def test_grouped_amounts_from_journal_pipeline(monkeypatch, tmp_path):
    j = tmp_path / "main.bean"
    j.write_text("", encoding="utf-8")

    fake = "\n".join(
        [
            "Currency  Sum",
            "──────────────",
            "USD     10.00 USD",
            "CRC 1_000.00 CRC",
            "sum total",
        ]
    )
    monkeypatch.setattr(io.subprocess, "check_output", lambda cmd, text=True: fake)

    rows = io.beanquery_grouped_amounts_from_journal(str(j), "SELECT currency, sum(position) GROUP BY currency")
    assert rows == [("USD", Decimal("10.00")), ("CRC", Decimal("1000.00"))]
