"""Unit tests for CLI formatting helpers."""

import json

import pytest

from imdfetch.cli import _display_observation, get_weather
from imdfetch.exceptions import CityNotFoundError, IMDWeatherError, NetworkError
from imdfetch.weather import WeatherData, WeatherParameter


class FakeClient:
    def get_current_weather(self, city_identifier):
        return WeatherData(
            city="Mumbai-Chembur",
            date="2026-06-24",
            city_id=city_identifier,
            parameters=[
                WeatherParameter("Maximum Temperature (°C)", ""),
                WeatherParameter("Minimum Temperature (°C)", "99.9"),
                WeatherParameter("24 Hours Rainfall (mm)", "999.00"),
                WeatherParameter("Relative Humidity at 08:30 (%)", "999"),
                WeatherParameter("Relative Humidity at 17:30 (%)", "NA"),
            ],
        )


def test_display_observation_replaces_imd_sentinel_values():
    assert _display_observation("Minimum Temperature", "99.9") == ("NA", True)
    assert _display_observation("24 Hours Rainfall", "999.00") == ("NA", True)
    assert _display_observation("Relative Humidity at 08:30", "999") == ("NA", True)
    assert _display_observation("Maximum Temperature", "28.5") == ("28.5", False)


def test_get_weather_warns_when_observations_are_unavailable(capsys):
    get_weather(FakeClient(), "99943")

    out = capsys.readouterr().out

    assert "Latest Observations for Mumbai-Chembur" in out
    assert "Min Temperature: NA" in out
    assert "24h Rainfall (mm): NA" in out
    assert "Relative Humidity at 08:30: NA" in out
    assert "Observation values appear unavailable for this station." in out


class DatedClient:
    def get_current_weather(self, city_identifier):
        return WeatherData(
            city="New Delhi",
            date="2026-11-09",
            max_date="2026-11-08",
            updated_at="2026-11-09 05:17:01",
            parameters=[WeatherParameter("Maximum Temperature (°C)", "31.1")],
        )


def test_get_weather_dates_the_max_and_does_not_claim_current(capsys):
    get_weather(DatedClient(), "42182")

    out = capsys.readouterr().out

    assert "Current Weather" not in out
    assert "Max Temperature (recorded 08 November, 2026)" in out
    assert "2026-11-09 05:17:01" in out


class HistoryClient:
    def get_daily_temperatures(self, city_identifier):
        from imdfetch.weather import DailyTemperature, TemperatureHistory

        return TemperatureHistory(
            city="New Delhi",
            city_id=city_identifier,
            days=[
                DailyTemperature("2026-11-08", max_temp=31.1, normal_max=29.5),
                DailyTemperature("2026-11-07", max_temp=99.9),
                DailyTemperature("2026-11-10", forecast_max=28),
            ],
        )


def test_show_history_renders_observed_forecast_and_sentinels(capsys):
    from imdfetch.cli import show_history

    show_history(HistoryClient(), "42182")

    lines = capsys.readouterr().out.splitlines()
    assert "New Delhi" in lines[0]
    row = next(line for line in lines if line.startswith("2026-11-08"))
    assert "31.1" in row and "29.5" in row
    sentinel = next(line for line in lines if line.startswith("2026-11-07"))
    assert "99.9" not in sentinel and "NA" in sentinel
    assert "28" in next(line for line in lines if line.startswith("2026-11-10"))


def test_show_history_json_output(capsys):
    from imdfetch.cli import show_history

    show_history(HistoryClient(), "42182", output_format="json")

    data = json.loads(capsys.readouterr().out)
    assert data["city"] == "New Delhi"
    assert data["days"][0]["max_temp"] == 31.1


class FailingClient:
    def __init__(self, error):
        self.error = error

    def get_current_weather(self, city_identifier):
        raise self.error


@pytest.mark.parametrize(
    "error,code",
    [
        (CityNotFoundError("nope"), 3),
        (NetworkError("down"), 5),
        (IMDWeatherError("bad"), 1),
    ],
)
def test_failures_have_distinct_exit_codes(error, code):
    with pytest.raises(SystemExit) as exit_info:
        get_weather(FailingClient(error), "Delhi")

    assert exit_info.value.code == code


def test_json_mode_reports_errors_as_json(capsys):
    with pytest.raises(SystemExit):
        get_weather(FailingClient(NetworkError("down")), "Delhi", "json")

    error = json.loads(capsys.readouterr().out)["error"]
    assert error == {"type": "NetworkError", "message": "down"}


def test_ambiguous_city_lists_ids_an_agent_can_retry_with(capsys):
    from imdfetch.exceptions import AmbiguousCityError
    from imdfetch.weather import CityInfo

    error = AmbiguousCityError("many", [CityInfo(1, "Mumbai-Colaba", "1")])

    with pytest.raises(SystemExit) as exit_info:
        get_weather(FailingClient(error), "Mumbai", "json")

    assert exit_info.value.code == 4
    matches = json.loads(capsys.readouterr().out)["error"]["matches"]
    assert matches == [{"city_id": 1, "name": "Mumbai-Colaba"}]


class MultiStationClient:
    def get_current_weather(self, city_identifier):
        return [
            WeatherData(
                city="Mumbai-Colaba",
                date="2026-11-09",
                city_id=1,
                parameters=[WeatherParameter("Maximum Temperature (°C)", "37")],
            ),
            WeatherData(city="Mumbai-Powai", date="", city_id=2),
        ]


def test_weather_prints_every_matching_station(capsys):
    get_weather(MultiStationClient(), "Mumbai")

    out = capsys.readouterr().out
    assert "2 stations match 'Mumbai'" in out
    assert "Latest Observations for Mumbai-Colaba" in out
    assert "Latest Observations for Mumbai-Powai" in out
    assert "Observation values appear unavailable" in out


def test_weather_json_is_a_list_for_several_stations(capsys):
    get_weather(MultiStationClient(), "Mumbai", "json")

    data = json.loads(capsys.readouterr().out)
    assert [station["city_id"] for station in data] == [1, 2]
