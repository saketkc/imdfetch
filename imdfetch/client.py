"""
Main client class for interacting with IMD weather services
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, overload

import pandas as pd

from .constants import (
    CITY_SEARCH_API_URL,
    CITY_STATIC_API_URL,
    CITY_STATIC_REFERER,
    INDIA_BBOX,
    IP_GEOLOCATION_URLS,
    JSON_PARAM_FIELDS,
    MAX_STATION_MATCHES,
    WEATHER_PARAM_NAMES,
    WEATHER_TEST_URL_PREFIX,
    WEATHER_URL_PREFIX,
)
from .exceptions import (
    AmbiguousCityError,
    CityNotFoundError,
    IMDWeatherError,
    NetworkError,
)
from .http import safe_get, safe_post
from .nowcast import fetch_nowcasts
from .parser import WeatherDataParser
from .weather import (
    CityInfo,
    DailyTemperature,
    ForecastData,
    ForecastDay,
    NowcastReport,
    TemperatureHistory,
    WeatherData,
    WeatherParameter,
)

logger = logging.getLogger(__name__)


def _clean(v: Any) -> Optional[str]:
    """Stripped string for a JSON value; None preserved. ``_clean(v) or ""``
    where an empty-string default is wanted (IMD values carry trailing \\r\\n)."""
    return None if v is None else str(v).strip()


def _date_or_none(v: Any) -> Optional[str]:
    """A date string, or None for empty values and IMD's literal "NA"."""
    text = _clean(v)
    return None if not text or text.upper() == "NA" else text


