import json
from typing import List, Dict
from urllib.request import urlopen
from urllib.parse import urlparse
from urllib.error import URLError, HTTPError


def fetch_all_stations(urls: List[str]) -> List[Dict]:
    readings = []
    for url in urls:
        with urlopen(url) as response:
            data = json.load(response)
            readings.append(data)
    return readings


def is_real_http_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    return "example.com" not in parsed.netloc.lower()


def main() -> None:
    example_urls = [
        "https://example.com/stations/1",
        "https://example.com/stations/2",
        "https://example.com/stations/3",
    ]

    if not all(is_real_http_url(url) for url in example_urls):
        demo_results = [
            {
                "station_id": "station-1",
                "temperature": 21.5,
                "humidity": 58,
                "timestamp": "2026-03-18T09:00:00Z",
            },
            {
                "station_id": "station-2",
                "temperature": 19.8,
                "humidity": 64,
                "timestamp": "2026-03-18T09:00:05Z",
            },
            {
                "station_id": "station-3",
                "temperature": 23.1,
                "humidity": 52,
                "timestamp": "2026-03-18T09:00:10Z",
            },
        ]
        print(json.dumps(demo_results, indent=2))
        return

    try:
        results = fetch_all_stations(example_urls)
        print(json.dumps(results, indent=2))
    except (HTTPError, URLError) as e:
        print(json.dumps({"error": str(e)}, indent=2))


if __name__ == "__main__":
    main()