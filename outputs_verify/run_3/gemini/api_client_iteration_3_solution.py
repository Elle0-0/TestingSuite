import asyncio
import time
import json
from typing import Any, Coroutine, cast

import aiohttp

MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5
RETRY_STATUSES = {503}

async def _fetch_one_with_semaphore(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
) -> tuple[str, dict[str, Any] | str]:
    """
    Fetches a single URL with retries, respecting the concurrency semaphore.
    Returns a tuple of (url, result_dict) or (url, error_message_str).
    """
    async with semaphore:
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                delay = BACKOFF_FACTOR * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
            try:
                # Set a reasonable timeout for the entire request operation
                timeout = aiohttp.ClientTimeout(total=15)
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        try:
                            # The aiohttp response.json() method can raise
                            # a ContentTypeError if the content is not JSON.
                            data = await response.json()
                            return url, cast(dict[str, Any], data)
                        except (json.JSONDecodeError, aiohttp.ContentTypeError) as e:
                            msg = f"Failed to decode JSON: {e}"
                            return url, msg

                    elif response.status in RETRY_STATUSES:
                        last_exc = aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=f"Service unavailable (status {response.status})",
                        )
                        continue  # Move to the next retry attempt

                    else:
                        # For other non-successful status codes, fail immediately
                        msg = f"HTTP Error: Received status {response.status}"
                        return url, msg

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                # Covers connection errors, DNS errors, timeouts, etc.
                last_exc = e
                continue  # Move to the next retry attempt

        # If all retries fail, return the last known error
        error_message = f"All {MAX_RETRIES} attempts failed for {url}. Last error: {last_exc}"
        return url, error_message


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetches data from a list of station URLs concurrently.

    Args:
        urls: A list of URLs to fetch.
        max_concurrent: The maximum number of concurrent requests.

    Returns:
        A dictionary with "readings" (a list of successful JSON responses)
        and "errors" (a dict mapping URLs to error messages).
    """
    async def _async_main() -> dict:
        """The core async implementation."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Use a single session for connection pooling, which is more efficient.
        async with aiohttp.ClientSession() as session:
            tasks: list[Coroutine[Any, Any, tuple[str, dict[str, Any] | str]]] = [
                _fetch_one_with_semaphore(session, url, semaphore) for url in urls
            ]
            
            # Run all fetch tasks concurrently and wait for them to complete.
            results = await asyncio.gather(*tasks)

        readings: list[dict] = []
        errors: dict[str, str] = {}
        for url_result, data_or_error in results:
            if isinstance(data_or_error, dict):
                readings.append(data_or_error)
            else:
                errors[url_result] = str(data_or_error)
        
        return {"readings": readings, "errors": errors}

    # In Python 3.7+, asyncio.run is the standard way to execute an async
    # function from synchronous code. It handles the event loop automatically.
    return asyncio.run(_async_main())


def main() -> None:
    """
    Demonstrates the concurrent fetching of station data and reports results.
    """
    # Use httpbin.org to simulate a web service with varied responses
    base_url = "https://httpbin.org"

    # Generate a large and diverse list of URLs for testing
    urls = []

    # 50 successful stations (using /anything to get a JSON response)
    for i in range(50):
        # httpbin's /anything/{val} endpoint returns a JSON object containing
        # the provided value, which simulates a unique station ID.
        urls.append(f"{base_url}/anything/station_{i:03d}")

    # 10 slow stations (simulating a 2-second network delay)
    for i in range(10):
        urls.append(f"{base_url}/delay/2")

    # 10 stations that will fail with 503 (and should be retried)
    for i in range(10):
        urls.append(f"{base_url}/status/503")

    # 5 stations that will fail with 404 (and should not be retried)
    for i in range(5):
        urls.append(f"{base_url}/status/404")

    # 5 invalid hostnames that will cause connection/DNS errors
    for i in range(5):
        urls.append(f"http://invalid-hostname-for-testing-{i}.local")

    # 5 URLs that do not return JSON content type
    for i in range(5):
        urls.append(f"{base_url}/html")

    print(f"Fetching data from {len(urls)} stations with max_concurrent=25...")
    start_time = time.monotonic()

    results = fetch_all_stations(urls, max_concurrent=25)

    end_time = time.monotonic()

    print("\n--- Summary ---")
    print(f"Total stations processed: {len(urls)}")
    print(f"Successful readings: {len(results.get('readings', []))}")
    print(f"Failed stations: {len(results.get('errors', {}))}")
    print(f"Total execution time: {end_time - start_time:.2f} seconds")

    print("\n--- Successful Readings (first 5) ---")
    for reading in results.get("readings", [])[:5]:
        # The /anything endpoint reflects the request URL in its response
        print(f"  - Successfully fetched from: {reading.get('url')}")

    print("\n--- Errors ---")
    if results.get("errors"):
        for url, error in results["errors"].items():
            print(f"  - {url}: {error}")
    else:
        print("  No errors reported.")


if __name__ == "__main__":
    main()