"""Backward-compatible facade.

The utilities were split into focused modules (:mod:`imdfetch.http`,
:mod:`imdfetch.dates`, :mod:`imdfetch.textfmt`). This module re-exports them so
existing ``from imdfetch.utils import ...`` imports keep working.
"""

from .dates import convert_date_to_iso, format_date, parse_date
from .http import make_robust_request, safe_get, safe_post
from .textfmt import (
    clean_city_name,
    clean_parameter_name,
    colorize_humidity,
    colorize_temperature,
    get_combined_legend,
    get_humidity_legend,
    get_temperature_legend,
)

__all__ = [
    "make_robust_request",
    "safe_get",
    "safe_post",
    "parse_date",
    "convert_date_to_iso",
    "format_date",
    "clean_city_name",
    "clean_parameter_name",
    "colorize_temperature",
    "colorize_humidity",
    "get_temperature_legend",
    "get_humidity_legend",
    "get_combined_legend",
]
