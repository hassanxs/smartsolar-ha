"""Helpers for parsing SmartSolar API values.

The API returns most values as strings with units attached (e.g. "238.5 V",
"48 C, 43 C"). This module has no Home Assistant imports so it can be
exercised by scripts/check_api.py outside of Home Assistant.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, tzinfo
import re

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_LAST_UPDATE_FORMATS = ("%H:%M %d-%b-%y", "%H:%M:%S %d-%b-%y", "%H:%M %d-%b-%Y")


def parse_numbers(value: object) -> list[float]:
    """Return every number found in a value such as "48 C, 43 C"."""
    if value is None or isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    return [float(match) for match in _NUMBER_RE.findall(str(value))]


def parse_number(value: object, index: int = 0) -> float | None:
    """Return the number at `index` in a value such as "238.5 V"."""
    numbers = parse_numbers(value)
    return numbers[index] if len(numbers) > index else None


def parse_text(value: object) -> str | None:
    """Return a stripped string, or None when empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_last_update(value: object, tz: tzinfo) -> datetime | None:
    """Parse "Update: 12:00 12-Apr-25" into an aware datetime."""
    text = parse_text(value)
    if text is None:
        return None
    text = text.removeprefix("Update:").strip()
    for fmt in _LAST_UPDATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def match_option(value: object, options: Iterable[str]) -> str | None:
    """Map a setting value onto one of its options.

    Values and options are not always formatted identically, e.g. the value
    "230.0" with options ["220", "230", "240"].
    """
    text = parse_text(value)
    if text is None:
        return None
    options = list(options)
    for option in options:
        if str(option).strip().lower() == text.lower():
            return option
    try:
        number = float(text)
    except ValueError:
        return None
    for option in options:
        try:
            if float(option) == number:
                return option
        except ValueError:
            continue
    return None
