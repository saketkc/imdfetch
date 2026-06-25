"""Unit tests for CLI formatting helpers."""

from imdfetch.cli import _display_observation, get_weather
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

    assert "Current Weather for Mumbai-Chembur" in out
    assert "Min Temperature: NA" in out
    assert "24h Rainfall (mm): NA" in out
    assert "Relative Humidity at 08:30: NA" in out
    assert "Observation values appear unavailable for this station." in out
