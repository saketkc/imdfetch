"""
IMD Weather - A Python package for fetching and parsing weather data from India Meteorological Department (IMD)
"""

__version__ = "0.1.0"
__author__ = "Saket Choudhary"
__email__ = "saketc@iitb.ac.in"

from .client import IMDWeatherClient
from .parser import WeatherDataParser
from .weather import WeatherData, ForecastData, CityInfo
from .exceptions import IMDWeatherError, DataParsingError, NetworkError

__all__ = [
    "IMDWeatherClient",
    "WeatherDataParser",
    "WeatherData",
    "ForecastData",
    "CityInfo",
    "IMDWeatherError",
    "DataParsingError",
    "NetworkError",
]
