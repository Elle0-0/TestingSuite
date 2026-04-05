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

    Each returned dict contains: station_id, temperature, humidity, timestamp.
    """
    readings: list[dict] = []
    for url in urls:
        reading = fetch_station(url)
        readings.append(reading)
    return readings


def main() -> None:
    """Demonstrate the solution with example URLs and print the results."""
    # Example URLs – in a real deployment these would point to actual weather station endpoints.
    # For demonstration we use httpbin-style or placeholder URLs.
    # Replace these with real endpoints for actual use.
    example_urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]

    # In a real scenario the endpoints would return weather data like:
    # {
    #     "station_id": "WS-001",
    #     "temperature": 22.5,
    #     "humidity": 65.3,
    #     "timestamp": "2024-01-15T10:30:00Z"
    # }

    print(f"Fetching data from {len(example_urls)} station(s)...\n")

    try:
        readings = fetch_all_stations(example_urls)
        print(f"Successfully collected {len(readings)} reading(s):\n")
        for i, reading in enumerate(readings, start=1):
            print(f"Reading {i}:")
            print(json.dumps(reading, indent=2))
            print()
    except Exception as e:
        print(f"Error fetching station data: {e}")
        print("\nFalling back to simulated data for demonstration...\n")

        # Simulated weather station data for demonstration purposes
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

        print(f"Simulated {len(simulated_readings)} reading(s):\n")
        for i, reading in enumerate(simulated_readings, start=1):
            print(f"Reading {i}:")
            print(json.dumps(reading, indent=2))
            print()


if __name__ == "__main__":
    main()