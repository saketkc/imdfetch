"""
Constants used throughout the IMD Weather package
"""

# URLs
BASE_URL = "https://internal.imd.gov.in"
CITY_LIST_URL = f"{BASE_URL}/pages/city_weather_main_mausam.php"
WEATHER_URL_PREFIX = "https://city.imd.gov.in/citywx/city_weather.php?id="
WEATHER_TEST_URL_PREFIX = (
    "https://city.imd.gov.in/citywx/city_weather_test_try_warnings.php?id="
)
# Responsive-site JSON API: POST ID=<station_id> -> record incl. lat/lon/station
CITY_STATIC_API_URL = (
    "https://city.imd.gov.in/citywx/responsive/api/fetchCity_static.php"
)
CITY_STATIC_REFERER = "https://city.imd.gov.in/citywx/responsive/"
IP_GEOLOCATION_URLS = [
    "https://ipwho.is/",
    "https://ipapi.co/json/",
    "http://ip-api.com/json/",
]

# Plausible (lat, lon) bounds for India; rejects the API's null/placeholder
# coordinates. (lat_min, lat_max, lon_min, lon_max).
INDIA_BBOX = (6.0, 38.0, 67.0, 99.0)

# Request settings
DEFAULT_TIMEOUT = 10
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1.0

# Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Date formats
DATE_FORMATS = [
    "%B %d, %Y",  # May 27, 2025
    "%b %d, %Y",  # May 27, 2025
    "%d %B %Y",  # 27 May 2025
    "%d %b %Y",  # 27 May 2025
    "%d-%m-%Y",  # 27-05-2025
    "%d/%m/%Y",  # 27/05/2025
    "%m/%d/%Y",  # 05/27/2025
    "%Y-%m-%d",  # 2025-05-27
    "%d-%m-%y",  # 27-05-25
    "%d/%m/%y",  # 27/05/25
    "%d %b %y",  # 27 May 25
    "%b %d %Y",  # May 27 2025
]

# Month abbreviations
MONTH_ABBREV = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

# Canonical weather-parameter names — single source of truth shared by the HTML
# scraper (textfmt.clean_parameter_name) and the JSON API builder
# (client._weather_from_json), so the two paths can never drift apart.
WEATHER_PARAM_NAMES = {
    "max_temp": "Maximum Temperature (°C)",
    "max_dep": "Temperature Departure from Normal (°C)",
    "min_temp": "Minimum Temperature (°C)",
    "rainfall": "24 Hours Rainfall (mm)",
    "rh_0830": "Relative Humidity at 08:30 (%)",
    "rh_1730": "Relative Humidity at 17:30 (%)",
    "sunset": "Today's Sunset (IST)",
    "sunrise": "Tomorrow's Sunrise (IST)",
    "moonset": "Moonset (IST)",
    "moonrise": "Moonrise (IST)",
}

# JSON API field -> canonical-name key, in the output order WeatherData expects.
JSON_PARAM_FIELDS = [
    ("max", "max_temp"),
    ("maxdep", "max_dep"),
    ("min", "min_temp"),
    ("rainfall", "rainfall"),
    ("rh0830", "rh_0830"),
    ("rh1730", "rh_1730"),
    ("sunset", "sunset"),
    ("sunrise", "sunrise"),
    ("moonset", "moonset"),
    ("moonrise", "moonrise"),
]
