from decimal import Decimal
import fava_forecast.convert as cv


# -----------------------------
# amounts_to_converted_breakdown
# -----------------------------
def test_amounts_to_converted_breakdown_basic():
    rows = [("USD", Decimal("10")), ("CRC", Decimal("700"))]
    rates = {"USD": Decimal("520"), "CRC": Decimal("1")}
    total, br = cv.amounts_to_converted_breakdown(rows, rates)

    assert total == Decimal("10") * Decimal("520") + Decimal("700") * Decimal("1")

    # Order must be preserved
    assert br[0] == ("USD", Decimal("10"), Decimal("520"), Decimal("5200"))
    assert br[1] == ("CRC", Decimal("700"), Decimal("1"), Decimal("700"))


def test_amounts_to_converted_breakdown_missing_rate():
    rows = [("EUR", Decimal("5")), ("USD", Decimal("2.5"))]
    rates = {"USD": Decimal("500")}  # EUR has no rate
    total, br = cv.amounts_to_converted_breakdown(rows, rates)

    # EUR is ignored in total
    assert total == Decimal("2.5") * Decimal("500")

    eur_row = [x for x in br if x[0] == "EUR"][0]
    usd_row = [x for x in br if x[0] == "USD"][0]
    assert eur_row == ("EUR", Decimal("5"), None, None)
    assert usd_row == ("USD", Decimal("2.5"), Decimal("500"), Decimal("1250"))


# -----------------------------
# query_grouped_sum_to_total
# -----------------------------
def test_query_grouped_sum_to_total_pipeline(monkeypatch):
    calls = {"run": [], "body": [], "group": []}

    # Mock helper functions imported into convert module
    def fake_run(journal_path, query):
        calls["run"].append((journal_path, query))
        return [
            "Currency  Sum",
            "──────────────",
            "USD     10.00 USD",
            "CRC 1_000.00 CRC",
            "sum  total",
        ]

    def fake_body(lines):
        calls["body"].append(tuple(lines))
        # Return already cleaned table body
        return ["USD     10.00 USD", "CRC 1_000.00 CRC"]

    def fake_group(body_lines):
        calls["group"].append(tuple(body_lines))
        return [("USD", Decimal("10.00")), ("CRC", Decimal("1000.00"))]

    monkeypatch.setattr(cv, "beanquery_run_lines", fake_run)
    monkeypatch.setattr(cv, "beanquery_table_body", fake_body)
    monkeypatch.setattr(cv, "beanquery_grouped_amounts", fake_group)

    rates = {"USD": Decimal("520"), "CRC": Decimal("1")}
    total = cv.query_grouped_sum_to_total("main.bean", "SELECT currency, sum(position) GROUP BY currency", rates)

    assert calls["run"] == [("main.bean", "SELECT currency, sum(position) GROUP BY currency")]
    assert len(calls["body"]) == 1 and len(calls["group"]) == 1

    # Total = 10*520 + 1000*1
    assert total == Decimal("10") * Decimal("520") + Decimal("1000")
