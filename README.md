# imdfetch

A Python package for fetching and parsing weather data from India Meteorological Department (IMD).


## Installation

```bash
pip install git+https://github.com/saketlab/imdfetch.git
```

Or install from source:

```bash
git clone https://github.com/saketkc/imdfetch.git
cd imdfetch
pip install -e .
```

## Quick Start

[See notebook](notebooks/demo.ipynb)

### Command Line Interface

```bash
# Search for cities
imdfetch search Mumbai

# Get current weather
imdfetch weather  # Uses IP geolocation to choose the nearest IMD station
imdfetch weather "Mumbai (Santacruz)"
imdfetch weather "colaba" # regex for Mumbai (Colaba)
imdfetch weather 13001  # Using city ID
```

Output:

```text
$ imdfetch weather "chembur"
🌤️  Current Weather for Mumbai-Chembur
📅 Date: 24 June, 2026 (Wednesday)
🌡️ Max Temperature: NA
🌡️ Min Temperature: NA
🌧️ 24h Rainfall (mm): NA
💧 Relative Humidity at 08:30: NA
💧 Relative Humidity at 17:30: NA
⚠️ Observation values appear unavailable for this station.
```

IMD sometimes returns sentinel values such as `99.9`, `999`, or `999.00`
when station observations are unavailable. The CLI displays those as `NA` and
prints the warning above. The Python API preserves the raw values returned by
IMD.

```text
$ imdfetch weather
# Uses your public IP location, chooses the nearest IMD station with coordinates,
# then prints the same current-weather format as above.
```

If IP geolocation is blocked by a network, VPN, or provider rate limit, pass a
station explicitly:

```bash
imdfetch weather "Mumbai (Santacruz)"
imdfetch weather 43057
```

```bash
# Get weather forecast
imdfetch forecast "Mumbai-Powai"
```

```bash
# List available cities
imdfetch cities --limit 10
imdfetch cities --limit 0  # Show all cities
```


## Python API

```python
from imdfetch import IMDWeatherClient

# Initialize the client
client = IMDWeatherClient()

# Get current weather for a city
weather = client.get_current_weather("Mumbai")
print(f"Temperature in {weather.city}: {weather.get_parameter('Maximum Temperature')}")

# Get 7-day forecast
forecast = client.get_forecast("Delhi")
print(f"Tomorrow's forecast: {forecast.days[1].forecast}")

# Search for cities
cities = client.find_city("Bangalore")
for city in cities:
    print(f"ID: {city.city_id}, Name: {city.display_name}")
```


## Detailed Usage

### Working with Cities

```python
# Get all available cities
all_cities = client.get_cities()
print(f"Total cities available: {len(all_cities)}")

# Search for cities (partial matching)
mumbai_cities = client.find_city("mumbai")
for city in mumbai_cities:
    print(f"{city.display_name} (ID: {city.city_id})")

# Get city by ID
city = client.get_city_by_id(43279)
if city:
    print(f"Found: {city.display_name}")

# Get cities as DataFrame
df = client.get_cities_dataframe()
print(df.head())
```

### Current Weather Data

```python
# Using your public IP location to choose the nearest IMD station
weather = client.get_current_weather_for_ip()

# Using city name
weather = client.get_current_weather("Chennai")

# Using city ID
weather = client.get_current_weather(43279)

# Access weather parameters
print(f"City: {weather.city}")
print(f"Date: {weather.date}")
print(f"Max Temperature: {weather.get_parameter('Maximum Temperature')}")
print(f"Rainfall: {weather.get_parameter('24 Hours Rainfall')}")
print(f"Humidity (Morning): {weather.get_parameter('Relative Humidity at 08:30')}")

# Convert to dictionary
weather_dict = weather.to_dict()
print(weather_dict)

# Access all parameters
for param in weather.parameters:
    print(f"{param.parameter}: {param.value}")
```

### Weather Forecast

```python
# Get 7-day forecast
forecast = client.get_forecast("Hyderabad")

print(f"Forecast for {forecast.city}")
for day in forecast.days:
    print(f"{day.date}: {day.min_temp}°C - {day.max_temp}°C, {day.forecast}")

# Get specific day forecast
tomorrow = forecast.get_day_forecast("28-May")  # or use ISO date
if tomorrow:
    print(f"Tomorrow: {tomorrow.forecast}")

# Convert to dictionary
forecast_dict = forecast.to_dict()
```

### Complete Weather Data

```python
# Get both current weather and forecast in one call
weather, forecast = client.get_complete_weather_data("Kolkata")

print(f"Current temperature: {weather.get_parameter('Maximum Temperature')}")
print(f"Tomorrow's forecast: {forecast.days[1].forecast}")
```


## API Reference

### IMDWeatherClient

#### Methods
- `get_cities(refresh_cache=False)`: Get all available cities
- `find_city(city_name, exact_match=False)`: Search for cities by name
- `get_city_by_id(city_id)`: Get city info by ID
- `get_current_weather(city_identifier)`: Get current weather data
- `get_current_weather_for_ip()`: Get current weather for the nearest IMD station to your public IP location
- `get_forecast(city_identifier)`: Get weather forecast
- `get_complete_weather_data(city_identifier)`: Get both current and forecast data
- `get_cities_dataframe()`: Get cities as pandas DataFrame

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This package is not officially affiliated with the India Meteorological Department. It's a third-party tool for accessing publicly available weather data.

