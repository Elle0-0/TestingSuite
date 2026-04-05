import json
from typing import List, Dict
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


def fetch_all_stations(urls: List[str]) -> List[Dict]:
    readings = []
    for url in urls:
        with urlopen(url) as response:
            data = json.load(response)
            readings.append(data)
    return readings


def main() -> None:
    example_station_payloads = [
        {
            "station_id": "station-001",
            "temperature": 21.5,
            "humidity": 58,
            "timestamp": "2026-03-18T09:00:00Z",
        },
        {
            "station_id": "station-002",
            "temperature": 19.8,
            "humidity": 64,
            "timestamp": "2026-03-18T09:01:00Z",
        },
        {
            "station_id": "station-003",
            "temperature": 23.1,
            "humidity": 52,
            "timestamp": "2026-03-18T09:02:00Z",
        },
    ]

    print("Demonstration results:")
    print(example_station_payloads)

    example_urls = [
        "https://example.com/station/1",
        "https://example.com/station/2",
        "https://example.com/station/3",
    ]

    try:
        results = fetch_all_stations(example_urls)
        print("Fetched from URLs:")
        print(results)
    except (HTTPError, URLError):
        pass


if __name__ == "__main__":
    main()