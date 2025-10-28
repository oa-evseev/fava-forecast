# dateutils.py
import datetime


def count_weeks(start: datetime.date, end: datetime.date) -> int:
    if end <= start:
        return 0
    delta = (end - start).days
    return (delta + 6) // 7  # round up


def count_months(start: datetime.date, end: datetime.date) -> int:
    if end <= start:
        return 0
    m = 0
    cur = datetime.date(start.year, start.month, 1)
    endm = datetime.date(end.year, end.month, 1)
    while cur < endm:
        m += 1
        y, mm = cur.year, cur.month
        mm = 1 if mm == 12 else mm + 1
        y = y + 1 if mm == 1 and cur.month == 12 else y
        cur = datetime.date(y, mm, 1)
    return m