def _warning_text(rec: Dict, day: int) -> Optional[str]:
    """Readable warning for a forecast day, or None when there is no warning."""
    texts = rec.get("wText")
    text = _clean(texts[day]) if isinstance(texts, list) and day < len(texts) else None
    if text:
        return None if text.lower() == "no warning" else text
    code = _clean(rec.get(f"warning{day}")) or ""
    return f"IMD warning code {code}" if re.search(r"[1-9]", code) else None


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
                response = safe_get(CITY_SEARCH_API_URL, params={"query": ""})
                self._cities_cache = self.parser.parse_station_search(response.json())
            except NetworkError:
                raise
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

    @overload
    def get_current_weather(self, city_identifier: int) -> WeatherData: ...

    @overload
    def get_current_weather(
        self, city_identifier: str
    ) -> Union[WeatherData, List[WeatherData]]: ...

    def get_current_weather(
        self, city_identifier: Union[int, str]
    ) -> Union[WeatherData, List[WeatherData]]:
        """
        Get current weather data for a station, or every station in a city

        Args:
            city_identifier: Either city ID (int) or city name (str)

        Returns:
            WeatherData for an ID or a name identifying one station. A name
            matching several stations, such as "Mumbai", returns a list with one
            entry per station. A station that could not be fetched stays in the
            list with empty parameters.

        Raises:
            CityNotFoundError: If city is not found
            AmbiguousCityError: If a name matches over MAX_STATION_MATCHES stations
            NetworkError: If unable to fetch weather data
            IMDWeatherError: If parsing fails
        """
        try:
            return self._load_weather(city_identifier)
        except AmbiguousCityError as e:
            if len(e.matches) > MAX_STATION_MATCHES:
                raise
            return self._weather_for_stations(e.matches)

    def _load_weather(self, city_identifier: Union[int, str]) -> WeatherData:
        return self._load(
            city_identifier,
            self._weather_from_json,
            self._weather_from_html,
            "current weather",
        )

    def _weather_for_stations(self, cities: List[CityInfo]) -> List[WeatherData]:
        """Fetch several stations, keeping failed ones visible with no readings."""
        errors: List[IMDWeatherError] = []

        def fetch(city: CityInfo) -> WeatherData:
            try:
                return self._load_weather(city.city_id)
            except IMDWeatherError as e:
                logger.warning("Could not fetch station %s: %s", city.city_id, e)
                errors.append(e)
                return WeatherData(
                    city=city.display_name, date="", city_id=city.city_id
                )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(fetch, cities))
        if len(errors) == len(cities):
            raise errors[-1]
        return results

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
        return self._load(
            city_identifier,
            self._forecast_from_json,
            self._forecast_from_html,
            "forecast",
        )

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
        # One response yields both current conditions and the 7-day forecast.
        return self._load(
            city_identifier,
            lambda rec, cid: (
                self._weather_from_json(rec, cid),
                self._forecast_from_json(rec, cid),
            ),
            lambda html, cid: (
                self._weather_from_html(html, cid),
                self._forecast_from_html(html, cid),
            ),
            "complete weather data",
        )

    def _load(
        self,
        city_identifier: Union[int, str],
        from_json: Callable[[Dict, int], Any],
        from_html: Callable[[str, int], Any],
        label: str,
    ) -> Any:
        """Read IMD's JSON API, using the HTML page only if that yields nothing."""
        city_id = self._resolve_city_id(city_identifier)
        json_result = self._try_json(city_id, from_json)
        if json_result is not None:
            return json_result

        try:
            response = safe_get(f"{self.weather_url_prefix}{city_id}")
            return from_html(response.text, city_id)
        except NetworkError:
            raise
        except Exception as e:
            raise IMDWeatherError(f"Failed to get {label}: {str(e)}")

    def _weather_from_html(self, html: str, city_id: int) -> WeatherData:
        weather_data = self.parser.parse_past_24_hours(html)
        weather_data.city_id = city_id
        return weather_data

    def _forecast_from_html(self, html: str, city_id: int) -> ForecastData:
        forecast_data = self.parser.parse_forecast_table(html)
        forecast_data.city_id = city_id
        return forecast_data

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
            max_date=_date_or_none(rec.get("max_date")),
            updated_at=_date_or_none(rec.get("updat")),
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
                    warnings=_warning_text(rec, i),
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

        The HTML page lacks max_date and updat.
        """
        try:
            rec = self._fetch_city_static(city_id)
            if rec:
                return builder(rec, city_id)
            logger.warning("IMD JSON API had no record for station %s", city_id)
        except (NetworkError, ValueError, IMDWeatherError) as e:
            logger.warning("IMD JSON API failed for station %s: %s", city_id, e)
        return None

    @staticmethod
    def _post_city_static(city_id: int) -> Any:
        """POST to the JSON API: normally [station record, date-keyed history]."""
        resp = safe_post(
            CITY_STATIC_API_URL,
            data={"ID": city_id},
            extra_headers={"Referer": CITY_STATIC_REFERER},
        )
        return resp.json()

    def _fetch_city_static(self, city_id: int) -> Optional[Dict]:
        """Fetch a station's record from the responsive JSON API (incl. lat/lon)."""
        payload = self._post_city_static(city_id)
        rec = payload[0] if isinstance(payload, list) and payload else payload
        return rec if isinstance(rec, dict) else None

    def get_daily_temperatures(
        self, city_identifier: Union[int, str]
    ) -> TemperatureHistory:
        """
        Get past observations and upcoming predictions for a station

        IMD publishes up to 14 days: the past week, today and the next 6 days.
        Values IMD has not recorded or predicted are None.

        Args:
            city_identifier: Either city ID (int) or city name (str)

        Returns:
            TemperatureHistory with days in date order

        Raises:
            CityNotFoundError: If city is not found
            NetworkError: If unable to fetch data
            IMDWeatherError: If IMD's response has no usable history
        """
        city_id = self._resolve_city_id(city_identifier)
        try:
            payload = self._post_city_static(city_id)
        except ValueError as e:
            raise IMDWeatherError(f"Invalid response from IMD: {e}")

        rec, history = (
            payload[:2]
            if isinstance(payload, list) and len(payload) > 1
            else (None, None)
        )
        if not (isinstance(rec, dict) and isinstance(history, dict) and history):
            raise IMDWeatherError(f"IMD returned no history for station {city_id}")
        return self._history_from_json(rec, history, city_id)

    def get_nowcasts(self, area: Optional[str] = None) -> NowcastReport:
        """
        Get IMD nowcast alerts that are valid right now

        Args:
            area: Optional district or state name to match, e.g. "Chennai"

        Returns:
            NowcastReport

        Raises:
            NetworkError: If the feed or every current alert cannot be reached
            DataParsingError: If the alert feed is malformed
        """
        return fetch_nowcasts(area)

    @staticmethod
    def _history_from_json(
        rec: Dict, history: Dict, city_id: int
    ) -> TemperatureHistory:
        """Build a TemperatureHistory from the API's date-keyed second element."""
        return TemperatureHistory(
            city=_clean(rec.get("station")) or "",
            city_id=city_id,
            days=[
                DailyTemperature(
                    date=day,
                    max_temp=v.get("MAX"),
                    min_temp=v.get("MIN"),
                    normal_max=v.get("MAX_N"),
                    normal_min=v.get("MIN_N"),
                    forecast_max=v.get("F_MAX"),
                    forecast_min=v.get("F_MIN"),
                )
                for day, v in sorted(history.items())
                if isinstance(v, dict)
            ],
        )

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
        raise AmbiguousCityError(
            f"Multiple cities found matching '{city_identifier}'. "
            f"Please be more specific. Matches: {', '.join(match_names)}",
            matches,
        )
