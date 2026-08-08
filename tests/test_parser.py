"""Unit tests for the HTML scrapers in imdfetch.parser (no network)."""

import pytest

from imdfetch.exceptions import DataParsingError
from imdfetch.parser import WeatherDataParser

PAST_24_HTML = """
<html>
Local Weather Report and Forecast For:</b> <FONT color="blue">New Delhi</Font>
<B>Dated : 2024-06-01</b>
<table>
  <tr><td>Past 24 Hours Weather Data</td><td>header</td></tr>
  <tr><td>Maximum Temperature (C)</td><td>35.0</td></tr>
  <tr><td>Minimum Temperature (C)</td><td>25.0</td></tr>
</table>
</html>
"""

FORECAST_HTML = """
<html>
Local Weather Report and Forecast For:</b> <FONT color="blue">New Delhi</Font>
<B>Dated : 2024-06-01</b>
<table>
  <tr><td>7 Day's Forecast</td></tr>
  <tr>
    <td>Date</td><td>Min Temp</td><td>Max Temp</td><td>Img</td><td>Forecast</td>
    <td>WImg</td><td>Warning</td><td>RH0830</td><td>RH1730</td>
  </tr>
  <tr>
    <td>01-Jun</td><td>25</td><td>35</td><td></td><td>Sunny</td>
    <td></td><td></td><td>80</td><td>50</td>
  </tr>
</table>
</html>
"""


class TestParseStationSearch:
    PAYLOAD = {
        "status": "1",
        "message": "List of Stations",
        "data": [
            {"station_id": "43003", "station": "Mumbai"},
            {"station_id": "42182", "station": "New Delhi (Safdarjung)"},
        ],
    }

    def test_extracts_ids_and_names_sorted(self):
        cities = WeatherDataParser.parse_station_search(self.PAYLOAD)
        assert [c.city_id for c in cities] == [42182, 43003]
        assert cities[0].display_name == "New Delhi (Safdarjung)"
        assert cities[0].clean_name == "New Delhi"
        assert cities[0].full_value == "42182"

    def test_skips_malformed_records(self):
        payload = {
            "data": [
                {"station_id": "abc", "station": "Bad ID"},
                {"station_id": "42182", "station": None},
                {"station_id": None, "station": "No ID"},
                {"station_id": "43003", "station": "Mumbai"},
            ]
        }
        cities = WeatherDataParser.parse_station_search(payload)
        assert [c.city_id for c in cities] == [43003]

    def test_empty_payload_raises(self):
        with pytest.raises(DataParsingError):
            WeatherDataParser.parse_station_search({"status": "1", "data": []})


class TestParsePast24Hours:
    def test_extracts_city_date_and_parameters(self):
        wd = WeatherDataParser.parse_past_24_hours(PAST_24_HTML)
        assert wd.city == "New Delhi"
        assert wd.date == "2024-06-01"
        assert wd.get_parameter("Maximum Temperature") == "35.0"
        assert wd.get_parameter("Minimum Temperature") == "25.0"

    def test_missing_table_raises(self):
        with pytest.raises(DataParsingError):
            WeatherDataParser.parse_past_24_hours("<html>no table</html>")


class TestParseForecastTable:
    def test_extracts_forecast_day(self):
        fc = WeatherDataParser.parse_forecast_table(FORECAST_HTML)
        assert len(fc.days) == 1
        day = fc.days[0]
        assert day.date == "01-Jun"
        assert day.min_temp == "25"
        assert day.max_temp == "35"
        assert day.forecast == "Sunny"
        assert day.warnings is None  # empty warning cell -> None

    def test_missing_table_raises(self):
        with pytest.raises(DataParsingError):
            WeatherDataParser.parse_forecast_table("<html>no table</html>")
