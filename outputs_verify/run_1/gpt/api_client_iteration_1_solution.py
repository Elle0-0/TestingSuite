from __future__ import annotations

import json
from typing import List, Dict
from urllib.request import urlopen


def fetch_all_stations(urls: list[str]) -> list[dict]:
    readings: list[dict] = []
    for url in urls:
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

    try:
        results = fetch_all_stations(example_urls)
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Demo request failed: {e}")


if __name__ == "__main__":
    main()