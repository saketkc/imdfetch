"""
HTML parsing functions for extracting weather data
"""

import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
from bs4 import BeautifulSoup

from .exceptions import DataParsingError
from .utils import (
    clean_city_name,
    clean_parameter_name,
    convert_date_to_iso,
    parse_date,
)
from .weather import CityInfo, ForecastData, ForecastDay, WeatherData, WeatherParameter


class WeatherDataParser:
    """Parser for IMD weather data"""

    @staticmethod
    def parse_city_list(html_content: str) -> pd.DataFrame:
        """
        Extract city list from IMD main page

        Args:
            html_content: HTML content containing city options

        Returns:
            DataFrame with city information

        Raises:
            DataParsingError: If parsing fails
        """
        try:
            raw_data = []
            option_pattern = r"<option value='(\d+)([^']*)'>(.*?)</option>"

            matches = re.findall(option_pattern, html_content)

            if not matches:
                raise DataParsingError("No city data found in HTML content")

            for match in matches:
                full_value = match[0] + match[1]
                display_name = match[2]

                # Extract numeric ID
                id_match = re.match(r"^(\d{4,6})", full_value)
                if id_match:
                    city_id = int(id_match.group(1))
                    clean_name = display_name.strip()

                    raw_data.append(
                        {
                            "city_id": city_id,
                            "display_name": clean_name,
                            "full_value": full_value,
                        }
                    )

            raw_data.sort(key=lambda x: x["city_id"])
            return pd.DataFrame(raw_data)

        except Exception as e:
            raise DataParsingError(f"Failed to parse city list: {str(e)}")

    @staticmethod
    def parse_city_and_date(html_content: str) -> Dict[str, str]:
        """
        Extract city name and date from weather page

        Args:
            html_content: HTML content of weather page

        Returns:
            Dictionary with city and date information
        """
        result = {}

        # Extract city name
        font_city_pattern = r'Local Weather Report and Forecast For:\s*</b>\s*<FONT[^>]*color\s*=\s*["\']?blue["\']?[^>]*>([^<]+)</Font>'
        match = re.search(font_city_pattern, html_content, re.IGNORECASE)
        if match:
            city_text = match.group(1).strip()
            result["city"] = clean_city_name(city_text)
            result["raw_city_text"] = city_text

        # Extract date
        dated_b_pattern = r"<B>Dated\s*:\s*([^<]+)</b>"
        match = re.search(dated_b_pattern, html_content, re.IGNORECASE)
        if match:
            date_text = match.group(1).strip()
            parsed_date = parse_date(date_text)
            if parsed_date:
                result["date"] = parsed_date
                result["raw_date_text"] = date_text

        return result

    @staticmethod
    def parse_past_24_hours(html_content: str) -> WeatherData:
        """
        Extract Past 24 Hours Weather Data from HTML

        Args:
            html_content: HTML content containing the weather table

        Returns:
            WeatherData object

        Raises:
            DataParsingError: If parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Get city and date info
            city_date_info = WeatherDataParser.parse_city_and_date(html_content)

            # Find the table containing "Past 24 Hours Weather Data"
            past_24_table = None
            for table in soup.find_all("table"):
                if "Past 24 Hours Weather Data" in table.get_text():
                    past_24_table = table
                    break

            if not past_24_table:
                raise DataParsingError("Past 24 Hours Weather Data table not found")

            # Extract all rows
            rows = past_24_table.find_all("tr")
            parameters = []

            for row in rows:
                cells = row.find_all(["td", "th"])

                # Skip rows that don't have exactly 2 cells
                if len(cells) != 2:
                    continue

                param_text = cells[0].get_text(strip=True)
                value_text = cells[1].get_text(strip=True)

                # Skip the header row and empty rows
                if (
                    "Past 24 Hours Weather Data" in param_text
                    or not param_text
                    or not value_text
                ):
                    continue

                clean_param = clean_parameter_name(param_text)
                parameters.append(
                    WeatherParameter(
                        parameter=clean_param,
                        value=value_text,
                        raw_parameter=param_text,
                    )
                )

            return WeatherData(
                city=city_date_info.get("city", "Unknown"),
                date=city_date_info.get("date", ""),
                raw_city_text=city_date_info.get("raw_city_text"),
                raw_date_text=city_date_info.get("raw_date_text"),
                parameters=parameters,
            )

        except Exception as e:
            raise DataParsingError(f"Failed to parse past 24 hours data: {str(e)}")

    @staticmethod
    def parse_forecast_table(html_content: str) -> ForecastData:
        """
        Extract 7-day weather forecast table from HTML content

        Args:
            html_content: HTML content containing the weather table

        Returns:
            ForecastData object

        Raises:
            DataParsingError: If parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, "html.parser")

            # Get city and date info
            city_date_info = WeatherDataParser.parse_city_and_date(html_content)

            # Find the table containing "7 Day's Forecast"
            forecast_table = None
            for table in soup.find_all("table"):
                table_text = table.get_text()
                if "7 Day's Forecast" in table.get_text():
                    forecast_table = table
                    break
            if not forecast_table:
                raise DataParsingError("7-day forecast table not found")

            rows = forecast_table.find_all("tr")
            # Find header row
            header_row = None
            for i, row in enumerate(rows):
                row_text = row.get_text()
                if "Date" in row_text and (
                    "Min Temp" in row_text or "Max Temp" in row_text
                ):
                    header_row = i
                    break

            if header_row is None:
                raise DataParsingError("Header row not found in forecast table")

            # Extract forecast days
            forecast_days = []
            for row in rows[(header_row + 1) :]:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 7:
                    cell_texts = [cell.get_text(strip=True) for cell in cells]
                    if len(cell_texts) >= 9:
                        date = cell_texts[0]
                        min_temp = cell_texts[1]
                        max_temp = cell_texts[2]
                        # Skip image cell (cell_texts[3])
                        forecast = cell_texts[4]
                        # Skip warning image cell (cell_texts[5])
                        warnings = cell_texts[6]
                        rh_0830 = cell_texts[7]
                        rh_1730 = cell_texts[8]
                        # Only add if we have a valid date
                        if date and re.match(r"\d{2}-[A-Za-z]{3}", date):
                            iso_date = convert_date_to_iso(date)
                            forecast_days.append(
                                ForecastDay(
                                    date=date,
                                    min_temp=min_temp,
                                    max_temp=max_temp,
                                    forecast=forecast,
                                    warnings=warnings if warnings else None,
                                    rh_0830=rh_0830 if rh_0830 else None,
                                    rh_1730=rh_1730 if rh_1730 else None,
                                    iso_date=iso_date,
                                )
                            )

            return ForecastData(
                city=city_date_info.get("city", "Unknown"),
                forecast_date=city_date_info.get("date", ""),
                days=forecast_days,
            )

        except Exception as e:
            raise DataParsingError(f"Failed to parse forecast data: {str(e)}")

    @staticmethod
    def get_cities_dataframe(html_content: str) -> List[CityInfo]:
        """
        Get list of cities as CityInfo objects

        Args:
            html_content: HTML content from city list page

        Returns:
            List of CityInfo objects
        """
        df = WeatherDataParser.parse_city_list(html_content)
        cities = []

        for _, row in df.iterrows():
            city_info = CityInfo(
                city_id=row["city_id"],
                display_name=row["display_name"],
                full_value=row["full_value"],
                clean_name=clean_city_name(row["display_name"]),
            )
            cities.append(city_info)

        return cities
