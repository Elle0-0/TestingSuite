from __future__ import annotations

import json
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
        "https://example.com/stations/101",
        "https://example.com/stations/102",
        "https://example.com/stations/103",
    ]

    try:
        results = fetch_all_stations(example_urls)
        print(json.dumps(results, indent=2))
    except Exception as exc:
        print(f"Demo request failed: {exc}")


if __name__ == "__main__":
    main()