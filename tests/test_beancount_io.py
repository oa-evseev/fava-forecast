import pytest
from decimal import Decimal

import fava_forecast.beancount_io as io
from fava_forecast.errors import BeanQueryError


# -------------------------
# beanquery_run_lines
# -------------------------
def test_run_lines_trims_and_drops_empty(monkeypatch):
    out = "\n  a  \n\nb\n"
    monkeypatch.setattr(
        io.subprocess, "check_output", lambda cmd, text=True: out
    )
    lines = io.beanquery_run_lines("journal.bean", "SELECT 1")
    assert lines == ["a", "b"]


# -------------------------
# beanquery_last_scalar
# -------------------------
@pytest.mark.parametrize(
    "line,expected",
    [
        ("123", Decimal("123")),
        ("+1_234.50", Decimal("1234.50")),
        ("-9,876.01", Decimal("-9876.01")),
        ("foo 42 bar", Decimal("42")),
    ],
)
def test_last_scalar_ok(line, expected):
    assert io.beanquery_last_scalar(["x", line]) == expected


def test_last_scalar_no_lines():
    with pytest.raises(BeanQueryError):
        io.beanquery_last_scalar([])


def test_last_scalar_no_number():
    with pytest.raises(BeanQueryError):
        io.beanquery_last_scalar(["only text"])


# -------------------------
# beanquery_table_body
# -------------------------
def test_table_body_removes_headers_and_borders():
    src = [
        "Currency  Sum",            # header
        "──────────────",           # border
        "USD     10.00 USD",
        "CRC 1_000.00 CRC",
        "=====+----",               # trash
        "sum     total",            # footer-like
        "EUR   5,000 EUR",
    ]
    body = io.beanquery_table_body(src)
    assert body == ["USD     10.00 USD", "CRC 1_000.00 CRC", "EUR   5,000 EUR"]


# -------------------------
# beanquery_grouped_amounts
# -------------------------
def test_grouped_amounts_parses_rows_and_skips_headers():
    rows = [
        "curr    sum(position)",
        "USD     10.00 USD",
        "CRC 1_000.00 CRC",
        "EUR   5,000 EUR",
        "BAD   not_a_number USD",   # should be skipped
    ]
    parsed = io.beanquery_grouped_amounts(rows)
    assert parsed == [
        ("USD", Decimal("10.00")),
        ("CRC", Decimal("1000.00")),
        ("EUR", Decimal("5000")),
    ]


# -------------------------
# Integration-ish check: run_lines -> table_body -> grouped_amounts
# -------------------------
def test_pipeline_runlines_tablebody_grouped(monkeypatch):
    fake = "\n".join(
        [
            "Currency  Sum",
            "──────────────",
            "USD     10.00 USD",
            "CRC 1_000.00 CRC",
            "sum total",
        ]
    )
    monkeypatch.setattr(
        io.subprocess, "check_output", lambda cmd, text=True: fake
    )
    lines = io.beanquery_run_lines("j.bean", "Q")
    body = io.beanquery_table_body(lines)
    grouped = io.beanquery_grouped_amounts(body)
    assert grouped == [
        ("USD", Decimal("10.00")),
        ("CRC", Decimal("1000.00")),
    ]
