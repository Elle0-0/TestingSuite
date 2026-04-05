import asyncio
import json
import time
from typing import Any

import aiohttp

RETRY_LIMIT = 3
RETRY_DELAY = 2  # seconds


class ServiceUnavailable(Exception):
    """Custom exception for 503 Service Unavailable."""
    pass


class TooManyRequests(Exception):
    """Custom exception for 429 Too Many Requests."""
    pass


async def _fetch_single_station(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
) -> tuple[str, dict | None, str | None]:
    """
    Fetches data for a single station URL with retry logic, inside a semaphore.
    """
    last_error_message = "Unknown error"
    async with semaphore:
        for attempt in range(RETRY_LIMIT):
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 503:
                        raise ServiceUnavailable(f"Service at {url} is unavailable")
                    if response.status == 429:
                        raise TooManyRequests(f"Too many requests to {url}")

                    response.raise_for_status()

                    # aiohttp is strict about content-type, but some servers
                    # might return application/json with a charset, so we
                    # relax the check by passing content_type=None.
                    data = await response.json(content_type=None)
                    return url, data, None  # Success

            except (ServiceUnavailable, TooManyRequests) as e:
                last_error_message = f"Attempt {attempt + 1}: {e}"
                if attempt < RETRY_LIMIT - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    return url, None, f"All retries failed. Last error: {e}"

            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                json.JSONDecodeError,
            ) as e:
                # These are considered non-recoverable and fail immediately
                error_msg = f"A non-retriable error occurred: {type(e).__name__}: {e}"
                return url, None, error_msg

        return url, None, f"All {RETRY_LIMIT} attempts failed. Last error: {last_error_message}"


async def fetch_all_stations(
    urls: list[str], max_concurrent: int = 10
) -> dict[str, Any]:
    """
    Fetches data from a list of station URLs concurrently.

    Args:
        urls: A list of URLs to fetch data from.
        max_concurrent: The maximum number of concurrent requests.

    Returns:
        A dictionary with "readings" for successful fetches and "errors"
        for failed fetches.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {"readings": {}, "errors": {}}

    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_single_station(session, url, semaphore) for url in urls
        ]
        processed_results = await asyncio.gather(*tasks, return_exceptions=False)

    for url, data, error in processed_results:
        if error:
            results["errors"][url] = error
        else:
            results["readings"][url] = data

    return results


async def main():
    """
    Demonstrates the concurrent station data fetching.
    """
    # A larger list of URLs to demonstrate concurrency benefits.
    # Includes valid, slow, failing, and non-existent endpoints.
    station_urls = [
        f"https://httpbin.org/json" for _ in range(20)
    ] + [
        f"https://httpbin.org/delay/{i % 4}" for i in range(15)
    ] + [
        "https://httpbin.org/status/503",
        "https://httpbin.org/status/429",
        "https://httpbin.org/status/404",
        "http://invalid.url.that.will.fail/api",
        "https://httpbin.org/html", # Will cause a JSONDecodeError
    ] * 2

    print(f"Fetching data for {len(station_urls)} stations...")
    start_time = time.perf_counter()

    # Use the async version of the function
    results = await fetch_all_stations(station_urls, max_concurrent=50)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    print(json.dumps(results, indent=2))
    print(f"\nTotal stations: {len(station_urls)}")
    print(f"Successful readings: {len(results['readings'])}")
    print(f"Failed attempts: {len(results['errors'])}")
    print(f"Total elapsed time: {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    # In Python 3.7+, asyncio.run is the standard way to run the top-level async function.
    asyncio.run(main())