"""
Utility functions for IMD Weather package
"""

import re
import time
import ssl
from datetime import datetime
from typing import Optional, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

from .constants import (
    DEFAULT_TIMEOUT,
    DEFAULT_MAX_RETRIES,
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_HEADERS,
    DATE_FORMATS,
    MONTH_ABBREV,
)
from .exceptions import NetworkError

# Disable SSL warnings if needed (optional)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def make_robust_request(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    timeout: int = DEFAULT_TIMEOUT,
    verify_ssl: bool = True,
) -> Optional[requests.Response]:
    """
    Make HTTP request with retry logic and SSL error handling

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for exponential retry delay
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Response object if successful, None if all retries failed

    Raises:
        NetworkError: If all retries failed
    """

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(
                url, headers=DEFAULT_HEADERS, timeout=timeout, verify=verify_ssl
            )
            response.raise_for_status()
            return response

        except requests.exceptions.SSLError as e:
            print(f"SSL Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

            if attempt < max_retries:
                try:
                    print("Retrying with SSL verification disabled...")
                    response = requests.get(
                        url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False
                    )
                    response.raise_for_status()
                    print("✅ Request succeeded with SSL verification disabled")
                    return response
                except Exception as fallback_error:
                    print(f"❌ Fallback also failed: {fallback_error}")

        except requests.exceptions.ConnectionError as e:
            print(f"Connection Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except requests.exceptions.Timeout as e:
            print(f"Timeout Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except requests.exceptions.RequestException as e:
            print(f"Request Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        except Exception as e:
            print(f"Unexpected Error on attempt {attempt + 1}/{max_retries + 1}: {e}")

        # Wait before retrying (exponential backoff)
        if attempt < max_retries:
            wait_time = backoff_factor * (2**attempt)
            print(f"⏳ Waiting {wait_time:.1f} seconds before retry...")
            time.sleep(wait_time)

    print(f"❌ All {max_retries + 1} attempts failed")
    raise NetworkError(
        f"Failed to fetch data from {url} after {max_retries + 1} attempts"
    )


def make_request_with_session(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[requests.Response]:
    """
    Alternative approach using requests Session with built-in retry strategy

    Args:
        url: URL to fetch
        max_retries: Maximum number of retry attempts
        backoff_factor: Backoff factor for retry delay
        timeout: Request timeout in seconds

    Returns:
        Response object if successful, None if failed
    """

    session = requests.Session()

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    try:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        response.raise_for_status()
        return response

    except requests.exceptions.SSLError as e:
        print(f"SSL Error with session: {e}")
        try:
            print("Retrying with SSL verification disabled...")
            response = session.get(
                url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False
            )
            response.raise_for_status()
            return response
        except Exception as fallback_error:
            print(f"Session fallback failed: {fallback_error}")
            return None

    except Exception as e:
        print(f"Session request failed: {e}")
        return None

    finally:
        session.close()


def safe_get(
    url: str, max_retries: int = DEFAULT_MAX_RETRIES, timeout: int = DEFAULT_TIMEOUT
) -> requests.Response:
    """
    Simple drop-in replacement for requests.get() with retry logic

    Args:
        url: URL to fetch
        max_retries: Maximum retry attempts
        timeout: Request timeout

    Returns:
        requests.Response object

    Raises:
        NetworkError: If request fails after all retries
    """
    return make_robust_request(url, max_retries=max_retries, timeout=timeout)


def parse_date(date_text: str) -> Optional[str]:
    """
    Parse various date formats commonly found on IMD pages

    Args:
        date_text: Raw date text

    Returns:
        Standardized date in YYYY-MM-DD format, or None if parsing fails
    """
    if not date_text:
        return None

    # Clean the date text
    date_text = re.sub(r"[^\w\s\/\-,:]", "", date_text.strip())

    for fmt in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_text, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def clean_city_name(city_text: str) -> Optional[str]:
    """
    Clean and standardize city name

    Args:
        city_text: Raw city text

    Returns:
        Cleaned city name
    """
    if not city_text:
        return None

    # Remove extra whitespace
    city = re.sub(r"\s+", " ", city_text.strip())

    # Remove common prefixes/suffixes that aren't part of city name
    city = re.sub(r"^(For|Weather|Report|Forecast):\s*", "", city, flags=re.IGNORECASE)
    city = re.sub(
        r"\s*(Weather|Report|Forecast|Station|Airport|City)$",
        "",
        city,
        flags=re.IGNORECASE,
    )

    # Remove any remaining HTML artifacts
    city = re.sub(r"[<>]", "", city)

    # Capitalize properly
    city = city.title()

    # Handle special cases
    city = city.replace("-", "-")  # Normalize hyphens

    return city.strip()


def convert_date_to_iso(date_str: str) -> Optional[str]:
    """
    Convert dates like "27-May", "2-Jun" to YYYY-MM-DD format using current year

    Args:
        date_str: Date string in format "DD-MMM" (e.g., "27-May", "2-Jun")

    Returns:
        Date in YYYY-MM-DD format, or None if parsing fails
    """
    if not date_str:
        return None

    current_year = datetime.now().year

    try:
        # Split by dash and clean
        parts = date_str.strip().replace("-", " ").replace("  ", " ").split(" ")
        if len(parts) != 2:
            return None

        day, month_abbr = parts

        # Convert day to 2-digit format
        day = day.zfill(2)

        # Convert month abbreviation to number
        month_key = month_abbr.lower()[:3]
        if month_key not in MONTH_ABBREV:
            return None

        month = MONTH_ABBREV[month_key]

        # Return in YYYY-MM-DD format
        return f"{current_year}-{month}-{day}"

    except Exception:
        return None


def clean_parameter_name(param_text: str) -> str:
    """
    Clean up parameter names for better readability
    """
    # Remove extra characters and standardize format
    param_text = param_text.replace("(", "").replace(")", "")
    param_text = param_text.replace("°C", "°C")
    param_text = param_text.replace("  ", " ")

    # Standardize common parameter names
    if "Maximum Temp" in param_text:
        return "Maximum Temperature (°C)"
    elif "Minimum Temp" in param_text:
        return "Minimum Temperature (°C)"
    elif "Departure from Normal" in param_text:
        if "max" in param_text.lower():
            return "Max Temp Departure from Normal (°C)"
        elif "min" in param_text.lower():
            return "Min Temp Departure from Normal (°C)"
        else:
            return "Temperature Departure from Normal (°C)"
    elif "24 Hours Rainfall" in param_text:
        return "24 Hours Rainfall (mm)"
    elif "Relative Humidity at 0830" in param_text:
        return "Relative Humidity at 08:30 (%)"
    elif "Relative Humidity at 1730" in param_text:
        return "Relative Humidity at 17:30 (%)"
    elif "Sunset" in param_text:
        return "Today's Sunset (IST)"
    elif "Sunrise" in param_text:
        return "Tomorrow's Sunrise (IST)"
    elif "Moonset" in param_text:
        return "Moonset (IST)"
    elif "Moonrise" in param_text:
        return "Moonrise (IST)"
    else:
        return param_text


def colorize_temperature(temp: float, unit: str = "°C") -> str:
    """
    Color-code temperature values based on ranges.

    Args:
        temp: Temperature value in Celsius
        unit: Temperature unit to append (default: "°C")

    Returns:
        Colored temperature string with ANSI escape codes
    """
    if isinstance(temp, str):
        if temp.upper() in ["NA", "N/A", "-", "--", ""]:
            return f"{temp}"
        try:
            temp = float(temp)
        except ValueError:
            return f"{temp}{unit}"
    # ANSI color codes
    RESET = "\033[0m"
    BLUE = "\033[94m"  # Cold: < 10°C
    CYAN = "\033[96m"  # Cool: 10-20°C
    GREEN = "\033[92m"  # Comfortable: 20-25°C
    YELLOW = "\033[93m"  # Warm: 25-30°C
    ORANGE = "\033[38;5;208m"  # Hot: 30-35°C
    RED = "\033[91m"  # Very Hot: > 35°C

    # Determine color based on temperature range
    if temp < 10:
        color = BLUE
    elif temp < 20:
        color = CYAN
    elif temp < 25:
        color = GREEN
    elif temp < 30:
        color = YELLOW
    elif temp < 35:
        color = ORANGE
    else:
        color = RED

    return f"{color}{temp}{unit}{RESET}"


def get_temperature_legend() -> str:
    """
    Get a legend showing temperature color coding.

    Returns:
        Formatted legend string
    """
    RESET = "\033[0m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    ORANGE = "\033[38;5;208m"
    RED = "\033[91m"

    legend = "Temperature Color Legend:\n"
    legend += f"  {BLUE}■{RESET} < 10°C (Cold)\n"
    legend += f"  {CYAN}■{RESET} 10-20°C (Cool)\n"
    legend += f"  {GREEN}■{RESET} 20-25°C (Comfortable)\n"
    legend += f"  {YELLOW}■{RESET} 25-30°C (Warm)\n"
    legend += f"  {ORANGE}■{RESET} 30-35°C (Hot)\n"
    legend += f"  {RED}■{RESET} > 35°C (Very Hot)"

    return legend


def get_humidity_legend() -> str:
    """
    Get a legend showing humidity color coding.

    Returns:
        Formatted legend string
    """
    RESET = "\033[0m"
    BROWN = "\033[38;5;130m"
    YELLOW = "\033[93m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"

    legend = "Relative Humidity Color Legend:\n"
    legend += f"  {BROWN}■{RESET} < 30% (Very Dry)\n"
    legend += f"  {YELLOW}■{RESET} 30-40% (Dry)\n"
    legend += f"  {GREEN}■{RESET} 40-60% (Comfortable)\n"
    legend += f"  {CYAN}■{RESET} 60-70% (Humid)\n"
    legend += f"  {BLUE}■{RESET} 70-80% (Very Humid)\n"
    legend += f"  {PURPLE}■{RESET} > 80% (Extremely Humid)"

    return legend


def colorize_humidity(humidity: float, unit: str = "%") -> str:
    """
    Color-code relative humidity values based on comfort ranges.

    Args:
        humidity: Relative humidity percentage (0-100)
        unit: Unit to append (default: "%")

    Returns:
        Colored humidity string with ANSI escape codes
    """
    if isinstance(humidity, str):
        if humidity.upper() in ["NA", "N/A", "-", "--", ""]:
            return f"{humidity}"
        try:
            humidity = float(humidity)
        except ValueError:
            return f"{humidity}{unit}"

    # ANSI color codes
    RESET = "\033[0m"
    BROWN = "\033[38;5;130m"  # Very Dry: < 30%
    YELLOW = "\033[93m"  # Dry: 30-40%
    GREEN = "\033[92m"  # Comfortable: 40-60%
    CYAN = "\033[96m"  # Humid: 60-70%
    BLUE = "\033[94m"  # Very Humid: 70-80%
    PURPLE = "\033[95m"  # Extremely Humid: > 80%

    # Determine color based on humidity range
    if humidity < 30:
        color = BROWN
    elif humidity < 40:
        color = YELLOW
    elif humidity < 60:
        color = GREEN
    elif humidity < 70:
        color = CYAN
    elif humidity < 80:
        color = BLUE
    else:
        color = PURPLE

    return f"{color}{humidity}{unit}{RESET}"


def get_combined_legend() -> str:
    """
    Get a combined legend showing both temperature and humidity color coding.

    Returns:
        Formatted legend string
    """
    return get_temperature_legend() + "\n\n" + get_humidity_legend()


def format_date(date_str: str, include_day: bool = True) -> str:
    """
    Format date string to a more readable format with day of week.

    Args:
        date_str: Date string in various formats (e.g., "2027-05-25", "25-05-2027", "25/05/2027")
        include_day: Whether to include the day of week

    Returns:
        Formatted date string like "25 May, 2027 (Tuesday)"
    """

    # Try different date formats
    date_formats = [
        "%Y-%m-%d",  # ISO format: 2027-05-25
        "%d-%m-%Y",  # DD-MM-YYYY: 25-05-2027
        "%d/%m/%Y",  # DD/MM/YYYY: 25/05/2027
        "%d %b %Y",  # DD Mon YYYY: 25 May 2027
        "%d %B %Y",  # DD Month YYYY: 25 May 2027
    ]

    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_str.strip(), fmt)
            # Format the date
            formatted = date_obj.strftime("%d %B, %Y")
            if include_day:
                day_name = date_obj.strftime("%A")
                formatted += f" ({day_name})"
            return formatted
        except ValueError:
            continue

    # If no format matches, return the original string
    return date_str
