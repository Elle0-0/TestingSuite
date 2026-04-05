import asyncio
import random
import time
from typing import Any, Dict, List, Optional


class APIError(Exception):
    pass


class RateLimitError(APIError):
    pass


class TemporaryError(APIError):
    pass


class PermanentError(APIError):
    pass


class InvalidResponseError(APIError):
    pass


MAX_RETRIES = 3
REQUEST_TIMEOUT = 2.5
BASE_BACKOFF = 0.2


async def simulated_station_request(url: str) -> Dict[str, Any]:
    seed = sum(ord(c) for c in url)
    rng = random.Random(seed + int(time.time() // 60))
    behavior = rng.random()

    if "blocked" in url:
        await asyncio.sleep(0.05)
        raise PermanentError("station access restricted")

    if "slow" in url:
        delay = 3.2 + rng.random() * 1.0
    else:
        delay = 0.05 + rng.random() * 1.5

    await asyncio.sleep(delay)

    if "badjson" in url:
        raise InvalidResponseError("invalid response payload")

    if behavior < 0.10:
        raise RateLimitError("rate limited")
    if behavior < 0.22:
        raise TemporaryError("temporary upstream failure")
    if behavior < 0.27:
        raise PermanentError("station not found")

    return {
        "station": url,
        "temperature_c": round(-10 + rng.random() * 45, 2),
        "humidity_pct": round(10 + rng.random() * 85, 2),
        "wind_kph": round(rng.random() * 60, 2),
    }


async def fetch_station(url: str) -> Dict[str, Any]:
    last_error: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await asyncio.wait_for(simulated_station_request(url), timeout=REQUEST_TIMEOUT)
        except asyncio.TimeoutError:
            last_error = TimeoutError(f"request timed out after {REQUEST_TIMEOUT}s")
        except RateLimitError as exc:
            last_error = exc
        except TemporaryError as exc:
            last_error = exc
        except PermanentError:
            raise
        except InvalidResponseError:
            raise

        if attempt < MAX_RETRIES:
            await asyncio.sleep(BASE_BACKOFF * (2 ** (attempt - 1)))

    if last_error is None:
        raise APIError("unknown failure")
    raise last_error


async def _fetch_with_semaphore(url: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    async with semaphore:
        try:
            reading = await fetch_station(url)
            return {"url": url, "reading": reading, "error": None}
        except Exception as exc:
            return {"url": url, "reading": None, "error": str(exc)}


async def _fetch_all_stations_async(urls: List[str], max_concurrent: int = 10) -> Dict[str, Any]:
    semaphore = asyncio.Semaphore(max_concurrent)
    tasks = [asyncio.create_task(_fetch_with_semaphore(url, semaphore)) for url in urls]
    results = await asyncio.gather(*tasks)

    output = {"readings": {}, "errors": {}}
    for item in results:
        if item["error"] is None:
            output["readings"][item["url"]] = item["reading"]
        else:
            output["errors"][item["url"]] = item["error"]
    return output


def fetch_all_stations(urls: List[str], max_concurrent: int = 10) -> Dict[str, Any]:
    return asyncio.run(_fetch_all_stations_async(urls, max_concurrent=max_concurrent))


def main() -> None:
    urls = []
    for i in range(1, 61):
        if i % 17 == 0:
            urls.append(f"https://api.example.com/stations/{i}/blocked")
        elif i % 13 == 0:
            urls.append(f"https://api.example.com/stations/{i}/badjson")
        elif i % 11 == 0:
            urls.append(f"https://api.example.com/stations/{i}/slow")
        else:
            urls.append(f"https://api.example.com/stations/{i}")

    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print("Readings:")
    for url, reading in result["readings"].items():
        print(f"{url}: {reading}")

    print("\nErrors:")
    for url, error in result["errors"].items():
        print(f"{url}: {error}")

    print(f"\nTotal elapsed time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()