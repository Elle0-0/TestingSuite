import json
from urllib.request import urlopen
from urllib.parse import urlparse, parse_qs, unquote
from urllib.error import URLError


def _read_json_from_url(url: str) -> dict:
    with urlopen(url) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def fetch_all_stations(urls: list[str]) -> list[dict]:
    readings = []
    for url in urls:
        readings.append(_read_json_from_url(url))
    return readings


def _example_url(station_id: str, temperature: float, humidity: int, timestamp: str) -> str:
    payload = json.dumps(
        {
            "station_id": station_id,
            "temperature": temperature,
            "humidity": humidity,
            "timestamp": timestamp,
        }
    )
    return "data:application/json," + payload


def _fallback_read_json_from_data_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme != "data":
        raise URLError("Unsupported URL scheme for demo fallback")
    data_part = url.split(",", 1)[1]
    return json.loads(unquote(data_part))


def main() -> None:
    urls = [
        _example_url("ST-001", 21.5, 55, "2026-03-23T10:00:00Z"),
        _example_url("ST-002", 18.9, 63, "2026-03-23T10:01:00Z"),
        _example_url("ST-003", 24.2, 47, "2026-03-23T10:02:00Z"),
    ]

    try:
        results = fetch_all_stations(urls)
    except Exception:
        results = [_fallback_read_json_from_data_url(url) for url in urls]

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()