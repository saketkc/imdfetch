"""
Main client class for interacting with IMD weather services
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pandas as pd

from .constants import (
    CITY_LIST_URL,
    CITY_STATIC_API_URL,
    CITY_STATIC_REFERER,
    INDIA_BBOX,
    IP_GEOLOCATION_URLS,
    JSON_PARAM_FIELDS,
    WEATHER_PARAM_NAMES,
    WEATHER_TEST_URL_PREFIX,
    WEATHER_URL_PREFIX,
)
from .exceptions import CityNotFoundError, IMDWeatherError, NetworkError
from .http import safe_get, safe_post
from .parser import WeatherDataParser
from .weather import (
    CityInfo,
    ForecastData,
    ForecastDay,
    WeatherData,
    WeatherParameter,
)


def _clean(v: Any) -> Optional[str]:
    """Stripped string for a JSON value; None preserved. ``_clean(v) or ""``
    where an empty-string default is wanted (IMD values carry trailing \\r\\n)."""
    return None if v is None else str(v).strip()


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

        json_result = self._try_json(city_id, self._weather_from_json)
        if json_result is not None:
            return json_result

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

        json_result = self._try_json(city_id, self._forecast_from_json)
        if json_result is not None:
            return json_result

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

        # One JSON call yields both current conditions and the 7-day forecast.
        json_result = self._try_json(
            city_id,
            lambda rec, cid: (
                self._weather_from_json(rec, cid),
                self._forecast_from_json(rec, cid),
            ),
        )
        if json_result is not None:
            return json_result

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

    @staticmethod
    def _weather_from_json(rec: Dict, city_id: int) -> WeatherData:
        """Build a WeatherData (current conditions) from a fetchCity_static record.

        Parameter names match the legacy HTML scraper exactly, so downstream
        consumers (and CSV column names) are unchanged.
        """
        params = [
            WeatherParameter(
                parameter=WEATHER_PARAM_NAMES[key],
                value=_clean(rec.get(json_key)) or "",
            )
            for json_key, key in JSON_PARAM_FIELDS
        ]
        # JSON values carry trailing \r\n
        station = _clean(rec.get("station")) or ""
        date_text = _clean(rec.get("dat")) or ""
        return WeatherData(
            city=station,
            date=date_text,
            city_id=city_id,
            raw_city_text=station,
            raw_date_text=date_text,
            parameters=params,
        )

    @staticmethod
    def _forecast_from_json(rec: Dict, city_id: int) -> ForecastData:
        """Build a 7-day ForecastData from a fetchCity_static record.

        Day i (0..6) is the issue date + i days; day 0 is the issue date.
        """
        issue = str(rec.get("dat") or "")
        try:
            issue_dt = datetime.strptime(issue, "%Y-%m-%d")
        except ValueError:
            issue_dt = None

        days: List[ForecastDay] = []
        for i in range(7):
            if rec.get(f"forecast{i}") is None and rec.get(f"max{i}") is None:
                continue
            if issue_dt is not None:
                day_dt = issue_dt + timedelta(days=i)
                iso_date = day_dt.strftime("%Y-%m-%d")
                disp = day_dt.strftime("%d-%b")
            else:
                iso_date = ""
                disp = ""

            days.append(
                ForecastDay(
                    date=disp,
                    min_temp=_clean(rec.get(f"min{i}")) or "",
                    max_temp=_clean(rec.get(f"max{i}")) or "",
                    forecast=_clean(rec.get(f"forecast{i}")) or "",
                    warnings=_clean(rec.get(f"warning{i}")),
                    rh_0830=_clean(rec.get(f"rh0830d{i}")),
                    rh_1730=_clean(rec.get(f"rh1730d{i}")),
                    iso_date=iso_date,
                )
            )

        return ForecastData(
            city=_clean(rec.get("station")) or "",
            forecast_date=issue,
            city_id=city_id,
            days=days,
        )

    def _try_json(
        self, city_id: int, builder: Callable[[Dict, int], Any]
    ) -> Optional[Any]:
        """Build a result from the responsive JSON API, or None to fall back.

        IMD migrated city.imd.gov.in to a SPA backed by a JSON API; the old HTML
        "Past 24 Hours" table no longer exists. Callers try this first and fall
        back to the legacy HTML scrape only when it returns None.
        """
        try:
            rec = self._fetch_city_static(city_id)
            if rec:
                return builder(rec, city_id)
        except (NetworkError, ValueError, IMDWeatherError):
            pass
        return None

    def _fetch_city_static(self, city_id: int) -> Optional[Dict]:
        """Fetch a station's record from the responsive JSON API (incl. lat/lon)."""
        resp = safe_post(
            CITY_STATIC_API_URL,
            data={"ID": city_id},
            extra_headers={"Referer": CITY_STATIC_REFERER},
        )
        payload = resp.json()
        rec = payload[0] if isinstance(payload, list) and payload else payload
        return rec if isinstance(rec, dict) else None

    @staticmethod
    def _extract_latlon(rec: Optional[Dict]) -> Optional[Tuple[float, float]]:
        """Pull a sane (lat, lon) out of an API record, or None."""
        if not rec:
            return None
        try:
            lat = float(str(rec.get("lat")))
            lon = float(str(rec.get("lon")))
        except (TypeError, ValueError):
            return None
        lat_min, lat_max, lon_min, lon_max = INDIA_BBOX
        if not (lat_min <= lat <= lat_max and lon_min <= lon <= lon_max):
            return None
        return (lat, lon)

    def get_coordinates(
        self, city_identifier: Union[int, str]
    ) -> Optional[Tuple[float, float]]:
        """
        Get (latitude, longitude) for a station from IMD's responsive API.

        Args:
            city_identifier: station ID (int) or city name (str)

        Returns:
            (latitude, longitude) in decimal degrees, or None if IMD has no
            coordinates for this station.
        """
        city_id = self._resolve_city_id(city_identifier)
        try:
            rec = self._fetch_city_static(city_id)
        except (NetworkError, ValueError, IMDWeatherError):
            return None
        return self._extract_latlon(rec)

    def get_cities_with_coordinates(
        self, max_workers: int = 8, refresh_cache: bool = False
    ) -> List[CityInfo]:
        """
        Return the city list enriched with latitude/longitude/station_name.

        Coordinates are fetched concurrently from IMD's responsive API and cached
        on the CityInfo objects. Stations IMD has no coordinates for keep
        latitude/longitude as None.

        Args:
            max_workers: concurrent requests to the IMD API
            refresh_cache: re-fetch the city list before enriching

        Returns:
            List of CityInfo with coordinate fields populated where available.
        """
        cities = self.get_cities(refresh_cache=refresh_cache)

        def enrich(city: CityInfo) -> None:
            if city.latitude is not None:  # already resolved
                return
            try:
                rec = self._fetch_city_static(city.city_id)
            except (NetworkError, ValueError, IMDWeatherError):
                return
            latlon = self._extract_latlon(rec)
            if latlon:
                city.latitude, city.longitude = latlon
                city.station_name = (rec or {}).get("station")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for _ in executor.map(enrich, cities):  # drain; enrich mutates in place
                pass
        return cities

    @staticmethod
    def _extract_any_latlon(rec: Optional[Dict]) -> Optional[Tuple[float, float]]:
        """Pull latitude/longitude from a generic geolocation response."""
        if not rec:
            return None

        lat_value = rec.get("latitude", rec.get("lat"))
        lon_value = rec.get("longitude", rec.get("lon"))
        loc_value = rec.get("loc")
        if (lat_value is None or lon_value is None) and isinstance(loc_value, str):
            parts = loc_value.split(",", 1)
            if len(parts) == 2:
                lat_value, lon_value = parts

        try:
            lat = float(str(lat_value))
            lon = float(str(lon_value))
        except (TypeError, ValueError):
            return None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return (lat, lon)

    def get_ip_coordinates(self) -> Tuple[float, float]:
        """Get approximate caller coordinates from the current public IP address."""
        errors = []
        for url in IP_GEOLOCATION_URLS:
            try:
                response = safe_get(url, max_retries=0, timeout=5)
                rec = response.json()
            except Exception as e:
                errors.append(f"{url}: {e}")
                continue

            latlon = self._extract_any_latlon(rec if isinstance(rec, dict) else None)
            if latlon is not None:
                return latlon
            errors.append(f"{url}: response did not include coordinates")

        detail = "; ".join(errors) if errors else "no providers configured"
        raise NetworkError(f"Failed to determine location from IP address ({detail})")

    @staticmethod
    def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance between two coordinates in kilometers."""
        radius_km = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        rlat1 = radians(lat1)
        rlat2 = radians(lat2)
        a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
        return 2 * radius_km * asin(sqrt(a))

    def get_nearest_city(
        self, latitude: float, longitude: float, max_workers: int = 8
    ) -> CityInfo:
        """Return the nearest IMD weather station to a coordinate."""
        cities = [
            city
            for city in self.get_cities_with_coordinates(max_workers=max_workers)
            if city.latitude is not None and city.longitude is not None
        ]
        if not cities:
            raise CityNotFoundError("No IMD stations with coordinates were found")

        return min(
            cities,
            key=lambda city: self._distance_km(
                latitude, longitude, city.latitude or 0.0, city.longitude or 0.0
            ),
        )

    def get_current_weather_for_ip(self) -> WeatherData:
        """Get current weather for the IMD station nearest to this public IP."""
        latitude, longitude = self.get_ip_coordinates()
        city = self.get_nearest_city(latitude, longitude)
        return self.get_current_weather(city.city_id)

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

        matches = self.find_city(city_identifier)
        if not matches:
            raise CityNotFoundError(f"No cities found matching '{city_identifier}'")

        if len(matches) == 1:
            return matches[0].city_id

        exact_matches = self.find_city(city_identifier, exact_match=True)
        if len(exact_matches) == 1:
            return exact_matches[0].city_id

        match_names = [
            city.display_name for city in matches[:5]
        ]  # Show first 5 matches
        raise CityNotFoundError(
            f"Multiple cities found matching '{city_identifier}'. "
            f"Please be more specific. Matches: {', '.join(match_names)}"
        )
