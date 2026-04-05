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
    # Example URLs — in a real deployment these would point to actual weather station endpoints.
    # For demonstration purposes we use JSONPlaceholder-style URLs or mock endpoints.
    # Replace these with real station endpoints when available.
    example_urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]

    print("Fetching station readings...")
    print(f"Number of stations to query: {len(example_urls)}")
    print()

    try:
        readings = fetch_all_stations(example_urls)

        print(f"Successfully collected {len(readings)} readings:")
        print("-" * 60)

        for i, reading in enumerate(readings, start=1):
            print(f"Reading {i}:")
            for key, value in reading.items():
                print(f"  {key}: {value}")
            print()

        # Return readings for potential further processing
        return readings

    except Exception as e:
        print(f"Error fetching station data: {e}")
        print()
        # Demonstrate with simulated data instead
        simulated_urls = []
        simulated_readings = [
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
                "humidity": 55.7,
                "timestamp": "2024-01-15T10:30:10Z",
            },
        ]

        print("Using simulated station data for demonstration:")
        print("-" * 60)

        for i, reading in enumerate(simulated_readings, start=1):
            print(f"Reading {i}:")
            print(f"  station_id:  {reading['station_id']}")
            print(f"  temperature: {reading['temperature']}°C")
            print(f"  humidity:    {reading['humidity']}%")
            print(f"  timestamp:   {reading['timestamp']}")
            print()

        return simulated_readings


if __name__ == "__main__":
    main()