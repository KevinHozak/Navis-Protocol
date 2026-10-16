"""Recurring mandates use date-only arithmetic and a 03:00 local day cutoff."""
import re
from calendar import monthrange
from datetime import date, datetime, timedelta


def journal_day(now=None):
    now = now or datetime.now().astimezone()
    day = now.date()
    if now.hour < 3:
        day -= timedelta(days=1)
    return day.isoformat()


def validate_date(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Expected YYYY-MM-DD")
    return parsed


def calculate_next_due(freq, last_done_str):
    day = validate_date(last_done_str)
    freq = freq.strip().lower()
    days = {"daily": 1, "weekly": 7, "bi-weekly": 14,
            "every 2 weeks": 14, "every 3 weeks": 21}
    months = {"monthly": 1, "bimonthly": 2, "every 2 months": 2,
              "quarterly": 3, "seasonal": 6, "yearly": 12}
    interval = re.fullmatch(r"every ([1-9][0-9]*) (days?|weeks?|months?)", freq)
    if interval:
        count, unit = int(interval[1]), interval[2]
        if unit.startswith("month"):
            months[freq] = count
        else:
            days[freq] = count * (7 if unit.startswith("week") else 1)
    if freq in days:
        try:
            return (day + timedelta(days=days[freq])).isoformat()
        except OverflowError as error:
            raise ValueError("Recurrence exceeds the supported date range") from error
    if freq not in months:
        raise ValueError("Unsupported recurrence frequency")
    index = day.year * 12 + day.month - 1 + months[freq]
    year, month = divmod(index, 12)
    month += 1
    if not 1 <= year <= 9999:
        raise ValueError("Recurrence exceeds the supported date range")
    return date(year, month, min(day.day, monthrange(year, month)[1])).isoformat()
