# tests/test_fava_ext.py
import datetime as dt
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

import pytest
from flask import Flask

import fava_forecast.fava_ext as fx


class _LedgerStub:
    """Minimal ledger stub that mimics Fava's ledger attributes used by the extension."""

    def __init__(self, journal_path: str):
        self.beancount_file_path = journal_path
        self.options = {"filename": journal_path}


def _mk_core_result(
    *,
    cur: str = "CRC",
    today: str = "2025-01-10",
    until: str = "2025-01-20",
    assets_total: Decimal = Decimal("100"),
    liabs_total: Decimal = Decimal("-20"),
    inc: Decimal = Decimal("50"),
    exp: Decimal = Decimal("10"),
    budg: Decimal = Decimal("5"),
) -> Dict[str, Any]:
    """Build a fake result dict returned by run_forecast()."""
    return {
        "op_currency": cur,
        "today": dt.date.fromisoformat(today),
        "until": dt.date.fromisoformat(until),
        "assets": (assets_total, [("CRC", assets_total, Decimal("1"), assets_total)]),
        "liabs": (liabs_total, [("CRC", liabs_total, Decimal("1"), liabs_total)]),
        "planned_income": (inc, [("CRC", inc, Decimal("1"), inc)]),
        "planned_expenses": (exp, [("CRC", exp, Decimal("1"), exp)]),
        "planned_budget_exp": (budg, [("CRC", budg, Decimal("1"), budg)]),
        "net_now": assets_total + liabs_total,
        "forecast_end": assets_total + liabs_total + inc - (exp + budg),
        "ok": True,
        "verbose": False,
        "past_future": [],
    }


def test_parse_config_variants():
    # Empty and None
    assert fx._parse_config(None) == {}
    assert fx._parse_config("") == {}
    # Spacing and multiple keys
    cfg = fx._parse_config("currency=USD,  budgets=/a/b/c,prices=/x/y/z ,  foo = bar ")
    assert cfg == {
        "currency": "USD",
        "budgets": "/a/b/c",
        "prices": "/x/y/z",
        "foo": "bar",
    }
    # Lone tokens should be ignored
    assert fx._parse_config("abc, x=1, y=2") == {"x": "1", "y": "2"}


def test_fmt_delegates_to_fmt_amount(monkeypatch):
    called = {}

    def fake_fmt_amount(x):
        called["v"] = x
        return "OK"

    monkeypatch.setattr(fx, "fmt_amount", fake_fmt_amount)
    ext = fx.BudgetForecast(_LedgerStub("/tmp/main.bean"))
    assert ext.fmt(Decimal("1.23")) == "OK"
    assert called["v"] == Decimal("1.23")


def test_data_defaults_and_values(tmp_path, monkeypatch):
    # Prepare a real journal path (so default budgets/prices are derived correctly)
    journal_dir = tmp_path / "ledger"
    journal_dir.mkdir()
    journal_path = journal_dir / "main.bean"
    journal_path.write_text("", encoding="utf-8")

    # Fake run_forecast
    def fake_run_forecast(**kwargs):
        # Assert defaults are passed in as absolute paths derived from journal dir
        assert Path(kwargs["budgets"]) == journal_dir / "budgets.bean"
        assert Path(kwargs["prices"]) == journal_dir / "prices.bean"
        # Assert default currency if not provided by config or query
        assert kwargs["currency"] == "CRC"
        return _mk_core_result()

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(_LedgerStub(str(journal_path)), config=None)

    # No query params -> defaults kick in
    with app.test_request_context(path="/extension/budget-forecast/"):
        data = ext.data()

    # Basic structure checks
    assert data["operating_currency"] == "CRC"
    assert str(data["today"]) == "2025-01-10"
    assert str(data["until"]) == "2025-01-20"
    assert data["paths"]["budgets"].endswith("budgets.bean")
    assert data["paths"]["prices"].endswith("prices.bean")
    assert isinstance(data["summary"]["assets"], Decimal)
    assert isinstance(data["breakdowns"]["assets"], list)


def test_query_params_override_and_cache(tmp_path, monkeypatch):
    # Journal file
    d = tmp_path / "l"
    d.mkdir()
    jpath = d / "main.bean"
    jpath.write_text("", encoding="utf-8")

    calls = {"n": 0}

    def fake_run_forecast(**kwargs):
        calls["n"] += 1
        # Pass through params to verify cache keys later
        return _mk_core_result(
            today=kwargs["today"],
            until=kwargs["until"],
            cur=kwargs["currency"],
        )

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(_LedgerStub(str(jpath)))

    # First request -> should call run_forecast once
    with app.test_request_context("/extension/budget-forecast/?until=2026-05-01&today=2026-04-01&currency=USD&verbose=1"):
        data1 = ext.data()
    assert calls["n"] == 1
    assert str(data1["until"]) == "2026-05-01"
    assert str(data1["today"]) == "2026-04-01"
    assert data1["operating_currency"] == "USD"
    assert data1["verbose"] is True

    # Second request with identical params -> served from cache (no extra call)
    with app.test_request_context("/extension/budget-forecast/?until=2026-05-01&today=2026-04-01&currency=USD&verbose=1"):
        data2 = ext.data()
    assert calls["n"] == 1
    assert data2 is data1  # same dict object from cache

    # Third request with changed param -> invalidates cache (extra call)
    with app.test_request_context("/extension/budget-forecast/?until=2026-06-01&today=2026-04-01&currency=USD&verbose=1"):
        data3 = ext.data()
    assert calls["n"] == 2
    assert str(data3["until"]) == "2026-06-01"


