"""Unit tests for the responsive-JSON-API code path in imdfetch.client (no network)."""

from unittest.mock import MagicMock, patch

import pytest

from imdfetch.client import IMDWeatherClient, _clean
from imdfetch.exceptions import (
    AmbiguousCityError,
    CityNotFoundError,
    IMDWeatherError,
    NetworkError,
)
from imdfetch.weather import CityInfo, ForecastData, WeatherData


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


class TestObservationDates:
    REC = {
        "station": "X",
        "dat": "2026-11-09",
        "max_date": "2026-11-08\r\n",
        "updat": "2026-11-09 05:17:01\r\n",
    }

    def test_keeps_max_date_and_update_time(self):
        wd = IMDWeatherClient._weather_from_json(self.REC, city_id=1)
        assert wd.date == "2026-11-09"
        assert wd.max_date == "2026-11-08"
        assert wd.updated_at == "2026-11-09 05:17:01"

    def test_placeholder_max_date_means_no_date(self):
        rec = {**self.REC, "max_date": "NA", "updat": "NA\r\n"}
        wd = IMDWeatherClient._weather_from_json(rec, city_id=1)
        assert wd.max_date is None
        assert wd.updated_at is None

    def test_to_dict_exposes_dates(self):
        d = IMDWeatherClient._weather_from_json(self.REC, city_id=1).to_dict()
        assert d["max_date"] == "2026-11-08"
        assert d["updated_at"] == "2026-11-09 05:17:01"


class TestForecastWarnings:
    def _days(self, **extra):
        rec = {
            "station": "X",
            "dat": "2026-11-09",
            "forecast0": "Sunny",
            "forecast1": "Fog",
            **extra,
        }
        return IMDWeatherClient._forecast_from_json(rec, city_id=1).days

    def test_uses_readable_text_not_codes(self):
        days = self._days(warning0="3", wText=["Thunderstorm", "No warning"])
        assert days[0].warnings == "Thunderstorm"

    @pytest.mark.parametrize("text", ["No warning", "No Warning", "", None])
    def test_no_warning_becomes_none(self, text):
        assert self._days(warning0="0", wText=[text, text])[0].warnings is None

    def test_missing_warning_text_is_none(self):
        assert self._days(warning0='{"morning":["0"]}')[0].warnings is None

    def test_active_code_without_text_is_not_hidden(self):
        assert "3" in self._days(warning0="3")[0].warnings


class TestDailyTemperatures:
    REC = {"station": "New Delhi\r\n", "dat": "2026-11-09"}
    HISTORY = {
        "2026-11-10": {"DATE": "10 Nov", "F_MAX": 28, "F_MIN": 15, "MAX_N": 29.5},
        "2026-11-08": {
            "MAX": 31.1,
            "MIN": 15.7,
            "MAX_N": 29.5,
            "MIN_N": 14.3,
            "F_MAX": None,
        },
    }

    def _client(self):
        client = IMDWeatherClient()
        client._cities_cache = [CityInfo(42182, "New Delhi", "42182")]
        return client

    @patch("imdfetch.client.safe_post")
    def test_maps_observed_normal_and_forecast_in_date_order(self, mock_post):
        mock_post.return_value.json.return_value = [self.REC, self.HISTORY]

        result = self._client().get_daily_temperatures(42182)

        assert result.city == "New Delhi"
        assert result.city_id == 42182
        assert [d.date for d in result.days] == ["2026-11-08", "2026-11-10"]
        past, future = result.days
        assert (past.max_temp, past.min_temp) == (31.1, 15.7)
        assert (past.normal_max, past.normal_min) == (29.5, 14.3)
        assert past.forecast_max is None
        assert future.max_temp is None
        assert (future.forecast_max, future.forecast_min) == (28, 15)

    @patch("imdfetch.client.safe_post")
    def test_to_dict_lists_days(self, mock_post):
        mock_post.return_value.json.return_value = [self.REC, self.HISTORY]

        d = self._client().get_daily_temperatures(42182).to_dict()

        assert d["days"][0]["date"] == "2026-11-08"
        assert d["days"][1]["forecast_max"] == 28

    @pytest.mark.parametrize("payload", [[REC], {"station": "X"}, [REC, []], [REC, {}]])
    @patch("imdfetch.client.safe_post")
    def test_missing_history_raises(self, mock_post, payload):
        mock_post.return_value.json.return_value = payload

        with pytest.raises(IMDWeatherError, match="history"):
            self._client().get_daily_temperatures(42182)

    @patch("imdfetch.client.safe_post")
    def test_non_json_response_raises_imd_error(self, mock_post):
        mock_post.return_value.json.side_effect = ValueError("not json")

        with pytest.raises(IMDWeatherError):
            self._client().get_daily_temperatures(42182)


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


def _mumbai_client():
    client = IMDWeatherClient()
    client._cities_cache = [
        CityInfo(1, "Mumbai-Colaba", "1", clean_name="Mumbai-Colaba"),
        CityInfo(2, "Mumbai-Powai", "2", clean_name="Mumbai-Powai"),
        CityInfo(3, "Delhi", "3", clean_name="Delhi"),
    ]
    return client


