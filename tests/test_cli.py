import sys
from decimal import Decimal
import fava_forecast.cli as cli
import fava_forecast.forecast as forecast

def _run_main_with_args(args, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"] + args)
    cli.main()
    return capsys.readouterr().out


def test_cli_main_summary(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    today = "2025-01-10"
    until = "2025-01-20"

    monkeypatch.setattr(forecast, "load_prices_to_op", lambda *_: {"CRC": Decimal("1"), "USD": Decimal("500")})
    monkeypatch.setattr(forecast, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")

    def fake_run_grouped_rows(_journal, query, messages=None):
        if "^Assets" in query:
            return [("CRC", Decimal("2000")), ("USD", Decimal("2"))]
        if "^Liabilities" in query:
            return [("CRC", Decimal("-100"))]
        if "^Income" in query:
            return [("USD", Decimal("-1"))]
        if "^Expenses" in query:
            return [("CRC", Decimal("300"))]
        raise AssertionError("Unexpected query")

    monkeypatch.setattr(forecast, "run_grouped_rows", fake_run_grouped_rows)
    monkeypatch.setattr(forecast, "compute_budget_planned_expenses",
        lambda *_: (Decimal("200"), [("CRC", Decimal("200"), Decimal("1"), Decimal("200"))])
    )

    out = _run_main_with_args(
        [
            "--journal", str(j),
            "--budgets", str(b),
            "--prices", str(p),
            "--until", until,
            "--today", today,
        ],
        monkeypatch,
        capsys,
    )

    print("\n\n\n\n")
    print(out)
    print("\n\n\n\n")

    assert "Assets:" in out and "3 000.00 CRC" in out     # 2000 CRC + 2 USD * 500 = 3000
    assert "Net now (Assets - Liabilities):" in out and "2 900.00 CRC" in out  # 3000 + (-100) = 2900
    assert "Planned income in range:" in out and "500.00 CRC" in out
    assert "Planned budget expenses:" in out and "200.00 CRC" in out
    assert "Forecast end balance:" in out and "2 900.00 CRC" in out  # 2900 + 500 - (300+200) = 2900

    for header in [
        "ASSETS breakdown:",
        "LIABILITIES breakdown:",
        "PLANNED INCOME breakdown:",
        "PLANNED EXPENSES breakdown:",
        "BUDGETED EXPENSES breakdown (forecast):",
    ]:
        assert header not in out


def test_cli_main_verbose(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    today = "2025-01-10"
    until = "2025-01-20"

    monkeypatch.setattr(forecast, "load_prices_to_op", lambda *_: {"CRC": Decimal("1"), "USD": Decimal("500")})
    monkeypatch.setattr(forecast, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")

    def fake_run_grouped_rows(_journal, query, messages=None):
        if "^Assets" in query:
            return [("USD", Decimal("1"))]  # -> 500
        if "^Liabilities" in query:
            return [("CRC", Decimal("-50"))]
        if "^Income" in query:
            return [("USD", Decimal("-1"))]
        if "^Expenses" in query:
            return [("CRC", Decimal("100"))]
        raise AssertionError("Unexpected query")

    monkeypatch.setattr(forecast, "run_grouped_rows", fake_run_grouped_rows)
    monkeypatch.setattr(forecast, "compute_budget_planned_expenses",
        lambda *_: (Decimal("200"), [("CRC", Decimal("200"), Decimal("1"), Decimal("200"))])
    )

    out = _run_main_with_args(
        [
            "--journal", str(j),
            "--budgets", str(b),
            "--prices", str(p),
            "--until", until,
            "--today", today,
            "--verbose",
        ],
        monkeypatch,
        capsys,
    )

    for header in [
        "ASSETS breakdown:",
        "LIABILITIES breakdown:",
        "PLANNED INCOME breakdown:",
        "PLANNED EXPENSES breakdown:",
        "BUDGETED EXPENSES breakdown (forecast):",
    ]:
        assert header in out

    assert "Net now (Assets - Liabilities):" in out and "450.00 CRC" in out
    assert "Forecast end balance:" in out and "650.00 CRC" in out


def test_cli_main_with_future_warning(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    # mock run_forecast to ensure CLI prints past_future block
    def fake_run_forecast(**kwargs):
        return {
            "op_currency": "CRC",
            "assets": (Decimal("100"), []),
            "liabs": (Decimal("0"), []),
            "planned_income": (Decimal("0"), []),
            "planned_expenses": (Decimal("0"), []),
            "planned_budget_exp": (Decimal("0"), []),
            "net_now": Decimal("100"),
            "forecast_end": Decimal("100"),
            "ok": True,
            "verbose": False,
            "past_future": ["2025-01-05 * \"Planned rent\" \"\""],
        }

    monkeypatch.setattr(cli, "run_forecast", fake_run_forecast)
    monkeypatch.setattr(cli, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")
    monkeypatch.setattr(cli, "load_prices_to_op", lambda *_: {"CRC": Decimal("1")})

    out = _run_main_with_args(
        [
            "--journal", str(j),
            "--budgets", str(b),
            "--prices", str(p),
            "--until", "2025-01-20",
            "--today", "2025-01-10",
            "--future", str(tmp_path / "future.bean"),
        ],
        monkeypatch,
        capsys,
    )

    assert "WARNING: the following planned entries are in the past" in out
    assert "Planned rent" in out


def test_cli_main_with_future_no_warning(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    def fake_run_forecast(**kwargs):
        return {
            "op_currency": "CRC",
            "assets": (Decimal("100"), []),
            "liabs": (Decimal("0"), []),
            "planned_income": (Decimal("0"), []),
            "planned_expenses": (Decimal("0"), []),
            "planned_budget_exp": (Decimal("0"), []),
            "net_now": Decimal("100"),
            "forecast_end": Decimal("100"),
            "ok": True,
            "verbose": False,
            "past_future": [],
        }

    monkeypatch.setattr(cli, "run_forecast", fake_run_forecast)
    monkeypatch.setattr(cli, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")
    monkeypatch.setattr(cli, "load_prices_to_op", lambda *_: {"CRC": Decimal("1")})

    out = _run_main_with_args(
        [
            "--journal", str(j),
            "--budgets", str(b),
            "--prices", str(p),
            "--until", "2025-01-20",
            "--today", "2025-01-10",
            "--future", str(tmp_path / "future.bean"),
        ],
        monkeypatch,
        capsys,
    )

    assert "WARNING: the following planned entries are in the past" not in out

def test_cli_prints_messages(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    def fake_run_forecast(**kwargs):
        return {
            "op_currency": "CRC",
            "assets": (Decimal("0"), []),
            "liabs": (Decimal("0"), []),
            "planned_income": (Decimal("0"), []),
            "planned_expenses": (Decimal("0"), []),
            "planned_budget_exp": (Decimal("0"), []),
            "net_now": Decimal("0"),
            "forecast_end": Decimal("0"),
            "ok": True,
            "verbose": False,
            "past_future": [],
            "messages": [
                {
                    "level": "warning",
                    "code": "future-missing-accounts",
                    "text": "Future journal was provided but accounts file is missing; skipped.",
                }
            ],
        }

    monkeypatch.setattr(cli, "run_forecast", fake_run_forecast)
    monkeypatch.setattr(cli, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")
    monkeypatch.setattr(cli, "load_prices_to_op", lambda *_: {"CRC": Decimal("1")})

    out = _run_main_with_args(
        [
            "--journal", str(j),
            "--budgets", str(b),
            "--prices", str(p),
            "--until", "2025-01-20",
            "--today", "2025-01-10",
            "--future", str(tmp_path / "future.bean"),
        ],
        monkeypatch,
        capsys,
    )

    assert "[WARNING] future-missing-accounts:" in out

def test_cli_passes_accounts(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    a = tmp_path / "accounts.bean"
    for f in (j, b, p, a):
        f.write_text("", encoding="utf-8")

    captured = {}

    def fake_run_forecast(**kwargs):
        captured.update(kwargs)
        return {
            "op_currency": "CRC",
            "assets": (Decimal("0"), []),
            "liabs": (Decimal("0"), []),
            "planned_income": (Decimal("0"), []),
            "planned_expenses": (Decimal("0"), []),
            "planned_budget_exp": (Decimal("0"), []),
            "net_now": Decimal("0"),
            "forecast_end": Decimal("0"),
            "ok": True,
            "verbose": False,
            "past_future": [],
            "messages": [],
        }

    monkeypatch.setattr(cli, "run_forecast", fake_run_forecast)
    monkeypatch.setattr(cli, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")
    monkeypatch.setattr(cli, "load_prices_to_op", lambda *_: {"CRC": Decimal("1")})

    _run_main_with_args(
        [
            "--journal", str(j),
            "--budgets", str(b),
            "--prices", str(p),
            "--until", "2025-01-20",
            "--today", "2025-01-10",
            "--future", str(tmp_path / "future.bean"),
            "--accounts", str(a),
        ],
        monkeypatch,
        capsys,
    )

    assert captured["accounts"] == str(a)
