"""
Data models for weather information
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class CityInfo:
    """Information about a city/weather station"""
    city_id: int
    display_name: str
    full_value: str
    clean_name: Optional[str] = None


@dataclass
class WeatherParameter:
    """Individual weather parameter with value"""
    parameter: str
    value: str
    raw_parameter: Optional[str] = None


@dataclass
class WeatherData:
    """Current weather data for a location"""
    city: str
    date: str
    city_id: Optional[int] = None
    raw_city_text: Optional[str] = None
    raw_date_text: Optional[str] = None
    parameters: List[WeatherParameter] = field(default_factory=list)
    
    def get_parameter(self, param_name: str) -> Optional[str]:
        """Get value of a specific parameter"""
        for param in self.parameters:
            if param_name.lower() in param.parameter.lower():
                return param.value
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'city': self.city,
            'date': self.date,
            'city_id': self.city_id,
            'raw_city_text': self.raw_city_text,
            'raw_date_text': self.raw_date_text,
            'parameters': {param.parameter: param.value for param in self.parameters}
        }


@dataclass
class ForecastDay:
    """Single day forecast data"""
    date: str
    min_temp: str
    max_temp: str
    forecast: str
    warnings: Optional[str] = None
    rh_0830: Optional[str] = None
    rh_1730: Optional[str] = None
    iso_date: Optional[str] = None


@dataclass
class ForecastData:
    """Multi-day weather forecast"""
    city: str
    forecast_date: str
    city_id: Optional[int] = None
    days: List[ForecastDay] = field(default_factory=list)
    
    def get_day_forecast(self, date: str) -> Optional[ForecastDay]:
        """Get forecast for a specific date"""
        for day in self.days:
            if day.date == date or day.iso_date == date:
                return day
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'city': self.city,
            'forecast_date': self.forecast_date,
            'city_id': self.city_id,
            'days': [
                {
                    'date': day.date,
                    'min_temp': day.min_temp,
                    'max_temp': day.max_temp,
                    'forecast': day.forecast,
                    'warnings': day.warnings,
                    'rh_0830': day.rh_0830,
                    'rh_1730': day.rh_1730,
                    'iso_date': day.iso_date
                }
                for day in self.days
            ]
        }
