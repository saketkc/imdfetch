"""
Main client class for interacting with IMD weather services
"""

from typing import List, Optional, Union

import pandas as pd

from .constants import (CITY_LIST_URL, WEATHER_TEST_URL_PREFIX,
                        WEATHER_URL_PREFIX)
from .exceptions import CityNotFoundError, IMDWeatherError, NetworkError
from .parser import WeatherDataParser
from .utils import safe_get
from .weather import CityInfo, ForecastData, WeatherData


class IMDWeatherClient:
    """
    Main client for fetching weather data from India Meteorological Department
    """

    def __init__(self, use_test_endpoint: bool = True):
        """
        Initialize the IMD Weather Client

        Args:
            use_test_endpoint: Whether to use the test endpoint for weather data
        """
        self.parser = WeatherDataParser()
        self.weather_url_prefix = (
            WEATHER_TEST_URL_PREFIX  # if use_test_endpoint else WEATHER_URL_PREFIX
        )
        self._cities_cache = None

    def get_cities(self, refresh_cache: bool = False) -> List[CityInfo]:
        """
        Get list of all available cities

        Args:
            refresh_cache: Whether to refresh the cached city list

        Returns:
            List of CityInfo objects

        Raises:
            NetworkError: If unable to fetch city data
            IMDWeatherError: If parsing fails
        """
        if self._cities_cache is None or refresh_cache:
            try:
                response = safe_get(CITY_LIST_URL)
                self._cities_cache = self.parser.get_cities_dataframe(response.text)
            except Exception as e:
                raise IMDWeatherError(f"Failed to fetch cities: {str(e)}")

        return self._cities_cache

    def find_city(self, city_name: str, exact_match: bool = False) -> List[CityInfo]:
        """
        Find cities by name

        Args:
            city_name: Name of the city to search for
            exact_match: Whether to perform exact matching

        Returns:
            List of matching CityInfo objects
        """
        cities = self.get_cities()
        matches = []

        search_term = city_name.lower().strip()

        for city in cities:
            city_display = city.display_name.lower()
            city_clean = city.clean_name.lower() if city.clean_name else ""

            if exact_match:
                if search_term == city_display or search_term == city_clean:
                    matches.append(city)
            else:
                if (
                    search_term in city_display
                    or search_term in city_clean
                    or city_display.startswith(search_term)
                    or city_clean.startswith(search_term)
                ):
                    matches.append(city)

        return matches

    def get_city_by_id(self, city_id: int) -> Optional[CityInfo]:
        """
        Get city information by ID

        Args:
            city_id: Numeric city ID

        Returns:
            CityInfo object or None if not found
        """
        cities = self.get_cities()
        for city in cities:
            if city.city_id == city_id:
                return city
        return None

    def get_current_weather(self, city_identifier: Union[int, str]) -> WeatherData:
        """
        Get current weather data for a city

        Args:
            city_identifier: Either city ID (int) or city name (str)

        Returns:
            WeatherData object

        Raises:
            CityNotFoundError: If city is not found
            NetworkError: If unable to fetch weather data
            IMDWeatherError: If parsing fails
        """
        city_id = self._resolve_city_id(city_identifier)

        try:
            url = f"{self.weather_url_prefix}{city_id}"
            response = safe_get(url)
            weather_data = self.parser.parse_past_24_hours(response.text)
            weather_data.city_id = city_id
            return weather_data
        except NetworkError:
            raise
        except Exception as e:
            raise IMDWeatherError(f"Failed to get current weather: {str(e)}")

    def get_forecast(self, city_identifier: Union[int, str]) -> ForecastData:
        """
        Get weather forecast for a city

        Args:
            city_identifier: Either city ID (int) or city name (str)

        Returns:
            ForecastData object

        Raises:
            CityNotFoundError: If city is not found
            NetworkError: If unable to fetch forecast data
            IMDWeatherError: If parsing fails
        """
        city_id = self._resolve_city_id(city_identifier)

        try:
            url = f"{self.weather_url_prefix}{city_id}"
            response = safe_get(url)
            forecast_data = self.parser.parse_forecast_table(response.text)
            forecast_data.city_id = city_id
            return forecast_data
        except NetworkError:
            raise
        except Exception as e:
            raise IMDWeatherError(f"Failed to get forecast: {str(e)}")

    def get_complete_weather_data(
        self, city_identifier: Union[int, str]
    ) -> tuple[WeatherData, ForecastData]:
        """
        Get both current weather and forecast data for a city

        Args:
            city_identifier: Either city ID (int) or city name (str)

        Returns:
            Tuple of (WeatherData, ForecastData)
        """
        city_id = self._resolve_city_id(city_identifier)

        try:
            url = f"{self.weather_url_prefix}{city_id}"
            response = safe_get(url)

            weather_data = self.parser.parse_past_24_hours(response.text)
            weather_data.city_id = city_id

            forecast_data = self.parser.parse_forecast_table(response.text)
            forecast_data.city_id = city_id

            return weather_data, forecast_data
        except NetworkError:
            raise
        except Exception as e:
            raise IMDWeatherError(f"Failed to get complete weather data: {str(e)}")

    def get_cities_dataframe(self) -> pd.DataFrame:
        """
        Get cities as a pandas DataFrame

        Returns:
            DataFrame with city information
        """
        cities = self.get_cities()
        data = []
        for city in cities:
            data.append(
                {
                    "city_id": city.city_id,
                    "display_name": city.display_name,
                    "clean_name": city.clean_name,
                    "full_value": city.full_value,
                }
            )
        return pd.DataFrame(data)

    def _resolve_city_id(self, city_identifier: Union[int, str]) -> int:
        """
        Resolve city identifier to city ID

        Args:
            city_identifier: Either city ID (int) or city name (str)

        Returns:
            City ID as integer

        Raises:
            CityNotFoundError: If city is not found
        """
        if isinstance(city_identifier, int):
            city = self.get_city_by_id(city_identifier)
            if not city:
                raise CityNotFoundError(f"City with ID {city_identifier} not found")
            return city_identifier

        # String identifier - search by name
        matches = self.find_city(city_identifier)
        if not matches:
            raise CityNotFoundError(f"No cities found matching '{city_identifier}'")

        if len(matches) == 1:
            return matches[0].city_id

        # Multiple matches - try exact match first
        exact_matches = self.find_city(city_identifier, exact_match=True)
        if len(exact_matches) == 1:
            return exact_matches[0].city_id

        # Still multiple matches - raise error with suggestions
        match_names = [
            city.display_name for city in matches[:5]
        ]  # Show first 5 matches
        raise CityNotFoundError(
            f"Multiple cities found matching '{city_identifier}'. "
            f"Please be more specific. Matches: {', '.join(match_names)}"
        )
