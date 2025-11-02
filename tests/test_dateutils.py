import datetime as dt
import pytest

from fava_forecast.dateutils import count_weeks, count_months


# -----------------------------
# count_weeks
# -----------------------------
@pytest.mark.parametrize(
    "start,end,expected",
    [
        # no duration
        (dt.date(2025, 1, 1), dt.date(2025, 1, 1), 0),
        (dt.date(2025, 1, 2), dt.date(2025, 1, 1), 0),

        # less than a week -> 1
        (dt.date(2025, 1, 1), dt.date(2025, 1, 2), 1),
        (dt.date(2025, 1, 1), dt.date(2025, 1, 8), 1),   # 7 days -> 1
        (dt.date(2025, 1, 1), dt.date(2025, 1, 9), 2),   # 8 days -> 2 (ceiling)

        # multi-weeks with remainder
        (dt.date(2025, 1, 1), dt.date(2025, 1, 14), 2),  # 13 days -> 2
        (dt.date(2025, 1, 1), dt.date(2025, 1, 15), 2),  # 14 days -> 2
        (dt.date(2025, 1, 1), dt.date(2025, 1, 16), 3),  # 15 days -> 3
    ],
)
def test_count_weeks(start, end, expected):
    assert count_weeks(start, end) == expected


# -----------------------------
# count_months
# -----------------------------
@pytest.mark.parametrize(
    "start,end,expected",
    [
        # no duration
        (dt.date(2025, 1, 1), dt.date(2025, 1, 1), 0),
        (dt.date(2025, 1, 2), dt.date(2025, 1, 1), 0),

        # within same month
        (dt.date(2025, 1, 1), dt.date(2025, 1, 31), 0),
        (dt.date(2025, 1, 15), dt.date(2025, 1, 16), 0),

        # boundary exactly at start of next month
        (dt.date(2025, 1, 1), dt.date(2025, 2, 1), 1),
        (dt.date(2025, 1, 31), dt.date(2025, 2, 1), 1),

        # partial month crossing
        (dt.date(2025, 1, 15), dt.date(2025, 2, 14), 1),
        (dt.date(2025, 1, 15), dt.date(2025, 3, 1), 2),

        # year change
        (dt.date(2024, 12, 31), dt.date(2025, 1, 1), 1),
        (dt.date(2024, 11, 30), dt.date(2025, 2, 1), 3),

        # multiple months
        (dt.date(2025, 1, 1), dt.date(2025, 6, 1), 5),
        (dt.date(2025, 1, 10), dt.date(2025, 6, 10), 5),
    ],
)
def test_count_months(start, end, expected):
    assert count_months(start, end) == expected
