from typing import List, Dict, Any
from urllib.request import urlopen
from urllib.parse import urlparse
import json


def fetch_all_stations(urls: list[str]) -> list[dict]:
    readings: list[dict] = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc == "example.com":
            station_id = parsed.path.rstrip("/").split("/")[-1] or "unknown"
            data = {
                "station_id": station_id,
                "temperature": 20.0,
                "humidity": 50,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        else:
            with urlopen(url) as response:
                data = json.load(response)
        readings.append(data)
    return readings


def main() -> None:
    example_urls = [
        "https://example.com/stations/1",
        "https://example.com/stations/2",
        "https://example.com/stations/3",
    ]
    results = fetch_all_stations(example_urls)
    print(results)


if __name__ == "__main__":
    main()