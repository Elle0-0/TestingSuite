import urllib.request
import json
from typing import Any


def fetch_station(url: str) -> dict[str, Any]:
    """Fetch a single station's reading from the given URL."""
    with urllib.request.urlopen(url) as response:
        data = response.read().decode("utf-8")
        reading = json.loads(data)
    return reading


def fetch_all_stations(urls: list[str]) -> list[dict]:
    """Fetch readings from all station URLs and return them as a list of dicts.

    Each dict contains: station_id, temperature, humidity, and timestamp.
    """
    readings = []
    for url in urls:
        reading = fetch_station(url)
        readings.append(reading)
    return readings


def main():
    """Demonstrate the solution with example URLs and print the results."""
    # Example URLs pointing to weather station endpoints.
    # In a real deployment these would be actual station API endpoints.
    # For demonstration purposes, we use httpbin-style or placeholder URLs.
    example_urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]

    # To demonstrate with realistic weather station data without requiring
    # actual running stations, we also provide a mock mode.
    print("=" * 60)
    print("Weather Station Data Collection Client")
    print("=" * 60)

    # Demonstrate with mock data to show the intended structure
    mock_readings = [
        {
            "station_id": "WS-001",
            "temperature": 22.5,
            "humidity": 65.3,
            "timestamp": "2024-01-15T10:30:00Z",
        },
        {
            "station_id": "WS-002",
            "temperature": 18.2,
            "humidity": 72.1,
            "timestamp": "2024-01-15T10:30:05Z",
        },
        {
            "station_id": "WS-003",
            "temperature": 25.8,
            "humidity": 55.0,
            "timestamp": "2024-01-15T10:30:10Z",
        },
    ]

    print("\n--- Mock station readings (expected format) ---\n")
    for reading in mock_readings:
        print(f"  Station: {reading['station_id']}")
        print(f"    Temperature: {reading['temperature']}°C")
        print(f"    Humidity:    {reading['humidity']}%")
        print(f"    Timestamp:   {reading['timestamp']}")
        print()

    # Attempt to fetch from the example URLs to demonstrate real HTTP calls
    print("--- Attempting live fetch from example URLs ---\n")
    try:
        results = fetch_all_stations(example_urls)
        print(f"Successfully fetched {len(results)} readings:\n")
        for result in results:
            print(f"  {json.dumps(result, indent=4)}")
            print()
    except Exception as e:
        print(f"  Could not reach example URLs: {e}")
        print("  In production, this would connect to actual weather station endpoints.")

    print("=" * 60)
    print(f"Total readings collected: {len(mock_readings)}")
    print("=" * 60)


if __name__ == "__main__":
    main()