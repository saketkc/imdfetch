"""Unit tests for the weather dataclasses (no network)."""

from imdfetch.weather import (
    ForecastData,
    ForecastDay,
    WeatherData,
    WeatherParameter,
)


def _sample_weather():
    return WeatherData(
        city="New Delhi",
        date="2024-06-01",
        city_id=42182,
        parameters=[
            WeatherParameter(parameter="Maximum Temperature (°C)", value="35"),
            WeatherParameter(parameter="Minimum Temperature (°C)", value="25"),
        ],
    )


class TestWeatherData:
    def test_get_parameter_substring_match(self):
        assert _sample_weather().get_parameter("Maximum Temperature") == "35"

    def test_get_parameter_missing_returns_none(self):
        assert _sample_weather().get_parameter("Rainfall") is None

    def test_to_dict_flattens_parameters(self):
        d = _sample_weather().to_dict()
        assert d["city"] == "New Delhi"
        assert d["parameters"]["Maximum Temperature (°C)"] == "35"


class TestForecastData:
    def _sample(self):
        return ForecastData(
            city="New Delhi",
            forecast_date="2024-06-01",
            city_id=42182,
            days=[
                ForecastDay(
                    date="01-Jun",
                    min_temp="25",
                    max_temp="35",
                    forecast="Sunny",
                    iso_date="2024-06-01",
                )
            ],
        )

    def test_get_day_forecast_by_display_date(self):
        assert self._sample().get_day_forecast("01-Jun").forecast == "Sunny"

    def test_get_day_forecast_by_iso_date(self):
        assert self._sample().get_day_forecast("2024-06-01").max_temp == "35"

    def test_get_day_forecast_missing_returns_none(self):
        assert self._sample().get_day_forecast("2099-01-01") is None

    def test_to_dict_includes_days(self):
        d = self._sample().to_dict()
        assert d["days"][0]["forecast"] == "Sunny"
