#!/usr/bin/env python3
"""
Batch processing examples for multiple cities
"""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import time

from imdfetch import IMDWeatherClient
from imdfetch.exceptions import IMDWeatherError


def get_weather_for_city(client: IMDWeatherClient, city_name: str) -> Dict[str, Any]:
    """
    Get weather data for a single city

    Args:
        client: IMD Weather client instance
        city_name: Name of the city

    Returns:
        Dictionary with weather data or error info
    """
    try:
        weather = client.get_current_weather(city_name)
        return {
            "city": weather.city,
            "date": weather.date,
            "status": "success",
            "max_temp": weather.get_parameter("Maximum Temperature"),
            "min_temp": weather.get_parameter("Minimum Temperature"),
            "rainfall": weather.get_parameter("24 Hours Rainfall"),
            "humidity_morning": weather.get_parameter("Relative Humidity at 08:30"),
            "humidity_evening": weather.get_parameter("Relative Humidity at 17:30"),
        }
    except IMDWeatherError as e:
        return {"city": city_name, "status": "error", "error": str(e)}


def batch_weather_sequential(cities: List[str]) -> pd.DataFrame:
    """
    Get weather data for multiple cities sequentially

    Args:
        cities: List of city names

    Returns:
        DataFrame with weather data
    """
    client = IMDWeatherClient()
    results = []

    print(f"📊 Processing {len(cities)} cities sequentially...")
    start_time = time.time()

    for i, city in enumerate(cities, 1):
        print(f"   Processing {i}/{len(cities)}: {city}")
        result = get_weather_for_city(client, city)
        results.append(result)
        time.sleep(0.5)  # Be nice to the server

    end_time = time.time()
    print(f"✅ Sequential processing completed in {end_time - start_time:.2f} seconds")

    return pd.DataFrame(results)


def batch_weather_parallel(cities: List[str], max_workers: int = 3) -> pd.DataFrame:
    """
    Get weather data for multiple cities in parallel

    Args:
        cities: List of city names
        max_workers: Maximum number of parallel workers

    Returns:
        DataFrame with weather data
    """
    results = []

    print(
        f"🚀 Processing {len(cities)} cities in parallel (max {max_workers} workers)..."
    )
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create a client for each worker
        future_to_city = {}
        for city in cities:
            client = IMDWeatherClient()  # Each thread gets its own client
            future = executor.submit(get_weather_for_city, client, city)
            future_to_city[future] = city

        # Collect results as they complete
        for future in as_completed(future_to_city):
            city = future_to_city[future]
            try:
                result = future.result()
                results.append(result)
                status = "✅" if result["status"] == "success" else "❌"
                print(f"   {status} {city}")
            except Exception as e:
                print(f"   ❌ {city}: {str(e)}")
                results.append({"city": city, "status": "error", "error": str(e)})

    end_time = time.time()
    print(f"✅ Parallel processing completed in {end_time - start_time:.2f} seconds")

    return pd.DataFrame(results)


def analyze_weather_data(df: pd.DataFrame) -> None:
    """
    Analyze the collected weather data

    Args:
        df: DataFrame with weather data
    """
    print("\n📊 Weather Data Analysis")
    print("=" * 40)

    # Success rate
    successful = df[df["status"] == "success"]
    success_rate = len(successful) / len(df) * 100
    print(f"📈 Success Rate: {success_rate:.1f}% ({len(successful)}/{len(df)})")

    if len(successful) > 0:
        # Temperature analysis
        successful["max_temp_numeric"] = pd.to_numeric(
            successful["max_temp"], errors="coerce"
        )
        successful["min_temp_numeric"] = pd.to_numeric(
            successful["min_temp"], errors="coerce"
        )

        if not successful["max_temp_numeric"].isna().all():
            print(
                f"🌡️  Average Max Temperature: {successful['max_temp_numeric'].mean():.1f}°C"
            )
            print(
                f"🔥 Highest Temperature: {successful['max_temp_numeric'].max():.1f}°C"
            )
            print(
                f"❄️  Lowest Max Temperature: {successful['max_temp_numeric'].min():.1f}°C"
            )

        # Rainfall analysis
        successful["rainfall_numeric"] = pd.to_numeric(
            successful["rainfall"], errors="coerce"
        )
        rainy_cities = successful[successful["rainfall_numeric"] > 0]
        if len(rainy_cities) > 0:
            print(f"🌧️  Cities with rainfall: {len(rainy_cities)}")
            print(
                f"💧 Average rainfall (rainy cities): {rainy_cities['rainfall_numeric'].mean():.1f}mm"
            )

    # Error analysis
    errors = df[df["status"] == "error"]
    if len(errors) > 0:
        print(f"\n❌ Failed Cities: {len(errors)}")
        for _, row in errors.iterrows():
            print(f"   • {row['city']}: {row['error']}")


def main():
    print("🌤️  IMD Weather Package - Batch Processing Examples")
    print("=" * 55)

    # List of major Indian cities to process
    cities = [
        "Mumbai (Santacruz)",
        "DELHI-DELHI UNIVERSITY",
        "BENGALURU",
        "Hyderabad",
        "CHENNAI (ENNORE)",
        "KOLKATA-Salt Lake",
        "PUNE-PASHAN",
        "Ahmedabad",
        "JAIPUR-AMER",
        "LUCKNOW-MALIHABAD",
    ]

    # Example 1: Sequential processing
    print("\n1. Sequential Processing")
    print("-" * 25)
    df_sequential = batch_weather_sequential(cities)  # Process first 5 cities

    # Example 2: Parallel processing
    print("\n2. Parallel Processing")
    print("-" * 23)
    df_parallel = batch_weather_parallel(cities, max_workers=3)

    # Example 3: Data analysis
    analyze_weather_data(df_parallel)

    # Example 4: Export to CSV
    print("\n📁 Exporting data to CSV...")
    df_parallel.to_csv("weather_data.csv", index=False)
    print("   ✅ Data exported to weather_data.csv")

    # Example 5: Create summary report
    print("\n📋 Summary Report")
    print("-" * 16)
    successful_data = df_parallel[df_parallel["status"] == "success"]
    if len(successful_data) > 0:
        print(
            successful_data[["city", "max_temp", "min_temp", "rainfall"]].to_string(
                index=False
            )
        )

    print("\n✅ Batch processing examples completed!")


if __name__ == "__main__":
    main()
