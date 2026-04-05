import asyncio
import random
import time
from typing import Any


async def mock_station_request(url: str) -> dict[str, Any]:
    await asyncio.sleep(random.uniform(0.05, 0.6))
    roll = random.random()
    if "restricted" in url:
        raise PermissionError("403 Forbidden")
    if "missing" in url:
        raise FileNotFoundError("404 Not Found")
    if roll < 0.12:
        raise TimeoutError("Request timed out")
    if roll < 0.2:
        raise ConnectionError("Temporary network failure")
    station_id = url.rsplit("/", 1)[-1]
    return {
        "station": station_id,
        "url": url,
        "temperature_c": round(random.uniform(-10, 38), 1),
        "humidity_pct": random.randint(20, 95),
        "status": "ok",
    }


def is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (TimeoutError, ConnectionError))


async def fetch_station_with_retries(
    url: str,
    retries: int = 3,
    base_backoff: float = 0.15,
) -> tuple[str, dict[str, Any] | None, dict[str, str] | None]:
    attempt = 0
    while True:
        attempt += 1
        try:
            data = await mock_station_request(url)
            return url, data, None
        except Exception as exc:
            if is_retryable(exc) and attempt <= retries:
                await asyncio.sleep(base_backoff * (2 ** (attempt - 1)))
                continue
            return url, None, {
                "type": exc.__class__.__name__,
                "message": str(exc),
                "attempts": str(attempt),
            }


async def _fetch_all_stations_async(urls: list[str], max_concurrent: int = 10) -> dict:
    semaphore = asyncio.Semaphore(max_concurrent)
    readings: dict[str, Any] = {}
    errors: dict[str, Any] = {}

    async def worker(url: str) -> None:
        async with semaphore:
            station_url, data, error = await fetch_station_with_retries(url)
            if data is not None:
                readings[station_url] = data
            else:
                errors[station_url] = error

    await asyncio.gather(*(worker(url) for url in urls))
    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    return asyncio.run(_fetch_all_stations_async(urls, max_concurrent=max_concurrent))


def build_example_urls(count: int = 60) -> list[str]:
    urls = []
    for i in range(1, count + 1):
        if i % 17 == 0:
            urls.append(f"https://api.example.com/stations/restricted-{i}")
        elif i % 13 == 0:
            urls.append(f"https://api.example.com/stations/missing-{i}")
        else:
            urls.append(f"https://api.example.com/stations/station-{i}")
    return urls


def main() -> None:
    urls = build_example_urls(80)
    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=12)
    elapsed = time.perf_counter() - start

    print("Readings:")
    for url, reading in sorted(result["readings"].items()):
        print(url, reading)

    print("\nErrors:")
    for url, error in sorted(result["errors"].items()):
        print(url, error)

    print(f"\nTotal stations: {len(urls)}")
    print(f"Successful: {len(result['readings'])}")
    print(f"Failed: {len(result['errors'])}")
    print(f"Elapsed time: {elapsed:.3f}s")


if __name__ == "__main__":
    main()