def test_config_defaults_used_when_no_query(tmp_path, monkeypatch):
    # Journal
    base = tmp_path / "acc"
    base.mkdir()
    (base / "main.bean").write_text("", encoding="utf-8")

    # run_forecast: check that config defaults are passed when no query params
    def fake_run_forecast(**kwargs):
        assert kwargs["currency"] == "EUR"
        assert kwargs["budgets"] == "/custom/budgets.bean"
        assert kwargs["prices"] == "/custom/prices.bean"
        return _mk_core_result(cur="EUR")

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(
        _LedgerStub(str(base / "main.bean")),
        config="currency=EUR, budgets=/custom/budgets.bean, prices=/custom/prices.bean",
    )

    with app.test_request_context("/extension/budget-forecast/"):
        data = ext.data()

    assert data["operating_currency"] == "EUR"
    assert data["paths"]["budgets"] == "/custom/budgets.bean"
    assert data["paths"]["prices"] == "/custom/prices.bean"


def test_query_overrides_config(tmp_path, monkeypatch):
    # Journal
    base = tmp_path / "acc2"
    base.mkdir()
    (base / "main.bean").write_text("", encoding="utf-8")

    captured: Dict[str, Any] = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return _mk_core_result(cur=kwargs["currency"], today=kwargs["today"], until=kwargs["until"])

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    # Config sets defaults
    ext = fx.BudgetForecast(
        _LedgerStub(str(base / "main.bean")),
        config="currency=EUR, budgets=/cfg/budgets.bean, prices=/cfg/prices.bean",
    )

    # Query overrides all three
    with app.test_request_context(
        "/extension/budget-forecast/?currency=USD&budgets=/q/b.bean&prices=/q/p.bean&today=2026-01-02&until=2026-01-15"
    ):
        data = ext.data()

    assert captured["currency"] == "USD"
    assert captured["budgets"] == "/q/b.bean"
    assert captured["prices"] == "/q/p.bean"
    assert captured["today"] == "2026-01-02"
    assert captured["until"] == "2026-01-15"
    assert data["operating_currency"] == "USD"


def test_future_default_path_from_journal(tmp_path, monkeypatch):
    base = tmp_path / "ledger"
    base.mkdir()
    jpath = base / "main.bean"
    jpath.write_text("", encoding="utf-8")

    captured = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return _mk_core_result()

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(_LedgerStub(str(jpath)), config=None)

    with app.test_request_context("/extension/budget-forecast/"):
        data = ext.data()

    assert Path(captured["future_journal"]) == base / "future.bean"
    assert data["paths"]["future"].endswith("future.bean")


def test_future_from_config(tmp_path, monkeypatch):
    base = tmp_path / "ledger2"
    base.mkdir()
    (base / "main.bean").write_text("", encoding="utf-8")

    captured = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return _mk_core_result()

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(
        _LedgerStub(str(base / "main.bean")),
        config="future=/cfg/future.bean, currency=CRC",
    )

    with app.test_request_context("/extension/budget-forecast/"):
        data = ext.data()

    assert captured["future_journal"] == "/cfg/future.bean"
    assert data["paths"]["future"] == "/cfg/future.bean"


def test_future_query_overrides_config(tmp_path, monkeypatch):
    base = tmp_path / "ledger3"
    base.mkdir()
    (base / "main.bean").write_text("", encoding="utf-8")

    captured = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return _mk_core_result()

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(
        _LedgerStub(str(base / "main.bean")),
        config="future=/cfg/future.bean",
    )

    with app.test_request_context("/extension/budget-forecast/?future=/q/future.bean"):
        data = ext.data()

    assert captured["future_journal"] == "/q/future.bean"
    assert data["paths"]["future"] == "/q/future.bean"

def test_accounts_default_path_from_journal(tmp_path, monkeypatch):
    base = tmp_path / "ledger_acc"
    base.mkdir()
    jpath = base / "main.bean"
    jpath.write_text("", encoding="utf-8")

    captured = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return _mk_core_result()

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(_LedgerStub(str(jpath)), config=None)

    with app.test_request_context("/extension/budget-forecast/"):
        data = ext.data()

    assert Path(captured["accounts"]) == base / "accounts.bean"
    assert data["paths"]["accounts"].endswith("accounts.bean")

def test_accounts_from_config(tmp_path, monkeypatch):
    base = tmp_path / "ledger_acc2"
    base.mkdir()
    (base / "main.bean").write_text("", encoding="utf-8")

    captured = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return _mk_core_result()

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(
        _LedgerStub(str(base / "main.bean")),
        config="accounts=/cfg/accounts.bean",
    )

    with app.test_request_context("/extension/budget-forecast/"):
        data = ext.data()

    assert captured["accounts"] == "/cfg/accounts.bean"
    assert data["paths"]["accounts"] == "/cfg/accounts.bean"

def test_messages_passed_through(tmp_path, monkeypatch):
    base = tmp_path / "ledger_acc3"
    base.mkdir()
    (base / "main.bean").write_text("", encoding="utf-8")

    def fake_run_forecast(**kwargs):
        res = _mk_core_result()
        res["messages"] = [
            {"level": "warning", "code": "future-missing-accounts", "text": "…"}
        ]
        return res

    monkeypatch.setattr(fx, "run_forecast", fake_run_forecast)

    app = Flask(__name__)
    ext = fx.BudgetForecast(_LedgerStub(str(base / "main.bean")))

    with app.test_request_context("/extension/budget-forecast/"):
        data = ext.data()

    assert data["messages"][0]["code"] == "future-missing-accounts"
