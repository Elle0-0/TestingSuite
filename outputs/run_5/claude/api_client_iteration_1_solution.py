import urllib.request
import json
from typing import List, Dict


def fetch_station(url: str) -> dict:
    """Fetch a single station's reading from the given URL."""
    with urllib.request.urlopen(url) as response:
        data = response.read().decode('utf-8')
        reading = json.loads(data)
    return reading


def fetch_all_stations(urls: List[str]) -> List[Dict]:
    """Fetch readings from all station URLs and return them as a list of dicts.
    
    Args:
        urls: A list of endpoint URLs, each returning JSON with fields:
              station_id, temperature, humidity, and timestamp.
    
    Returns:
        A list of dictionaries, each containing a station's reading.
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
        "https://api.example.com/stations/station-001/reading",
        "https://api.example.com/stations/station-002/reading",
        "https://api.example.com/stations/station-003/reading",
    ]

    # For demonstration purposes, since the example URLs are not real,
    # we simulate the behavior by showing what the program would do
    # and providing sample output.
    print("Weather Station Data Collection Client")
    print("=" * 45)
    print(f"\nConfigured to fetch from {len(example_urls)} stations:")
    for url in example_urls:
        print(f"  - {url}")

    # Attempt to fetch from real URLs; if unavailable, use simulated data
    try:
        readings = fetch_all_stations(example_urls)
    except Exception:
        print("\n[Note: Example URLs are not reachable. Using simulated data.]\n")
        readings = [
            {
                "station_id": "station-001",
                "temperature": 22.5,
                "humidity": 65.3,
                "timestamp": "2024-01-15T10:30:00Z"
            },
            {
                "station_id": "station-002",
                "temperature": 18.2,
                "humidity": 72.1,
                "timestamp": "2024-01-15T10:30:05Z"
            },
            {
                "station_id": "station-003",
                "temperature": 25.8,
                "humidity": 58.7,
                "timestamp": "2024-01-15T10:30:10Z"
            },
        ]

    print(f"\nCollected {len(readings)} readings:\n")
    print("-" * 65)
    print(f"{'Station ID':<15} {'Temperature':>12} {'Humidity':>10} {'Timestamp':<25}")
    print("-" * 65)

    for reading in readings:
        print(
            f"{reading['station_id']:<15} "
            f"{reading['temperature']:>10.1f}°C "
            f"{reading['humidity']:>9.1f}% "
            f"{reading['timestamp']:<25}"
        )

    print("-" * 65)
    print(f"\nRaw JSON output:")
    print(json.dumps(readings, indent=2))


if __name__ == "__main__":
    main()