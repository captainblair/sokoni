"""
Turning the words a trader uses for time into concrete date ranges.

"Today" and "this month" are how the question actually gets asked, out loud and
in the UI, so the API accepts them directly rather than making every caller
compute boundaries and risk each one drawing them slightly differently.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone


class UnknownPeriod(Exception):
    """Raised when a period name or date range cannot be understood."""


@dataclass(frozen=True)
class Period:
    """A closed range of local dates, plus the label it was asked for by."""

    label: str
    start_date: date | None
    end_date: date | None

    @property
    def start(self) -> datetime | None:
        return _as_datetime(self.start_date, time.min)

    @property
    def end(self) -> datetime | None:
        return _as_datetime(self.end_date, time.max)


def _as_datetime(value: date | None, at: time) -> datetime | None:
    if value is None:
        return None
    return timezone.make_aware(datetime.combine(value, at))


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise UnknownPeriod(f"{field} must be a date in YYYY-MM-DD form.") from exc


def resolve_period(params) -> Period:
    """
    Builds a period from `period=`, or from an explicit `date_from`/`date_to`.

    Defaults to today, because the most common question a trader asks is about
    the day they are standing in.
    """
    today = timezone.localdate()
    date_from = params.get("date_from")
    date_to = params.get("date_to")

    if date_from or date_to:
        start = _parse_date(date_from, "date_from") if date_from else None
        end = _parse_date(date_to, "date_to") if date_to else None

        if start and end and start > end:
            raise UnknownPeriod("date_from cannot be after date_to.")
        return Period("custom", start, end)

    name = (params.get("period") or "today").lower()

    if name == "today":
        return Period(name, today, today)
    if name == "yesterday":
        yesterday = today - timedelta(days=1)
        return Period(name, yesterday, yesterday)
    if name == "week":
        # The last seven days including today, not the calendar week: a trader
        # asking "how was this week" means the days just lived through.
        return Period(name, today - timedelta(days=6), today)
    if name == "month":
        return Period(name, today.replace(day=1), today)
    if name == "year":
        return Period(name, today.replace(month=1, day=1), today)
    if name == "all":
        return Period(name, None, None)

    raise UnknownPeriod(
        "Unknown period. Use today, yesterday, week, month, year, all, or a "
        "date_from/date_to range."
    )
