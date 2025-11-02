# dateutils.py
import datetime


def count_weeks(start: datetime.date, end: datetime.date) -> int:
    """
    Count whole/partial calendar weeks in the half-open interval [start, end).
    Returns 0 if end <= start.
    Rounds up any positive number of days to the next week.
    """
    if end <= start:
        return 0
    days = (end - start).days
    return (days + 6) // 7  # ceiling(days/7)


def count_months(start: datetime.date, end: datetime.date) -> int:
    """
    Count calendar months between the 1st of start's month (inclusive)
    and the 1st of end's month (exclusive). Effectively the number of month
    boundaries crossed by any instant in [start, end).

    Examples:
      start=2025-01-01, end=2025-01-31  -> 0
      start=2025-01-01, end=2025-02-01  -> 1
      start=2025-01-15, end=2025-02-14  -> 1
      start=2024-12-31, end=2025-01-01  -> 1
    """
    if end <= start:
        return 0

    cur = datetime.date(start.year, start.month, 1)
    endm = datetime.date(end.year, end.month, 1)

    months = 0
    while cur < endm:
        # advance to first day of next month
        year, mon = cur.year, cur.month
        if mon == 12:
            cur = datetime.date(year + 1, 1, 1)
        else:
            cur = datetime.date(year, mon + 1, 1)
        months += 1
    return months
