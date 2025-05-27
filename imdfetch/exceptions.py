"""
Custom exceptions for IMD Weather package
"""


class IMDWeatherError(Exception):
    """Base exception for all IMD Weather related errors"""

    pass


class NetworkError(IMDWeatherError):
    """Raised when network requests fail"""

    pass


class DataParsingError(IMDWeatherError):
    """Raised when data parsing fails"""

    pass


class CityNotFoundError(IMDWeatherError):
    """Raised when a city is not found in the IMD database"""

    pass


class InvalidDataError(IMDWeatherError):
    """Raised when received data is invalid or corrupted"""

    pass
