#!/usr/bin/env python3
"""
Command-line interface for IMD Weather package
"""

import argparse
import sys
import json
from typing import Optional

from . import IMDWeatherClient
from .exceptions import IMDWeatherError, CityNotFoundError
from .utils import colorize_temperature, colorize_humidity, format_date


def search_cities(
    client: IMDWeatherClient, city_name: str, exact: bool = False
) -> None:
    """Search for cities and display results"""
    try:
        cities = client.find_city(city_name, exact_match=exact)
        if not cities:
            print(f"❌ No cities found matching '{city_name}'")
            return

        print(f"🏙️  Found {len(cities)} cities matching '{city_name}':")
        for city in cities:
            print(f"   📍 {city.display_name} (ID: {city.city_id})")

    except Exception as e:
        print(f"❌ Error searching cities: {e}")
        sys.exit(1)


def get_weather(
    client: IMDWeatherClient, city_identifier: str, output_format: str = "text"
) -> None:
    """Get current weather for a city"""
    try:
        # Try to convert to int if it's a number
        if city_identifier.isdigit():
            city_identifier = int(city_identifier)

        weather = client.get_current_weather(city_identifier)

        if output_format == "json":
            print(json.dumps(weather.to_dict(), indent=2))
        else:
            print(f"🌤️ Current Weather for {weather.city}")
            print(f"📅 Date: {format_date(weather.date)}")

            # Get temperature values
            max_temp = weather.get_parameter("Maximum Temperature")
            min_temp = weather.get_parameter("Minimum Temperature")

            # Get humidity values
            humidity_0830 = weather.get_parameter("Relative Humidity at 08:30")
            humidity_1730 = weather.get_parameter("Relative Humidity at 17:30")

            # Display with color coding
            print(f"🌡️ Max Temperature: {colorize_temperature(max_temp)}")
            print(f"🌡️ Min Temperature: {colorize_temperature(min_temp)}")
            print(f"🌧️ 24h Rainfall (mm): {weather.get_parameter('24 Hours Rainfall')}")
            print(f"💧 Relative Humidity at 08:30: {colorize_humidity(humidity_0830)}")
            print(f"💧 Relative Humidity at 17:30: {colorize_humidity(humidity_1730)}")

    except CityNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error getting weather: {e}")
        sys.exit(1)


def get_forecast(
    client: IMDWeatherClient,
    city_identifier: str,
    days: int = 7,
    output_format: str = "text",
) -> None:
    """Get weather forecast for a city"""
    try:
        # Try to convert to int if it's a number
        if city_identifier.isdigit():
            city_identifier = int(city_identifier)

        forecast = client.get_forecast(city_identifier)
        if output_format == "json":
            print(json.dumps(forecast.to_dict(), indent=2))
        else:
            print(f"🔮 {days}-Day Weather Forecast for {forecast.city}")
            print(f"📅 Forecast Date: {format_date(forecast.forecast_date)}")
            print("-" * 50)
            for i, day in enumerate(forecast.days[:days]):
                print(f"📅 {format_date(day.iso_date)}")
                # Color code the temperature range
                min_colored = colorize_temperature(day.min_temp)
                max_colored = colorize_temperature(day.max_temp)
                print(f"   🌡️  Temperature: {min_colored} - {max_colored}")
                print(f"   🌤️  Forecast: {day.forecast}")
                if day.warnings:
                    print(f"   ⚠️  Warnings: {day.warnings}")
                print()

    except CityNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error getting forecast: {e}")
        sys.exit(1)


def list_cities(client: IMDWeatherClient, limit: Optional[int] = None) -> None:
    """List all available cities"""
    try:
        cities = client.get_cities()
        total_cities = len(cities)

        if limit:
            cities = cities[:limit]
            print(f"🏙️  Showing {len(cities)} of {total_cities} available cities:")
        else:
            print(f"🏙️  All {total_cities} available cities:")

        for city in cities:
            print(f"   📍 {city.display_name} (ID: {city.city_id})")

        if limit and limit < total_cities:
            print(f"\n... and {total_cities - limit} more cities")
            print("Use --limit 0 to show all cities")

    except Exception as e:
        print(f"❌ Error listing cities: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="IMD Weather CLI - Get weather data from India Meteorological Department",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  imd-weather search Mumbai
  imd-weather weather "Delhi"
  imd-weather weather 12001
  imd-weather forecast "Bangalore" --days 5
  imd-weather cities --limit 10
        """,
    )

    parser.add_argument(
        "--test", action="store_true", help="Use test endpoint (if available)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for cities")
    search_parser.add_argument("city_name", help="City name to search for")
    search_parser.add_argument(
        "--exact", action="store_true", help="Perform exact match search"
    )

    # Weather command
    weather_parser = subparsers.add_parser("weather", help="Get current weather")
    weather_parser.add_argument("city", help="City name or ID")

    # Forecast command
    forecast_parser = subparsers.add_parser("forecast", help="Get weather forecast")
    forecast_parser.add_argument("city", help="City name or ID")
    forecast_parser.add_argument(
        "--days", type=int, default=7, help="Number of forecast days (default: 7)"
    )

    # Cities command
    cities_parser = subparsers.add_parser("cities", help="List all available cities")
    cities_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit number of cities shown (0 for all, default: 20)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    client = IMDWeatherClient(use_test_endpoint=args.test)

    # Execute command
    try:
        if args.command == "search":
            search_cities(client, args.city_name, args.exact)
        elif args.command == "weather":
            get_weather(client, args.city, args.format)
        elif args.command == "forecast":
            get_forecast(client, args.city, args.days, args.format)
        elif args.command == "cities":
            limit = None if args.limit == 0 else args.limit
            list_cities(client, limit)

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
