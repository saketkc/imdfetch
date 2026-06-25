"""Text cleaning and terminal-colorizing helpers."""

import math
import re
from typing import List, Optional, Tuple, Union

from .constants import WEATHER_PARAM_NAMES

__all__ = [
    "clean_city_name",
    "clean_parameter_name",
    "colorize_temperature",
    "colorize_humidity",
    "get_temperature_legend",
    "get_humidity_legend",
    "get_combined_legend",
]

_RESET = "\033[0m"
_BLUE = "\033[94m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_ORANGE = "\033[38;5;208m"
_RED = "\033[91m"
_BROWN = "\033[38;5;130m"
_PURPLE = "\033[95m"

_NA_VALUES = {"NA", "N/A", "-", "--", ""}

_TEMP_BANDS: List[Tuple[float, str, str]] = [
    (10, _BLUE, "< 10°C (Cold)"),
    (20, _CYAN, "10-20°C (Cool)"),
    (25, _GREEN, "20-25°C (Comfortable)"),
    (30, _YELLOW, "25-30°C (Warm)"),
    (35, _ORANGE, "30-35°C (Hot)"),
    (math.inf, _RED, "> 35°C (Very Hot)"),
]

_HUMIDITY_BANDS: List[Tuple[float, str, str]] = [
    (30, _BROWN, "< 30% (Very Dry)"),
    (40, _YELLOW, "30-40% (Dry)"),
    (60, _GREEN, "40-60% (Comfortable)"),
    (70, _CYAN, "60-70% (Humid)"),
    (80, _BLUE, "70-80% (Very Humid)"),
    (math.inf, _PURPLE, "> 80% (Extremely Humid)"),
]


def clean_city_name(city_text: str) -> Optional[str]:
    """Clean and standardize a city name, or None for empty input."""
    if not city_text:
        return None

    city = re.sub(r"\s+", " ", city_text.strip())
    city = re.sub(r"\s*\([^)]*\)", "", city)  # Remove space and parentheses content
    city = re.sub(r"^(For|Weather|Report|Forecast):\s*", "", city, flags=re.IGNORECASE)
    city = re.sub(r"\s*(Weather|Report|Forecast)$", "", city, flags=re.IGNORECASE)
    city = re.sub(r"[<>]", "", city)
    city = city.title()
    city = city.replace(" -", "-")
    city = city.replace("- ", "-")
    return city.strip()


def clean_parameter_name(param_text: str) -> str:
    """Canonicalize an HTML parameter label to a name in WEATHER_PARAM_NAMES."""
    param_text = param_text.replace("(", "").replace(")", "")
    param_text = param_text.replace("  ", " ")

    n = WEATHER_PARAM_NAMES
    if "Maximum Temp" in param_text:
        return n["max_temp"]
    elif "Minimum Temp" in param_text:
        return n["min_temp"]
    elif "Departure from Normal" in param_text:
        if "max" in param_text.lower():
            return "Max Temp Departure from Normal (°C)"
        elif "min" in param_text.lower():
            return "Min Temp Departure from Normal (°C)"
        else:
            return n["max_dep"]
    elif "24 Hours Rainfall" in param_text:
        return n["rainfall"]
    elif "Relative Humidity at 0830" in param_text:
        return n["rh_0830"]
    elif "Relative Humidity at 1730" in param_text:
        return n["rh_1730"]
    elif "Sunset" in param_text:
        return n["sunset"]
    elif "Sunrise" in param_text:
        return n["sunrise"]
    elif "Moonset" in param_text:
        return n["moonset"]
    elif "Moonrise" in param_text:
        return n["moonrise"]
    else:
        return param_text


def _colorize(
    value: Union[str, float],
    bands: List[Tuple[float, str, str]],
    unit: str,
) -> str:
    """Wrap a numeric value in the ANSI color for its band; pass through N/A."""
    if isinstance(value, str):
        if value.upper() in _NA_VALUES:
            return value
        try:
            value = float(value)
        except ValueError:
            return f"{value}{unit}"

    for upper, color, _label in bands:
        if value < upper:
            return f"{color}{value}{unit}{_RESET}"
    return f"{value}{unit}"  # unreachable: last band is math.inf


def _legend(title: str, bands: List[Tuple[float, str, str]]) -> str:
    lines = [f"{title}:"]
    lines += [f"  {color}■{_RESET} {label}" for _upper, color, label in bands]
    return "\n".join(lines)


def colorize_temperature(temp: Union[str, float], unit: str = "°C") -> str:
    """Color-code a temperature value with ANSI escape codes."""
    return _colorize(temp, _TEMP_BANDS, unit)


def colorize_humidity(humidity: Union[str, float], unit: str = "%") -> str:
    """Color-code a relative-humidity value with ANSI escape codes."""
    return _colorize(humidity, _HUMIDITY_BANDS, unit)


def get_temperature_legend() -> str:
    """Legend for the temperature color coding."""
    return _legend("Temperature Color Legend", _TEMP_BANDS)


def get_humidity_legend() -> str:
    """Legend for the humidity color coding."""
    return _legend("Relative Humidity Color Legend", _HUMIDITY_BANDS)


def get_combined_legend() -> str:
    """Combined temperature + humidity legend."""
    return get_temperature_legend() + "\n\n" + get_humidity_legend()
