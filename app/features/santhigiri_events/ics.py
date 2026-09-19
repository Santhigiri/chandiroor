"""
Pure RFC 5545 (iCalendar) text builder for Santhigiri event occurrences.

Used by ``SanthigiriEventService.get_calendar_ics()`` to serve
``GET /api/v1/panchangam/events/calendar.ics`` — a live feed a client (e.g.
Google Calendar's "From URL" subscription) can poll periodically and always
get the current occurrence set, without a separate export/download step.

No DB or HTTP imports here — this module only turns already-fetched
``(date, SanthigiriEvent)`` pairs into calendar text.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Tuple

from app.utils.santhigiri_events import SanthigiriEvent

_PRODID = "-//Santhigiri Ashram//Panchangam//EN"
_FOLD_WIDTH = 75


def _escape_text(value: str) -> str:
    """Escape a TEXT value per RFC 5545 (backslash, semicolon, comma, newlines)."""
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold_line(line: str) -> str:
    """Fold a content line longer than 75 octets, continued by a leading space
    on the next line, per RFC 5545 §3.1."""
    if len(line) <= _FOLD_WIDTH:
        return line
    chunks = [line[:_FOLD_WIDTH]]
    rest = line[_FOLD_WIDTH:]
    while rest:
        chunks.append(" " + rest[: _FOLD_WIDTH - 1])
        rest = rest[_FOLD_WIDTH - 1 :]
    return "\r\n".join(chunks)


def build_events_ics(occurrences: Iterable[Tuple[date, SanthigiriEvent]]) -> str:
    """Build a single ``VCALENDAR`` document containing one all-day ``VEVENT``
    per ``(date, event)`` occurrence.

    Each event is emitted as an all-day event (``DTSTART``/``DTEND`` with
    ``VALUE=DATE``, ``DTEND`` exclusive per the spec). The ``UID`` is stable
    and deterministic (``<event_id>-<date>@panchangam.santhigiri``), so
    re-polling the same URL after data changes updates/removes the matching
    ``VEVENT`` in a client's calendar rather than duplicating it.
    """
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for day, event in occurrences:
        next_day = day + timedelta(days=1)
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{event.id}-{day.isoformat()}@panchangam.santhigiri")
        lines.append(f"DTSTAMP:{dtstamp}")
        lines.append(f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{_escape_text(event.name)}")
        if event.description:
            lines.append(f"DESCRIPTION:{_escape_text(event.description)}")
        lines.append("TRANSP:TRANSPARENT")
        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")

    return "\r\n".join(_fold_line(line) for line in lines) + "\r\n"
