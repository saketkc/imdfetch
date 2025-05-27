#!/usr/bin/env python3
"""
Basic usage examples for imdfetch package
"""

from imdfetch import IMDWeatherClient
from imdfetch.exceptions import CityNotFoundError, NetworkError


def main():
    # Initialize the client
    print("🌤️  imdfetch Package - Basic Usage Examples")
    print("=" * 50)

    client = IMDWeatherClient()

    # Example 1: Search for cities
    print("\n1. Searching for cities...")
    cities = client.find_city("Mumbai")
    for city in cities:
        print(f"   📍 {city.display_name} (ID: {city.city_id})")

    # Example 2: Get current weather
    print("\n2. Getting current weather for Mumbai...")
    try:
        weather = client.get_current_weather("Mumbai (Santacruz)")
        print(f"   🏙️  City: {weather.city}")
        print(f"   📅 Date: {weather.date}")
        print(f"   🌡️  Max Temperature: {weather.get_parameter('Maximum Temperature')}")
        print(f"   🌧️  24h Rainfall: {weather.get_parameter('24 Hours Rainfall')}")
        print(
            f"   💧 Humidity (AM): {weather.get_parameter('Relative Humidity at 08:30')}"
        )

    except CityNotFoundError as e:
        print(f"   ❌ City not found: {e}")
    except NetworkError as e:
        print(f"   🌐 Network error: {e}")

    # Example 3: Get weather forecast
    print("\n3. Getting 7-day forecast for New Delhi (Safdarjung)...")
    try:
        forecast = client.get_forecast("New Delhi (Safdarjung)")
        print(f"   🏙️  Forecast for: {forecast.city}")
        for day in forecast.days[:3]:  # Show first 3 days
            print(f"   📅 {day.date}: {day.min_temp}°C - {day.max_temp}°C")
            print(f"      🌤️  {day.forecast}")

        if len(forecast.days) > 3:
            print(f"   ... and {len(forecast.days) - 3} more days")

    except Exception as e:
        print(f"   ❌ Error getting forecast: {e}")

    # Example 4: Get complete weather data
    print("\n4. Getting complete weather data for Bengaluru...")
    try:
        # Search for Bengaluru first
        bangalore_cities = client.find_city("Bengaluru")
        if bangalore_cities:
            weather, forecast = client.get_complete_weather_data(
                bangalore_cities[0].city_id
            )

            print(f"   🏙️  Current weather in {weather.city}:")
            print(
                f"   🌡️  Temperature: {weather.get_parameter('Minimum Temperature')} - {weather.get_parameter('Maximum Temperature')}"
            )

            print(f"   📅 Tomorrow's forecast:")
            if len(forecast.days) > 1:
                tomorrow = forecast.days[1]
                print(f"   🌤️  {tomorrow.forecast}")
                print(f"   🌡️  {tomorrow.min_temp}°C - {tomorrow.max_temp}°C")
        else:
            print("   ❌ Bengaluru not found")

    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Example 5: Export data to DataFrame
    print("\n5. Working with DataFrames...")
    try:
        # Get cities as DataFrame
        cities_df = client.get_cities_dataframe()
        print(f"   📊 Total cities available: {len(cities_df)}")
        print(f"   🔍 Sample cities:")
        print(cities_df.head(3)[["city_id", "display_name"]].to_string(index=False))

        # Get weather data and convert to dict
        weather = client.get_current_weather(cities_df.iloc[0]["city_id"])
        weather_dict = weather.to_dict()
        print(f"\n   📋 Weather data keys: {list(weather_dict.keys())}")

    except Exception as e:
        print(f"   ❌ Error working with DataFrames: {e}")

    print("\n✅ Examples completed!")


if __name__ == "__main__":
    main()
