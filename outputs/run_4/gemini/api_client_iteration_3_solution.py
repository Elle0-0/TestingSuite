import asyncio
import time
import aiohttp
from typing import Any, Coroutine, Type

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
REQUEST_TIMEOUT = 5

async def _fetch_one_with_retries(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore
) -> dict[str, Any]:
    """Helper to fetch a single URL with retries and semaphore control."""
    last_exception: Exception | None = None
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    response.raise_for_status()
                    return await response.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BACKOFF_FACTOR * (2 ** attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                last_exception = e
                break

    raise last_exception if last_exception is not None else Exception(f"Unknown error fetching {url}")


async def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetches data from multiple station URLs concurrently.

    Improves overall execution time by processing stations concurrently,
    ensuring that failures or delays from one station do not block others.

    Args:
        urls: A list of station data URLs.
        max_concurrent: The maximum number of concurrent requests.

    Returns:
        A dictionary with "readings" and "errors" keys.
    """
    if not urls:
        return {"readings": [], "errors": {}}

    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, list | dict] = {"readings": [], "errors": {}}

    async with aiohttp.ClientSession() as session:
        tasks: list[Coroutine] = [
            _fetch_one_with_retries(session, url, semaphore) for url in urls
        ]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

    for url, result in zip(urls, task_results):
        if isinstance(result, dict):
            results["readings"].append(result)
        elif isinstance(result, Exception):
            error_type: Type[Exception] = type(result)
            results["errors"][url] = f"{error_type.__name__}: {result}"
        else:
            results["errors"][url] = f"Unknown failure: {result}"

    return results


async def main() -> None:
    """
    Demonstrates the concurrent station data fetching solution with a
    large list of example URLs.
    """
    base_url = "https://httpbin.org"
    station_urls = [f"{base_url}/get?station_id={i:03}" for i in range(1, 41)]
    station_urls.extend([
        f"{base_url}/delay/4",              # A very slow but successful response
        f"{base_url}/status/500",           # A server error that will fail
        "http://nonexistent.domain.invalid", # A DNS error that will fail
        f"{base_url}/status/404",           # A not-found error that will fail
        f"{base_url}/get?station_id=999",     # Another successful one
        f"{base_url}/delay/2",              # A moderately slow one
    ])

    print(f"--- Starting concurrent fetch for {len(station_urls)} stations ---")
    start_time = time.monotonic()

    data = await fetch_all_stations(station_urls, max_concurrent=15)

    end_time = time.monotonic()
    elapsed_time = end_time - start_time

    print(f"\n--- Fetching Complete in {elapsed_time:.2f} seconds ---")

    print(f"\nSuccessfully fetched readings: {len(data['readings'])}")
    if data['readings']:
        print("Example reading:", data['readings'][0])

    print(f"\nFailed stations: {len(data['errors'])}")
    if data['errors']:
        for url, error in data['errors'].items():
            print(f"  - {url}: {error}")


if __name__ == "__main__":
    asyncio.run(main())