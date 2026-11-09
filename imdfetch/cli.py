#!/usr/bin/env python3
"""
Command-line interface for imdfetch package
"""

import argparse
import json
import sys
from typing import Any, Dict, NoReturn, Optional, Tuple, Union

from . import IMDWeatherClient
from .exceptions import AmbiguousCityError, CityNotFoundError, NetworkError
from .utils import colorize_humidity, colorize_temperature, format_date
from .weather import WeatherData


def _exit_code(error: Exception) -> int:
    """1 is a general failure; 2 is reserved by argparse for bad usage."""
    if isinstance(error, AmbiguousCityError):
        return 4
    if isinstance(error, CityNotFoundError):
        return 3
    if isinstance(error, NetworkError):
        return 5
    return 1


def _fail(
    error: Exception, output_format: str = "text", hint: Optional[str] = None
) -> NoReturn:
    """Report an error in the requested format and exit with its code."""
    if output_format == "json":
        detail: Dict[str, Any] = {"type": type(error).__name__, "message": str(error)}
        if isinstance(error, AmbiguousCityError):
            detail["matches"] = [
                {"city_id": city.city_id, "name": city.display_name}
                for city in error.matches
            ]
        print(json.dumps({"error": detail}, indent=2))
    else:
        print(f"❌ {error}")
        if hint:
            print(hint)
    sys.exit(_exit_code(error))


def _is_missing_observation(param_name: str, value: Union[str, float, None]) -> bool:
    if value is None:
        return True

    text = str(value).strip()
    if text.upper() in {"", "NA", "N/A", "-", "--", "NONE"}:
        return True

    try:
        numeric = float(text)
    except ValueError:
        return False

    param_lower = param_name.lower()
    if "temperature" in param_lower and numeric in {99.9, 999.0}:
        return True
    if "rainfall" in param_lower and numeric == 999.0:
        return True
    if "humidity" in param_lower and numeric == 999.0:
        return True
    return False


def _display_observation(
    param_name: str, value: Union[str, float, None]
) -> Tuple[str, bool]:
    missing = _is_missing_observation(param_name, value)
    return ("NA" if missing else str(value).strip(), missing)


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
        _fail(e)


def _print_weather(weather: WeatherData) -> None:
    print(f"🌤️ Latest Observations for {weather.city}")
    if weather.date:
        print(f"📅 Bulletin Date: {format_date(weather.date)}")
    if weather.updated_at:
        print(f"🕒 Updated by IMD: {weather.updated_at}")

    observations = [
        _display_observation(name, weather.get_parameter(name))
        for name in (
            "Maximum Temperature",
            "Minimum Temperature",
            "24 Hours Rainfall",
            "Relative Humidity at 08:30",
            "Relative Humidity at 17:30",
        )
    ]
    max_temp, min_temp, rainfall, humidity_0830, humidity_1730 = [
        text for text, _ in observations
    ]

    recorded = (
        f" (recorded {format_date(weather.max_date, include_day=False)})"
        if weather.max_date
        else ""
    )
    print(f"🌡️ Max Temperature{recorded}: {colorize_temperature(max_temp)}")
    print(f"🌡️ Min Temperature: {colorize_temperature(min_temp)}")
    print(f"🌧️ 24h Rainfall (mm): {rainfall}")
    print(f"💧 Relative Humidity at 08:30: {colorize_humidity(humidity_0830)}")
    print(f"💧 Relative Humidity at 17:30: {colorize_humidity(humidity_1730)}")
    if any(missing for _, missing in observations):
        print("⚠️ Observation values appear unavailable for this station.")
    if weather.max_date:
        print("ℹ️ These are IMD's latest reported values, not a live reading.")


def get_weather(
    client: IMDWeatherClient,
    city_identifier: Union[int, str, None] = None,
    output_format: str = "text",
) -> None:
    """Get current weather for a city"""
    try:
        if city_identifier is None:
            weather = client.get_current_weather_for_ip()
        else:
            weather = client.get_current_weather(city_identifier)

        if output_format == "json":
            data = (
                [w.to_dict() for w in weather]
                if isinstance(weather, list)
                else weather.to_dict()
            )
            print(json.dumps(data, indent=2))
        elif isinstance(weather, list):
            print(f"🏙️  {len(weather)} stations match '{city_identifier}':\n")
            for station in weather:
                _print_weather(station)
                print()
        else:
            _print_weather(weather)

    except Exception as e:
        hint = (
            'Pass a city or station ID instead, e.g. `imdfetch weather "Delhi"`.'
            if city_identifier is None and isinstance(e, NetworkError)
            else None
        )
        _fail(e, output_format, hint)


