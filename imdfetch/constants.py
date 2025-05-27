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
