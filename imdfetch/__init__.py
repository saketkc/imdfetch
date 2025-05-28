"""
IMD Weather - A Python package for fetching and parsing weather data from India Meteorological Department (IMD)
"""

__version__ = "0.1.0"
__author__ = "Saket Choudhary"
__email__ = "saketc@iitb.ac.in"

from .client import IMDWeatherClient
from .exceptions import DataParsingError, IMDWeatherError, NetworkError
from .parser import WeatherDataParser
from .weather import CityInfo, ForecastData, WeatherData

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
