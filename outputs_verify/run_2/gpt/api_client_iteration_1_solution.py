from typing import List, Dict, Any
import json
from urllib.request import urlopen, Request


def fetch_station(url: str) -> Dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        data = response.read().decode(charset)
        return json.loads(data)


def fetch_all_stations(urls: List[str]) -> List[Dict[str, Any]]:
    return [fetch_station(url) for url in urls]


def main() -> None:
    example_urls = [
        "https://example.com/stations/alpha",
        "https://example.com/stations/bravo",
        "https://example.com/stations/charlie",
    ]

    try:
        readings = fetch_all_stations(example_urls)
        print(json.dumps(readings, indent=2))
    except Exception as e:
        print(f"Failed to fetch station data: {e}")


if __name__ == "__main__":
    main()