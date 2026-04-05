import asyncio
import random
import time
from typing import Any


class HTTPError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        super().__init__(message or f"HTTP {status_code}")
        self.status_code = status_code


class TransientError(Exception):
    pass


async def mock_fetch_station(url: str) -> dict[str, Any]:
    await asyncio.sleep(random.uniform(0.05, 0.6))

    roll = random.random()

    if "forbidden" in url:
        raise HTTPError(403, "Forbidden")
    if "missing" in url:
        raise HTTPError(404, "Not Found")
    if "slowfail" in url and roll < 0.5:
        await asyncio.sleep(0.7)
        raise TransientError("Delayed upstream timeout")
    if "flaky" in url and roll < 0.45:
        raise TransientError("Temporary network issue")
    if "busy" in url and roll < 0.35:
        raise HTTPError(429, "Too Many Requests")
    if "server" in url and roll < 0.4:
        raise HTTPError(503, "Service Unavailable")
    if roll < 0.08:
        raise TransientError("Random connection reset")

    station_id = url.rsplit("/", 1)[-1]
    return {
        "station": station_id,
        "temperature_c": round(random.uniform(-10, 38), 1),
        "humidity_pct": random.randint(15, 95),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_url": url,
    }


def is_retryable(exc: Exception) -> bool:
    if isinstance(exc, TransientError):
        return True
    if isinstance(exc, HTTPError):
        return exc.status_code in {408, 425, 429, 500, 502, 503, 504}
    return False


def is_restricted(exc: Exception) -> bool:
    return isinstance(exc, HTTPError) and exc.status_code in {401, 403}


async def fetch_station_with_retries(
    url: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    base_backoff: float = 0.2,
    request_timeout: float = 1.5,
) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    attempts = 0
    last_error: Exception | None = None

    while attempts <= max_retries:
        attempts += 1
        try:
            async with semaphore:
                result = await asyncio.wait_for(mock_fetch_station(url), timeout=request_timeout)
            return url, result, None
        except Exception as exc:
            last_error = exc

            if is_restricted(exc):
                return url, None, {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "attempts": attempts,
                    "retryable": False,
                }

            if attempts > max_retries or not is_retryable(exc):
                return url, None, {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "attempts": attempts,
                    "retryable": is_retryable(exc),
                }

            await asyncio.sleep(base_backoff * (2 ** (attempts - 1)) + random.uniform(0, 0.1))

    return url, None, {
        "type": type(last_error).__name__ if last_error else "UnknownError",
        "message": str(last_error) if last_error else "Unknown failure",
        "attempts": attempts,
        "retryable": False,
    }


async def _fetch_all_stations_async(urls: list[str], max_concurrent: int = 10) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(max(1, max_concurrent))
    tasks = [fetch_station_with_retries(url, semaphore) for url in urls]
    results = await asyncio.gather(*tasks)

    readings: dict[str, Any] = {}
    errors: dict[str, Any] = {}

    for url, reading, error in results:
        if reading is not None:
            readings[url] = reading
        elif error is not None:
            errors[url] = error

    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    return asyncio.run(_fetch_all_stations_async(urls, max_concurrent=max_concurrent))


def main() -> None:
    random.seed(7)

    urls: list[str] = []
    for i in range(1, 61):
        suffix = f"station-{i}"
        if i % 17 == 0:
            suffix = f"forbidden-{i}"
        elif i % 13 == 0:
            suffix = f"missing-{i}"
        elif i % 11 == 0:
            suffix = f"slowfail-{i}"
        elif i % 7 == 0:
            suffix = f"flaky-{i}"
        elif i % 5 == 0:
            suffix = f"busy-{i}"
        elif i % 3 == 0:
            suffix = f"server-{i}"
        urls.append(f"https://api.example.com/stations/{suffix}")

    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print("Readings:")
    for url, reading in result["readings"].items():
        print(url, "->", reading)

    print("\nErrors:")
    for url, error in result["errors"].items():
        print(url, "->", error)

    print(f"\nSummary: {len(result['readings'])} succeeded, {len(result['errors'])} failed")
    print(f"Elapsed time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()