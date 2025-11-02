import sys
import datetime as dt
from decimal import Decimal

import fava_forecast.cli as cli


def _run_main_with_args(args, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"] + args)
    cli.main()
    return capsys.readouterr().out


def test_cli_main_summary(monkeypatch, capsys, tmp_path):
    # --- fixtures (empty files just to satisfy argparse paths)
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    today = "2025-01-10"
    until = "2025-01-20"

    # rates
    monkeypatch.setattr(cli, "load_prices_to_op", lambda prices, cur, t: {"CRC": Decimal("1"), "USD": Decimal("500")})
    # operating currency detection (used if --currency not provided or equals 'CRC')
    monkeypatch.setattr(cli, "detect_operating_currency_from_journal", lambda *_args, **_kw: "CRC")

    # grouped rows: return per-query data
    def fake_run_grouped_rows(_journal, query):
        if "^Assets" in query:
            return [("CRC", Decimal("1000")), ("USD", Decimal("2"))]  # 1000*1 + 2*500 = 2000
        if "^Liabilities" in query:
            return [("CRC", Decimal("-100"))]  # -100
        if "^Income" in query:
            return [("USD", Decimal("-1"))]  # will flip to +1 -> 1*500 = 500
        if "^Expenses" in query:
            return [("CRC", Decimal("300"))]  # 300
        raise AssertionError("Unexpected query")
    monkeypatch.setattr(cli, "run_grouped_rows", fake_run_grouped_rows)

    # budgets forecast total only (no verbose breakdown needed here)
    monkeypatch.setattr(
        cli,
        "compute_budget_planned_expenses",
        lambda *_: (Decimal("200"), [("CRC", Decimal("200"), Decimal("1"), Decimal("200"))]),
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

    # Breakdown headers do not appear
    assert "ASSETS breakdown:" not in out
    assert "LIABILITIES breakdown:" not in out
    assert "PLANNED INCOME breakdown:" not in out
    assert "PLANNED EXPENSES breakdown:" not in out
    assert "BUDGETED EXPENSES breakdown (forecast):" not in out

    # Operating currency line
    assert "Operating currency: CRC" in out
    # Summary lines (formatted via fmt_amount)
    assert "Assets:" in out and "2 000.00 CRC" in out           # 2000
    assert "Liabilities:" in out and "100.00 CRC" in out        # prints -liabs_total
    assert "Net now (Assets - Liabilities):" in out and "1 900.00 CRC" in out
    assert "Planned income in range:" in out and "500.00 CRC" in out
    assert "Planned expenses in range:" in out and "300.00 CRC" in out
    assert "Planned budget expenses:" in out and "200.00 CRC" in out
    assert "Forecast end balance:" in out and "1 900.00 CRC" in out
    # No breakdown titles when not verbose
    assert "ASSETS breakdown:" not in out


def test_cli_main_verbose(monkeypatch, capsys, tmp_path):
    j = tmp_path / "main.bean"
    b = tmp_path / "budgets.bean"
    p = tmp_path / "prices.bean"
    for f in (j, b, p):
        f.write_text("", encoding="utf-8")

    today = "2025-01-10"
    until = "2025-01-20"

    monkeypatch.setattr(cli, "load_prices_to_op", lambda *_: {"CRC": Decimal("1"), "USD": Decimal("500")})
    monkeypatch.setattr(cli, "detect_operating_currency_from_journal", lambda *_args, **_kw: "CRC")

    def fake_run_grouped_rows(_journal, query):
        if "^Assets" in query:
            return [("USD", Decimal("1"))]  # -> 500
        if "^Liabilities" in query:
            return [("CRC", Decimal("-50"))]  # -> -50
        if "^Income" in query:
            return [("USD", Decimal("-1"))]  # -> +1 -> 500
        if "^Expenses" in query:
            return [("CRC", Decimal("100"))]  # -> 100
        raise AssertionError("Unexpected query")
    monkeypatch.setattr(cli, "run_grouped_rows", fake_run_grouped_rows)

    # Budgets total 200
    monkeypatch.setattr(
        cli,
        "compute_budget_planned_expenses",
        lambda *_: (Decimal("200"), [("CRC", Decimal("200"), Decimal("1"), Decimal("200"))]),
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

    # Breakdown headers appear
    assert "ASSETS breakdown:" in out
    assert "LIABILITIES breakdown:" in out
    assert "PLANNED INCOME breakdown:" in out
    assert "PLANNED EXPENSES breakdown:" in out
    assert "BUDGETED EXPENSES breakdown (forecast):" in out

    # And summary still consistent:
    # assets_total=500, liabs_total=-50 => net_now=450
    # income=500, pexp=100, budget=200 => total_future_exp=300
    # forecast_end=450+500-300=650
    assert "Net now (Assets - Liabilities):" in out and "450.00 CRC" in out
    assert "Forecast end balance:" in out and "650.00 CRC" in out

