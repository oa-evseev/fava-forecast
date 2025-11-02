import datetime as dt
from decimal import Decimal
import os
import pytest

import fava_forecast.rates as r
from fava_forecast.errors import PriceParseError


# -----------------------------
# _parse_price_line
# -----------------------------
def test_parse_price_line_ok_multi_underscores():
    line = "2025-03-01 price GOLD 1_234_567.89 CRC"
    d, base, val, quote = r._parse_price_line(line)
    assert d == dt.date(2025, 3, 1)
    assert base == "GOLD"
    assert val == Decimal("1234567.89")
    assert quote == "CRC"


def test_parse_price_line_ok_tabs_spaces():
    line = "2025-03-02\tprice\tEUR\t12_345.00\tCRC"
    d, base, val, quote = r._parse_price_line(line)
    assert d == dt.date(2025, 3, 2)
    assert base == "EUR"
    assert val == Decimal("12345.00")
    assert quote == "CRC"


def test_parse_price_line_ok_base_with_digits():
    line = "2025-03-03 price XBT0 1_000 USD"
    d, base, val, quote = r._parse_price_line(line)
    assert d == dt.date(2025, 3, 3)
    assert base == "XBT0"
    assert val == Decimal("1000")
    assert quote == "USD"


# --- invalid number → raises PriceParseError ---

def test_parse_price_line_bad_number_underscore_only_raises():
    with pytest.raises(PriceParseError):
        r._parse_price_line("2025-04-01 price USD _ CRC")


def test_parse_price_line_bad_number_letters_raises():
    with pytest.raises(PriceParseError):
        r._parse_price_line("2025-04-02 price USD X_Y CRC")


def test_parse_price_line_bad_number_dot_only_raises():
    with pytest.raises(PriceParseError):
        r._parse_price_line("2025-04-03 price USD . CRC")


def test_parse_price_line_bad_number_misplaced_underscore_raises():
    with pytest.raises(PriceParseError):
        r._parse_price_line("2025-04-04 price USD 1._23 CRC")


def test_parse_price_line_bad_number_multiple_dots_raises():
    with pytest.raises(PriceParseError):
        r._parse_price_line("2025-04-05 price USD 1.2.3 CRC")


# -----------------------------
# _select_last_rate
# -----------------------------
def test_select_last_rate_empty():
    assert r._select_last_rate([], dt.date(2025, 1, 1)) is None


def test_select_last_rate_only_future():
    pairs = [(dt.date(2030, 1, 1), Decimal("1.1"))]
    assert r._select_last_rate(pairs, dt.date(2025, 1, 1)) is None


def test_select_last_rate_mixed_picks_last_leq_today():
    pairs = [
        (dt.date(2025, 1, 1), Decimal("1.0")),
        (dt.date(2025, 1, 10), Decimal("1.5")),
        (dt.date(2025, 2, 1), Decimal("2.0")),
    ]
    assert r._select_last_rate(pairs, dt.date(2025, 1, 15)) == Decimal("1.5")


# -----------------------------
# load_prices_to_op
# -----------------------------
def _write_prices(tmp_path, lines):
    p = tmp_path / "prices.bean"
    p.write_text("\n".join(lines), encoding="utf-8")
    return str(p)


def test_load_prices_missing_file_returns_empty(tmp_path):
    path = os.path.join(str(tmp_path), "absent.bean")
    got = r.load_prices_to_op(path, "CRC", dt.date(2025, 1, 1))
    assert got == {}


def test_load_prices_direct_and_identity(tmp_path):
    lines = [
        "2024-12-31 price EUR 600.00 CRC",   # older
        "2025-01-05 price EUR 650.00 CRC",   # latest <= today
        "2025-01-10 price JPY 0.0035 CRC",
        "2026-01-01 price EUR 700.00 CRC",   # future, must be ignored
        "garbage",
    ]
    path = _write_prices(tmp_path, lines)
    rates = r.load_prices_to_op(path, "CRC", dt.date(2025, 1, 20))
    assert rates["CRC"] == Decimal("1")
    assert rates["EUR"] == Decimal("650.00")
    assert rates["JPY"] == Decimal("0.0035")
    assert "garbage" not in rates


def test_load_prices_indirect_via_usd(tmp_path):
    lines = [
        # USD -> CRC
        "2025-01-01 price USD 500.00 CRC",
        "2025-01-10 price USD 520.00 CRC",  # latest
        # BTC -> USD
        "2025-01-05 price BTC 2.00 USD",
        "2025-01-20 price BTC 3.00 USD",  # beyond today -> ignored
        # ETH -> USD (no USD->CRC -> should NOT appear)
        "2025-01-07 price ETH 1000.00 USD",
    ]
    path = _write_prices(tmp_path, lines)
    today = dt.date(2025, 1, 15)
    rates = r.load_prices_to_op(path, "CRC", today)
    # BTC->USD (2.00) * USD->CRC (520) = 1040
    assert rates["BTC"] == Decimal("1040")
    # ETH must be absent because conversion USD->CRC exists, but ETH->USD exists too;
    # However both exist => actually ETH should also be present (2-hop). Verify:
    assert rates["ETH"] == Decimal("1000") * Decimal("520")


def test_load_prices_indirect_skipped_if_no_usd_to_op(tmp_path):
    # No USD->CRC; via_usd entries must not be used.
    lines = [
        "2025-01-05 price BTC 2.00 USD",
        "2025-01-07 price ETH 1000.00 USD",
    ]
    path = _write_prices(tmp_path, lines)
    rates = r.load_prices_to_op(path, "CRC", dt.date(2025, 1, 10))
    assert "BTC" not in rates
    assert "ETH" not in rates


def test_load_prices_prefers_latest_leq_today(tmp_path):
    lines = [
        "2025-01-01 price USD 500.00 CRC",
        "2025-01-20 price USD 530.00 CRC",  # future w.r.t today(1/10) -> ignore
        "2025-01-05 price EUR 600.00 CRC",
        "2025-01-15 price EUR 700.00 CRC",  # future -> ignore
    ]
    path = _write_prices(tmp_path, lines)
    today = dt.date(2025, 1, 10)
    rates = r.load_prices_to_op(path, "CRC", today)
    assert rates["USD"] == Decimal("500.00")
    assert rates["EUR"] == Decimal("600.00")
