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
    # For demonstration purposes we use JSONPlaceholder-style or mock URLs.
    example_urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]

    # For a self-contained demo without requiring real weather station endpoints,
    # we simulate the behavior by showing what the function does structurally.
    print("Weather Station Data Collection Client")
    print("=" * 50)
    print()
    print(f"Configured to fetch from {len(example_urls)} station(s):")
    for url in example_urls:
        print(f"  - {url}")
    print()

    try:
        readings = fetch_all_stations(example_urls)
        print(f"Successfully collected {len(readings)} reading(s):")
        print()
        for i, reading in enumerate(readings, start=1):
            print(f"Reading {i}:")
            print(json.dumps(reading, indent=2))
            print()
    except Exception as e:
        print(f"Error fetching station data: {e}")
        print()
        # Demonstrate with simulated data instead
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
                "humidity": 55.0,
                "timestamp": "2024-01-15T10:30:10Z",
            },
        ]
        print("Demonstrating with simulated station data:")
        print()
        for i, reading in enumerate(simulated_readings, start=1):
            print(f"Reading {i}:")
            print(json.dumps(reading, indent=2))
            print()
        print(f"Total readings collected: {len(simulated_readings)}")


if __name__ == "__main__":
    main()