class TestCityResolution:
    def test_ambiguous_name_carries_candidates(self):
        with pytest.raises(AmbiguousCityError) as err:
            _mumbai_client()._resolve_city_id("Mumbai")

        assert [c.city_id for c in err.value.matches] == [1, 2]

    def test_ambiguous_is_still_a_city_not_found_error(self):
        with pytest.raises(CityNotFoundError):
            _mumbai_client()._resolve_city_id("Mumbai")

    def test_unknown_name_is_not_ambiguous(self):
        with pytest.raises(CityNotFoundError) as err:
            _mumbai_client()._resolve_city_id("Nowhere")

        assert not isinstance(err.value, AmbiguousCityError)


class TestMultiStationWeather:
    @staticmethod
    def _serve(failing=()):
        def fake_post(_url, data, **_kwargs):
            if data["ID"] in failing:
                raise NetworkError("down")
            response = MagicMock()
            response.json.return_value = [
                {"station": f"Station {data['ID']}", "dat": "2026-11-09", "max": "31"}
            ]
            return response

        return fake_post

    @patch("imdfetch.client.safe_post")
    def test_name_matching_several_stations_returns_each(self, mock_post):
        mock_post.side_effect = self._serve()

        result = _mumbai_client().get_current_weather("Mumbai")

        assert [w.city_id for w in result] == [1, 2]
        assert result[1].city == "Station 2"
        assert result[0].get_parameter("Maximum Temperature") == "31"

    @patch("imdfetch.client.safe_post")
    def test_unique_name_still_returns_one_result(self, mock_post):
        mock_post.side_effect = self._serve()

        assert isinstance(_mumbai_client().get_current_weather("Delhi"), WeatherData)

    @patch("imdfetch.client.safe_get", side_effect=NetworkError("html down"))
    @patch("imdfetch.client.safe_post")
    def test_failed_station_stays_visible_with_no_readings(self, mock_post, _get):
        mock_post.side_effect = self._serve(failing={2})

        result = _mumbai_client().get_current_weather("Mumbai")

        assert [w.city_id for w in result] == [1, 2]
        assert result[1].city == "Mumbai-Powai"
        assert result[1].parameters == []

    @patch("imdfetch.client.safe_get", side_effect=NetworkError("html down"))
    @patch("imdfetch.client.safe_post")
    def test_every_station_failing_is_a_network_error(self, mock_post, _get):
        mock_post.side_effect = self._serve(failing={1, 2})

        with pytest.raises(NetworkError):
            _mumbai_client().get_current_weather("Mumbai")

    @patch("imdfetch.client.MAX_STATION_MATCHES", 1)
    @patch("imdfetch.client.safe_post")
    def test_too_many_matches_asks_for_a_narrower_name(self, mock_post):
        with pytest.raises(AmbiguousCityError):
            _mumbai_client().get_current_weather("Mumbai")

        mock_post.assert_not_called()

    @patch("imdfetch.client.safe_post")
    def test_forecast_still_requires_one_station(self, mock_post):
        with pytest.raises(AmbiguousCityError):
            _mumbai_client().get_forecast("Mumbai")

        mock_post.assert_not_called()


class TestSourceFallback:
    def _client(self):
        client = IMDWeatherClient()
        client._cities_cache = [CityInfo(1, "X", "1")]
        client.parser = MagicMock()
        client.parser.parse_past_24_hours.return_value = WeatherData("X", "d")
        client.parser.parse_forecast_table.return_value = ForecastData("X", "d")
        return client

    @patch("imdfetch.client.safe_get")
    @patch("imdfetch.client.safe_post", side_effect=NetworkError("json down"))
    def test_weather_falls_back_to_html(self, _post, mock_get):
        mock_get.return_value.text = "<html>"
        client = self._client()

        assert client.get_current_weather(1).city_id == 1
        client.parser.parse_past_24_hours.assert_called_once_with("<html>")

    @patch("imdfetch.client.safe_get")
    @patch("imdfetch.client.safe_post", side_effect=NetworkError("json down"))
    def test_forecast_falls_back_to_html(self, _post, mock_get):
        mock_get.return_value.text = "<html>"

        assert self._client().get_forecast(1).city_id == 1

    @patch("imdfetch.client.safe_get")
    @patch("imdfetch.client.safe_post", side_effect=NetworkError("json down"))
    def test_complete_uses_one_html_page_for_both(self, _post, mock_get):
        mock_get.return_value.text = "<html>"

        weather, forecast = self._client().get_complete_weather_data(1)

        assert (weather.city_id, forecast.city_id) == (1, 1)
        assert mock_get.call_count == 1

    @patch("imdfetch.client.safe_get", side_effect=NetworkError("html down"))
    @patch("imdfetch.client.safe_post", side_effect=NetworkError("json down"))
    def test_both_sources_down_is_a_network_error(self, _post, _get):
        with pytest.raises(NetworkError):
            self._client().get_current_weather(1)

    @patch("imdfetch.client.safe_get")
    @patch("imdfetch.client.safe_post")
    def test_parse_failure_is_wrapped_with_the_operation(self, mock_post, mock_get):
        mock_post.return_value.json.return_value = []
        client = self._client()
        client.parser.parse_forecast_table.side_effect = RuntimeError("bad table")

        with pytest.raises(IMDWeatherError, match="forecast"):
            client.get_forecast(1)
