import asyncio
import random
import time
from typing import Any


class TemporaryStationError(Exception):
    pass


class PermanentStationError(Exception):
    pass


class ServiceRestrictionError(Exception):
    pass


async def fetch_station_with_retries(
    url: str,
    retries: int = 3,
    base_delay: float = 0.2,
    timeout: float = 2.5,
) -> dict[str, Any]:
    attempt = 0
    last_error: Exception | None = None

    while attempt <= retries:
        try:
            return await asyncio.wait_for(simulated_station_request(url), timeout=timeout)
        except ServiceRestrictionError:
            raise
        except PermanentStationError:
            raise
        except (TemporaryStationError, asyncio.TimeoutError) as exc:
            last_error = exc
            if attempt == retries:
                break
            await asyncio.sleep(base_delay * (2 ** attempt))
            attempt += 1

    if isinstance(last_error, asyncio.TimeoutError):
        raise TimeoutError(f"Timeout after {retries + 1} attempts")
    if last_error is not None:
        raise last_error
    raise RuntimeError("Unknown failure")


async def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    semaphore = asyncio.Semaphore(max_concurrent)
    readings: dict[str, Any] = {}
    errors: dict[str, str] = {}

    async def worker(url: str) -> None:
        async with semaphore:
            try:
                result = await fetch_station_with_retries(url)
                readings[url] = result
            except Exception as exc:
                errors[url] = f"{type(exc).__name__}: {exc}"

    await asyncio.gather(*(worker(url) for url in urls))
    return {"readings": readings, "errors": errors}


async def simulated_station_request(url: str) -> dict[str, Any]:
    seed = sum(ord(c) for c in url)
    rng = random.Random(seed)

    if "restricted" in url:
        await asyncio.sleep(0.05)
        raise ServiceRestrictionError("Access denied by service policy")

    station_id = url.rsplit("/", 1)[-1]

    mode = seed % 10

    if "permanent" in url or mode == 0:
        await asyncio.sleep(0.1 + rng.random() * 0.2)
        raise PermanentStationError("Station endpoint is invalid")

    if "slow" in url or mode in (1, 2):
        await asyncio.sleep(3.2)

    await asyncio.sleep(0.1 + rng.random() * 1.0)

    if "flaky" in url or mode in (3, 4):
        if rng.random() < 0.7:
            raise TemporaryStationError("Transient upstream error")

    temperature = round(-5 + rng.random() * 40, 2)
    humidity = round(20 + rng.random() * 70, 2)
    pressure = round(980 + rng.random() * 50, 2)

    return {
        "station": station_id,
        "temperature_c": temperature,
        "humidity_pct": humidity,
        "pressure_hpa": pressure,
    }


def build_example_urls(count: int = 60) -> list[str]:
    urls = []
    for i in range(count):
        if i % 17 == 0:
            suffix = f"restricted-station-{i}"
        elif i % 13 == 0:
            suffix = f"permanent-station-{i}"
        elif i % 11 == 0:
            suffix = f"slow-station-{i}"
        elif i % 7 == 0:
            suffix = f"flaky-station-{i}"
        else:
            suffix = f"station-{i}"
        urls.append(f"https://api.example.com/{suffix}")
    return urls


def main() -> None:
    urls = build_example_urls(80)
    start = time.perf_counter()
    result = asyncio.run(fetch_all_stations(urls, max_concurrent=10))
    elapsed = time.perf_counter() - start

    print("Readings:")
    for url, reading in sorted(result["readings"].items()):
        print(f"{url}: {reading}")

    print("\nErrors:")
    for url, error in sorted(result["errors"].items()):
        print(f"{url}: {error}")

    print(f"\nTotal stations: {len(urls)}")
    print(f"Successful readings: {len(result['readings'])}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Elapsed time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()