"""Unit tests for the responsive-JSON-API code path in imdfetch.client (no network)."""

from unittest.mock import MagicMock, patch

import pytest

from imdfetch.client import IMDWeatherClient, _clean
from imdfetch.exceptions import NetworkError
from imdfetch.weather import CityInfo


class TestClean:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, None),
            ("  x\r\n", "x"),
            (5, "5"),
            ("", ""),
        ],
    )
    def test_clean(self, value, expected):
        assert _clean(value) == expected


class TestExtractLatLon:
    def test_valid_indian_coordinate(self):
        rec = {"lat": 28.58, "lon": 77.2}
        assert IMDWeatherClient._extract_latlon(rec) == (28.58, 77.2)

    def test_string_coordinates_parsed(self):
        rec = {"lat": "19.07", "lon": "72.87"}
        assert IMDWeatherClient._extract_latlon(rec) == (19.07, 72.87)

    def test_none_record(self):
        assert IMDWeatherClient._extract_latlon(None) is None

    @pytest.mark.parametrize(
        "rec",
        [
            {"lat": 0.0, "lon": 0.0},  # null-island placeholder, outside India
            {"lat": 51.5, "lon": 0.1},  # London, outside India bbox
            {"lat": "n/a", "lon": "n/a"},  # non-numeric
            {},  # missing keys
        ],
    )
    def test_rejects_implausible(self, rec):
        assert IMDWeatherClient._extract_latlon(rec) is None


class TestWeatherFromJson:
    def test_maps_fields_and_param_names(self):
        rec = {
            "station": "New Delhi\r\n",
            "dat": "2024-06-01\r\n",
            "max": "35",
            "min": "25",
            "rainfall": "0",
            "rh0830": "80",
        }
        wd = IMDWeatherClient._weather_from_json(rec, city_id=42182)
        assert wd.city == "New Delhi"
        assert wd.date == "2024-06-01"
        assert wd.city_id == 42182
        # Parameter vocabulary must match the HTML scraper exactly.
        assert wd.get_parameter("Maximum Temperature") == "35"
        assert wd.get_parameter("Minimum Temperature") == "25"
        assert len(wd.parameters) == 10

    def test_none_values_become_empty_string(self):
        rec = {"station": "X", "dat": "2024-06-01", "max": None}
        wd = IMDWeatherClient._weather_from_json(rec, city_id=1)
        assert wd.get_parameter("Maximum Temperature") == ""


class TestForecastFromJson:
    def test_builds_days_with_iso_and_display_dates(self):
        rec = {
            "station": "New Delhi",
            "dat": "2024-06-01",
            "forecast0": "Sunny",
            "max0": "35",
            "min0": "25",
            "forecast1": "Cloudy",
            "max1": "33",
            "min1": "24",
        }
        fc = IMDWeatherClient._forecast_from_json(rec, city_id=42182)
        assert fc.city == "New Delhi"
        assert fc.city_id == 42182
        assert len(fc.days) == 2
        assert fc.days[0].date == "01-Jun"
        assert fc.days[0].iso_date == "2024-06-01"
        assert fc.days[0].forecast == "Sunny"
        assert fc.days[1].iso_date == "2024-06-02"

    def test_skips_empty_days(self):
        rec = {"station": "X", "dat": "2024-06-01", "forecast0": "Sunny", "max0": "30"}
        fc = IMDWeatherClient._forecast_from_json(rec, city_id=1)
        assert len(fc.days) == 1

    def test_bad_issue_date_yields_blank_display_dates(self):
        rec = {"station": "X", "dat": "not-a-date", "forecast0": "Sunny", "max0": "30"}
        fc = IMDWeatherClient._forecast_from_json(rec, city_id=1)
        assert len(fc.days) == 1
        assert fc.days[0].date == ""
        assert fc.days[0].iso_date == ""