def get_forecast(
    client: IMDWeatherClient,
    city_identifier: Union[int, str],
    days: int = 7,
    output_format: str = "text",
) -> None:
    """Get weather forecast for a city"""
    try:
        forecast = client.get_forecast(city_identifier)
        if output_format == "json":
            print(json.dumps(forecast.to_dict(), indent=2))
        else:
            print(f"🔮 {days}-Day Weather Forecast for {forecast.city}")
            print(f"📅 Forecast Date: {format_date(forecast.forecast_date)}")
            print("-" * 50)
            for i, day in enumerate(forecast.days[:days]):
                print(f"📅 {format_date(day.iso_date)}")
                min_colored = colorize_temperature(day.min_temp)
                max_colored = colorize_temperature(day.max_temp)
                print(f"🌡️ Temperature: {min_colored} - {max_colored}")
                print(f"🌤️ Forecast: {day.forecast}")
                if day.warnings:
                    print(f"⚠️ Warnings: {day.warnings}")
                print()

    except Exception as e:
        _fail(e, output_format)


def _temp_cell(value: Optional[float]) -> str:
    return _display_observation("temperature", value)[0]


def show_history(
    client: IMDWeatherClient,
    city_identifier: Union[int, str],
    output_format: str = "text",
) -> None:
    """Show past observations and upcoming predictions for a city"""
    try:
        history = client.get_daily_temperatures(city_identifier)
        if output_format == "json":
            print(json.dumps(history.to_dict(), indent=2))
            return

        print(f"📈 Daily Temperatures for {history.city} (°C)")
        print(
            f"{'Date':<12}{'Max':>7}{'Fcst Max':>10}{'Norm Max':>10}"
            f"{'Min':>7}{'Fcst Min':>10}{'Norm Min':>10}"
        )
        for day in history.days:
            print(
                f"{day.date:<12}{_temp_cell(day.max_temp):>7}"
                f"{_temp_cell(day.forecast_max):>10}{_temp_cell(day.normal_max):>10}"
                f"{_temp_cell(day.min_temp):>7}"
                f"{_temp_cell(day.forecast_min):>10}{_temp_cell(day.normal_min):>10}"
            )

    except Exception as e:
        _fail(e, output_format)


def show_nowcast(
    client: IMDWeatherClient, area: Optional[str] = None, output_format: str = "text"
) -> None:
    """Show IMD nowcast alerts that are valid right now"""
    try:
        report = client.get_nowcasts(area)
        if output_format == "json":
            print(json.dumps(report.to_dict(), indent=2))
            return

        for nowcast in report.alerts:
            print(f"⚡ {nowcast.event} ({nowcast.severity}) - {nowcast.sender}")
            print(f"📍 {nowcast.area}")
            print(f"📝 {nowcast.headline}")
            print(f"🕒 Valid: {nowcast.effective} to {nowcast.expires}")
            print()

        if report.unreadable:
            print(
                f"⚠️ {report.unreadable} alert(s) could not be read, "
                "so this list may be incomplete."
            )
        elif not report.alerts:
            where = f" for '{area}'" if area else ""
            print(f"✅ No active IMD nowcast alerts{where}.")

    except Exception as e:
        _fail(e, output_format)


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
        _fail(e)


def _city_arg(text: str) -> Union[int, str]:
    return int(text) if text.isdigit() else text


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="imdfetch CLI - Get weather data from India Meteorological Department",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  imd-weather search Mumbai
  imd-weather weather
  imd-weather weather "Delhi"
  imd-weather weather 43057
  imd-weather forecast "Bangalore" --days 5
  imd-weather cities --limit 10
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    search_parser = subparsers.add_parser("search", help="Search for cities")
    search_parser.add_argument("city_name", help="City name to search for")
    search_parser.add_argument(
        "--exact", action="store_true", help="Perform exact match search"
    )

    weather_parser = subparsers.add_parser(
        "weather", help="Get IMD's latest observations"
    )
    weather_parser.add_argument(
        "city",
        nargs="?",
        type=_city_arg,
        help="City name or ID. If omitted, use IP geolocation to find the nearest IMD station.",
    )

    forecast_parser = subparsers.add_parser("forecast", help="Get weather forecast")
    forecast_parser.add_argument("city", type=_city_arg, help="City name or ID")
    forecast_parser.add_argument(
        "--days", type=int, default=7, help="Number of forecast days (default: 7)"
    )

    history_parser = subparsers.add_parser(
        "history", help="Show past observations and upcoming predictions"
    )
    history_parser.add_argument("city", type=_city_arg, help="City name or ID")

    nowcast_parser = subparsers.add_parser(
        "nowcast", help="Show IMD nowcast alerts valid right now"
    )
    nowcast_parser.add_argument(
        "area", nargs="?", help="District or state name. If omitted, all of India."
    )
    for command_parser in (
        weather_parser,
        forecast_parser,
        history_parser,
        nowcast_parser,
    ):
        command_parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )

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

    client = IMDWeatherClient(use_test_endpoint=True)

    try:
        if args.command == "search":
            search_cities(client, args.city_name, args.exact)
        elif args.command == "weather":
            get_weather(client, args.city, args.format)
        elif args.command == "forecast":
            get_forecast(client, args.city, args.days, args.format)
        elif args.command == "history":
            show_history(client, args.city, args.format)
        elif args.command == "nowcast":
            show_nowcast(client, args.area, args.format)
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
