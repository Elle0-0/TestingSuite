import asyncio
import random
import time
from urllib.parse import urlparse, parse_qs


MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 0.2
REQUEST_TIMEOUT_SECONDS = 1.5


class TemporaryStationError(Exception):
    pass


class PermanentStationError(Exception):
    pass


class RateLimitError(Exception):
    pass


async def simulated_fetch(url: str) -> dict:
    parsed = urlparse(url)
    station = parsed.path.strip("/") or "unknown"
    query = parse_qs(parsed.query)
    mode = query.get("mode", ["ok"])[0]

    if "delay" in query:
        try:
            delay = float(query["delay"][0])
        except ValueError:
            delay = random.uniform(0.05, 0.3)
    else:
        delay = random.uniform(0.05, 0.6)

    await asyncio.sleep(delay)

    if mode == "ok":
        return {
            "station": station,
            "value": round(random.uniform(10.0, 99.9), 2),
            "unit": "kWh",
        }
    if mode == "timeout":
        await asyncio.sleep(10)
    if mode == "tempfail":
        raise TemporaryStationError("temporary upstream failure")
    if mode == "rate":
        raise RateLimitError("rate limited by service")
    if mode == "permfail":
        raise PermanentStationError("permanent station failure")

    return {
        "station": station,
        "value": round(random.uniform(10.0, 99.9), 2),
        "unit": "kWh",
    }


async def fetch_station_with_retries(url: str) -> tuple[str, dict | None, str | None]:
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await asyncio.wait_for(simulated_fetch(url), timeout=REQUEST_TIMEOUT_SECONDS)
            return url, result, None
        except PermanentStationError as exc:
            return url, None, f"permanent_error: {exc}"
        except RateLimitError as exc:
            return url, None, f"rate_limited: {exc}"
        except asyncio.TimeoutError:
            last_error = "timeout"
        except TemporaryStationError as exc:
            last_error = f"temporary_error: {exc}"
        except Exception as exc:
            last_error = f"unexpected_error: {exc}"

        if attempt < MAX_RETRIES:
            await asyncio.sleep(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)))

    return url, None, f"failed_after_{MAX_RETRIES}_retries: {last_error}"


async def _fetch_all_stations_async(urls: list[str], max_concurrent: int = 10) -> dict:
    semaphore = asyncio.Semaphore(max(1, max_concurrent))
    readings = {}
    errors = {}

    async def worker(url: str) -> None:
        async with semaphore:
            station_url, reading, error = await fetch_station_with_retries(url)
            if error is None:
                readings[station_url] = reading
            else:
                errors[station_url] = error

    await asyncio.gather(*(worker(url) for url in urls))
    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    return asyncio.run(_fetch_all_stations_async(urls, max_concurrent=max_concurrent))


def build_example_urls(count: int = 60) -> list[str]:
    urls = []
    modes = ["ok"] * 40 + ["tempfail"] * 8 + ["permfail"] * 5 + ["rate"] * 4 + ["timeout"] * 3
    random.shuffle(modes)

    for i in range(count):
        mode = modes[i % len(modes)]
        delay = round(random.uniform(0.05, 1.2), 2)
        urls.append(f"https://api.example.com/station-{i+1}?mode={mode}&delay={delay}")

    return urls


def main() -> None:
    urls = build_example_urls(80)
    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print("Readings:")
    for url, reading in result["readings"].items():
        print(f"{url} -> {reading}")

    print("\nErrors:")
    for url, error in result["errors"].items():
        print(f"{url} -> {error}")

    print(f"\nSummary: {len(result['readings'])} successes, {len(result['errors'])} errors")
    print(f"Elapsed time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()