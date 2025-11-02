from decimal import Decimal
import datetime as dt
import fava_forecast.forecast as fc


def test_run_forecast_minimal(monkeypatch, tmp_path):
    journal = tmp_path / "main.bean"
    budgets = tmp_path / "budgets.bean"
    prices = tmp_path / "prices.bean"
    for f in (journal, budgets, prices):
        f.write_text("", encoding="utf-8")

    monkeypatch.setattr(fc, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")
    monkeypatch.setattr(fc, "load_prices_to_op", lambda *_: {"CRC": Decimal("1")})

    def fake_run_grouped_rows(_j, q):
        if "^Assets" in q:
            return [("CRC", Decimal("100"))]
        if "^Liabilities" in q:
            return [("CRC", Decimal("-20"))]
        if "^Income" in q:
            return [("CRC", Decimal("-50"))]
        if "^Expenses" in q:
            return [("CRC", Decimal("10"))]
        raise AssertionError(f"Unexpected query: {q}")

    monkeypatch.setattr(fc, "run_grouped_rows", fake_run_grouped_rows)
    monkeypatch.setattr(fc, "compute_budget_planned_expenses",
        lambda *_: (Decimal("5"), [("CRC", Decimal("5"), Decimal("1"), Decimal("5"))])
    )

    data = fc.run_forecast(
        journal=str(journal),
        budgets=str(budgets),
        prices=str(prices),
        until="2025-01-20",
        today="2025-01-10",
        currency="CRC",
    )

    assert data["op_currency"] == "CRC"
    # assets = 100
    # liabs = -20          → net_now = 80
    # income = +50 (−(−50))
    # expenses = 10
    # budget = 5
    # total_future_exp = 10 + 5 = 15
    # forecast_end = 80 + 50 − 15 = 115
    assert data["forecast_end"] == Decimal("115.00")
    assert data["ok"]

def test_run_forecast_multicurrency(monkeypatch, tmp_path):
    """Check correct conversion and summation across multiple currencies."""
    journal = tmp_path / "main.bean"
    budgets = tmp_path / "budgets.bean"
    prices = tmp_path / "prices.bean"
    for f in (journal, budgets, prices):
        f.write_text("", encoding="utf-8")

    monkeypatch.setattr(fc, "detect_operating_currency_from_journal", lambda *_, **__: "CRC")
    # Conversion rates: 1 USD = 500 CRC, 1 EUR = 600 CRC
    monkeypatch.setattr(fc, "load_prices_to_op", lambda *_: {"CRC": Decimal("1"), "USD": Decimal("500"), "EUR": Decimal("600")})

    def fake_run_grouped_rows(_j, q):
        if "^Assets" in q:
            return [("CRC", Decimal("100")), ("USD", Decimal("1"))]     # 100 + 1×500 = 600
        if "^Liabilities" in q:
            return [("EUR", Decimal("-0.5"))]                           # -0.5×600 = -300
        if "^Income" in q:
            return [("USD", Decimal("-0.5"))]                           # +0.5×500 = +250
        if "^Expenses" in q:
            return [("CRC", Decimal("50"))]                             # 50
        raise AssertionError(f"Unexpected query: {q}")

    monkeypatch.setattr(fc, "run_grouped_rows", fake_run_grouped_rows)
    monkeypatch.setattr(fc, "compute_budget_planned_expenses",
        lambda *_: (Decimal("25"), [("CRC", Decimal("25"), Decimal("1"), Decimal("25"))])
    )

    data = fc.run_forecast(
        journal=str(journal),
        budgets=str(budgets),
        prices=str(prices),
        until="2025-01-20",
        today="2025-01-10",
        currency="CRC",
    )

    # Calculation reference:
    # assets = 600
    # liabs = -300          → net_now = 300
    # income = +250
    # expenses = 50
    # budget = 25
    # total_future_exp = 75
    # forecast_end = 300 + 250 − 75 = 475
    assert data["forecast_end"] == Decimal("475.00")
    assert data["ok"]
    assert data["op_currency"] == "CRC"
