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

    def fake_run_grouped_rows(_journal, query):
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

    def fake_run_grouped_rows(_journal, query):
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

