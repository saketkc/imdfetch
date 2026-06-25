"""Date parsing and formatting helpers for IMD pages."""

import re
from datetime import datetime
from typing import Optional

from .constants import DATE_FORMATS, MONTH_ABBREV

__all__ = ["parse_date", "convert_date_to_iso", "format_date"]


def parse_date(date_text: str) -> Optional[str]:
    """Parse common IMD date formats into YYYY-MM-DD, or None if unrecognized."""
    if not date_text:
        return None

    date_text = re.sub(r"[^\w\s\/\-,:]", "", date_text.strip())

    for fmt in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_text, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def convert_date_to_iso(date_str: str) -> Optional[str]:
    """Convert "DD-MMM" (e.g. "27-May") to YYYY-MM-DD using the current year."""
    if not date_str:
        return None

    current_year = datetime.now().year

    try:
        parts = date_str.strip().replace("-", " ").replace("  ", " ").split(" ")
        if len(parts) != 2:
            return None

        day, month_abbr = parts
        day = day.zfill(2)

        month_key = month_abbr.lower()[:3]
        if month_key not in MONTH_ABBREV:
            return None

        month = MONTH_ABBREV[month_key]
        return f"{current_year}-{month}-{day}"

    except Exception:
        return None


def format_date(date_str: str, include_day: bool = True) -> str:
    """Format a date string as "25 May, 2027 (Tuesday)"; pass through on failure."""
    date_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]

    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_str.strip(), fmt)
            formatted = date_obj.strftime("%d %B, %Y")
            if include_day:
                formatted += f" ({date_obj.strftime('%A')})"
            return formatted
        except ValueError:
            continue

    return date_str
