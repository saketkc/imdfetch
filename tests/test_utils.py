"""Unit tests for pure helper functions in imdfetch.utils (no network)."""

from datetime import datetime

import pytest

from imdfetch.utils import (
    clean_city_name,
    clean_parameter_name,
    colorize_humidity,
    colorize_temperature,
    convert_date_to_iso,
    format_date,
    parse_date,
)


class TestCleanCityName:
    def test_strips_parenthetical(self):
        assert clean_city_name("New Delhi (Safdarjung)") == "New Delhi"

    def test_collapses_whitespace_and_titlecases(self):
        assert clean_city_name("  mumbai   city ") == "Mumbai City"

    def test_strips_report_suffix(self):
        assert clean_city_name("Shimla Weather") == "Shimla"

    def test_empty_returns_none(self):
        assert clean_city_name("") is None


class TestCleanParameterName:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Maximum Temperature (C)", "Maximum Temperature (°C)"),
            ("Minimum Temperature", "Minimum Temperature (°C)"),
            ("24 Hours Rainfall (mm)", "24 Hours Rainfall (mm)"),
            ("Sunset", "Today's Sunset (IST)"),
        ],
    )
    def test_canonicalizes_known_params(self, raw, expected):
        assert clean_parameter_name(raw) == expected

    def test_unknown_param_passes_through(self):
        assert clean_parameter_name("Some Unknown Param") == "Some Unknown Param"


class TestConvertDateToIso:
    def test_basic(self):
        year = datetime.now().year
        assert convert_date_to_iso("27-May") == f"{year}-05-27"

    def test_pads_single_digit_day(self):
        year = datetime.now().year
        assert convert_date_to_iso("2-Jun") == f"{year}-06-02"

    @pytest.mark.parametrize("bad", ["", "notadate", "27-Xyz", "27"])
    def test_unparseable_returns_none(self, bad):
        assert convert_date_to_iso(bad) is None


class TestParseDate:
    def test_iso_passthrough(self):
        assert parse_date("2025-05-27") == "2025-05-27"

    def test_long_form(self):
        assert parse_date("May 27, 2025") == "2025-05-27"

    @pytest.mark.parametrize("bad", ["", "not a date"])
    def test_unparseable_returns_none(self, bad):
        assert parse_date(bad) is None


class TestColorize:
    def test_temperature_passes_through_na(self):
        assert colorize_temperature("NA") == "NA"

    def test_temperature_wraps_value(self):
        out = colorize_temperature(35.0)
        assert "35" in out and out.endswith("\033[0m")

    def test_humidity_passes_through_na(self):
        assert colorize_humidity("--") == "--"

    def test_humidity_wraps_value(self):
        out = colorize_humidity(82.0)
        assert "82" in out and out.endswith("\033[0m")


class TestFormatDate:
    def test_iso_to_readable(self):
        assert format_date("2027-05-25", include_day=False) == "25 May, 2027"

    def test_unparseable_returns_input(self):
        assert format_date("garbage") == "garbage"
