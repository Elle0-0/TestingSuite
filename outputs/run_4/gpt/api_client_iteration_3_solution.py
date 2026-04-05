import asyncio
import random
import time
from typing import Any


class APIClientError(Exception):
    pass


class RateLimitError(APIClientError):
    pass


class TemporaryServerError(APIClientError):
    pass


class PermanentClientError(APIClientError):
    pass


async def simulated_station_request(url: str) -> dict[str, Any]:
    await asyncio.sleep(random.uniform(0.05, 0.6))

    roll = random.random()
    if "bad" in url:
        raise PermanentClientError("invalid station endpoint")
    if "slowfail" in url:
        await asyncio.sleep(1.0)
        raise TemporaryServerError("delayed server failure")
    if roll < 0.08:
        raise RateLimitError("rate limit exceeded")
    if roll < 0.18:
        raise TemporaryServerError("temporary server error")

    station_id = url.rstrip("/").split("/")[-1]
    return {
        "station": station_id,
        "url": url,
        "temperature_c": round(random.uniform(-10, 38), 1),
        "humidity_pct": round(random.uniform(15, 98), 1),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


async def fetch_with_retry(
    url: str,
    semaphore: asyncio.Semaphore,
    retries: int = 3,
    timeout: float = 1.5,
    base_backoff: float = 0.2,
) -> tuple[str, dict[str, Any] | None, str | None]:
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            async with semaphore:
                result = await asyncio.wait_for(simulated_station_request(url), timeout=timeout)
            return url, result, None
        except PermanentClientError as e:
            return url, None, f"permanent_error: {e}"
        except asyncio.TimeoutError:
            last_error = f"timeout after {timeout}s"
        except RateLimitError as e:
            last_error = f"rate_limited: {e}"
        except TemporaryServerError as e:
            last_error = f"temporary_error: {e}"
        except Exception as e:
            last_error = f"unexpected_error: {e}"

        if attempt < retries:
            await asyncio.sleep(base_backoff * (2 ** (attempt - 1)))

    return url, None, f"failed_after_{retries}_attempts: {last_error}"


async def _fetch_all_stations_async(urls: list[str], max_concurrent: int = 10) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [asyncio.create_task(fetch_with_retry(url, semaphore)) for url in urls]

    readings: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    for task in asyncio.as_completed(tasks):
        url, result, error = await task
        if error is None and result is not None:
            readings.append(result)
        else:
            errors[url] = error or "unknown error"

    readings.sort(key=lambda x: x.get("station", ""))
    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    return asyncio.run(_fetch_all_stations_async(urls, max_concurrent=max_concurrent))


def main() -> None:
    example_urls = [f"https://api.example.com/stations/{i:03d}" for i in range(1, 81)]
    example_urls += [
        "https://api.example.com/stations/bad-001",
        "https://api.example.com/stations/bad-002",
        "https://api.example.com/stations/slowfail-001",
        "https://api.example.com/stations/slowfail-002",
    ]

    start = time.perf_counter()
    results = fetch_all_stations(example_urls, max_concurrent=12)
    elapsed = time.perf_counter() - start

    print("Readings:", len(results["readings"]))
    print("Errors:", len(results["errors"]))
    print("Elapsed:", round(elapsed, 3), "seconds")
    print(results)


if __name__ == "__main__":
    main()