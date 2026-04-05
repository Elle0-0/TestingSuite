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
    example_urls = [
        "https://api.example.com/stations/1/reading",
        "https://api.example.com/stations/2/reading",
        "https://api.example.com/stations/3/reading",
    ]

    print("Weather Station Data Collection Client")
    print("=" * 45)
    print(f"Fetching data from {len(example_urls)} station(s)...\n")

    try:
        readings = fetch_all_stations(example_urls)

        print(f"Successfully collected {len(readings)} reading(s):\n")
        for reading in readings:
            print(f"  Station ID  : {reading.get('station_id', 'N/A')}")
            print(f"  Temperature : {reading.get('temperature', 'N/A')}°C")
            print(f"  Humidity    : {reading.get('humidity', 'N/A')}%")
            print(f"  Timestamp   : {reading.get('timestamp', 'N/A')}")
            print("-" * 40)

        print(f"\nAll readings as JSON:")
        print(json.dumps(readings, indent=2))

    except Exception as e:
        # For this initial version we demonstrate with mock data
        # since example.com URLs won't return real station data.
        print(f"Could not reach live endpoints ({e}).")
        print("Demonstrating with mock data instead:\n")

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
                "humidity": 58.7,
                "timestamp": "2024-01-15T10:30:02Z",
            },
        ]

        print(f"Collected {len(mock_readings)} reading(s):\n")
        for reading in mock_readings:
            print(f"  Station ID  : {reading['station_id']}")
            print(f"  Temperature : {reading['temperature']}°C")
            print(f"  Humidity    : {reading['humidity']}%")
            print(f"  Timestamp   : {reading['timestamp']}")
            print("-" * 40)

        print(f"\nAll readings as JSON:")
        print(json.dumps(mock_readings, indent=2))


if __name__ == "__main__":
    main()