class TestNearestStation:
    def test_extract_any_latlon_accepts_ip_geolocation_keys(self):
        rec = {"latitude": "19.076", "longitude": "72.877"}
        assert IMDWeatherClient._extract_any_latlon(rec) == (19.076, 72.877)

    def test_extract_any_latlon_accepts_loc_key(self):
        rec = {"loc": "19.076,72.877"}
        assert IMDWeatherClient._extract_any_latlon(rec) == (19.076, 72.877)

    @pytest.mark.parametrize(
        "rec",
        [
            {},
            {"latitude": "north", "longitude": "east"},
            {"latitude": 91, "longitude": 72},
            {"lat": 19, "lon": 181},
        ],
    )
    def test_extract_any_latlon_rejects_invalid_coordinates(self, rec):
        assert IMDWeatherClient._extract_any_latlon(rec) is None

    def test_distance_km_orders_nearby_coordinates(self):
        near = IMDWeatherClient._distance_km(19.076, 72.877, 19.08, 72.88)
        far = IMDWeatherClient._distance_km(19.076, 72.877, 28.58, 77.2)
        assert near < far

    def test_get_nearest_city_uses_station_coordinates(self, monkeypatch):
        client = IMDWeatherClient()
        cities = [
            CityInfo(1, "New Delhi", "1", latitude=28.58, longitude=77.2),
            CityInfo(2, "Mumbai", "2", latitude=19.07, longitude=72.87),
        ]
        monkeypatch.setattr(
            client, "get_cities_with_coordinates", lambda max_workers=8: cities
        )

        nearest = client.get_nearest_city(19.076, 72.877)

        assert nearest.city_id == 2

    def test_get_current_weather_for_ip_fetches_nearest_station(self, monkeypatch):
        client = IMDWeatherClient()
        calls = []
        monkeypatch.setattr(client, "get_ip_coordinates", lambda: (19.076, 72.877))
        monkeypatch.setattr(
            client,
            "get_nearest_city",
            lambda lat, lon: CityInfo(
                2, "Mumbai", "2", latitude=19.07, longitude=72.87
            ),
        )

        def fake_weather(city_id):
            calls.append(city_id)
            return IMDWeatherClient._weather_from_json(
                {"station": "Mumbai", "dat": "2024-06-01"}, city_id=city_id
            )

        monkeypatch.setattr(client, "get_current_weather", fake_weather)

        weather = client.get_current_weather_for_ip()

        assert calls == [2]
        assert weather.city == "Mumbai"

    @patch(
        "imdfetch.client.IP_GEOLOCATION_URLS",
        ["https://blocked.test", "https://ok.test"],
    )
    @patch("imdfetch.client.safe_get")
    def test_get_ip_coordinates_falls_back_after_forbidden_provider(
        self, mock_safe_get
    ):
        blocked = Exception("403 Client Error: Forbidden")
        ok_response = MagicMock()
        ok_response.json.return_value = {"latitude": 19.076, "longitude": 72.877}
        mock_safe_get.side_effect = [blocked, ok_response]

        assert IMDWeatherClient().get_ip_coordinates() == (19.076, 72.877)
        assert [call.args[0] for call in mock_safe_get.call_args_list] == [
            "https://blocked.test",
            "https://ok.test",
        ]
        assert all(
            call.kwargs == {"max_retries": 0, "timeout": 5}
            for call in mock_safe_get.call_args_list
        )

    @patch(
        "imdfetch.client.IP_GEOLOCATION_URLS",
        ["https://bad.test", "https://empty.test"],
    )
    @patch("imdfetch.client.safe_get")
    def test_get_ip_coordinates_reports_all_provider_failures(self, mock_safe_get):
        empty_response = MagicMock()
        empty_response.json.return_value = {"status": "success"}
        mock_safe_get.side_effect = [
            Exception("403 Client Error: Forbidden"),
            empty_response,
        ]

        with pytest.raises(NetworkError, match="Failed to determine location"):
            IMDWeatherClient().get_ip_coordinates()

        assert len(mock_safe_get.call_args_list) == 2
        assert all(
            call.kwargs == {"max_retries": 0, "timeout": 5}
            for call in mock_safe_get.call_args_list
        )
