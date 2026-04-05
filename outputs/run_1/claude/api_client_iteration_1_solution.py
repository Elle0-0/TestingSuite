import urllib.request
import json
from typing import List, Dict


def fetch_station(url: str) -> dict:
    """Fetch a single station's reading from the given URL."""
    with urllib.request.urlopen(url) as response:
        data = response.read().decode('utf-8')
        return json.loads(data)


def fetch_all_stations(urls: List[str]) -> List[Dict]:
    """
    Fetch readings from all given station URLs and return them as a list of dicts.
    
    Each dict contains: station_id, temperature, humidity, and timestamp.
    
    Args:
        urls: A list of endpoint URLs for weather stations.
        
    Returns:
        A list of dictionaries, each representing a station's reading.
    """
    readings = []
    for url in urls:
        reading = fetch_station(url)
        readings.append(reading)
    return readings


def main():
    """Demonstrate the solution with example URLs and print the results."""
    # Example URLs - these would be real weather station endpoints in production.
    # For demonstration purposes, we use httpbin.org or similar test endpoints.
    # In a real scenario, these would return station data JSON.
    example_urls = [
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]

    # Since the above URLs don't return weather data, we'll demonstrate
    # the structure with simulated data as a fallback.
    try:
        readings = fetch_all_stations(example_urls)
        print(f"Successfully fetched {len(readings)} station readings:")
        for reading in readings:
            print(json.dumps(reading, indent=2))
    except Exception as e:
        print(f"Could not reach live endpoints ({e}). Using simulated data.")
        
        # Simulated weather station data for demonstration
        simulated_readings = [
            {
                "station_id": "WS-001",
                "temperature": 22.5,
                "humidity": 65.3,
                "timestamp": "2024-01-15T10:30:00Z"
            },
            {
                "station_id": "WS-002",
                "temperature": 18.2,
                "humidity": 72.1,
                "timestamp": "2024-01-15T10:30:05Z"
            },
            {
                "station_id": "WS-003",
                "temperature": 25.8,
                "humidity": 55.9,
                "timestamp": "2024-01-15T10:30:10Z"
            },
        ]
        
        print(f"Simulated {len(simulated_readings)} station readings:")
        for reading in simulated_readings:
            print(json.dumps(reading, indent=2))
        
        return simulated_readings


if __name__ == "__main__":
    main()