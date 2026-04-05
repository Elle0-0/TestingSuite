import asyncio
import aiohttp
import time
import json
from typing import Any


async def fetch_single_station(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> tuple[str, dict | None, str | None]:
    """
    Fetch data from a single station with retries and exponential backoff.
    Returns (url, data_or_none, error_or_none).
    """
    async with semaphore:
        last_error = None
        for attempt in range(max_retries):
            try:
                client_timeout = aiohttp.ClientTimeout(total=timeout)
                async with session.get(url, timeout=client_timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        return (url, data, None)
                    elif response.status == 429:
                        # Rate limited - respect Retry-After header if present
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = base_delay * (2 ** attempt)
                        else:
                            delay = base_delay * (2 ** attempt)
                        last_error = f"HTTP 429 Too Many Requests"
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            continue
                    elif response.status >= 500:
                        # Server error - retry with backoff
                        last_error = f"HTTP {response.status}"
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue
                    else:
                        # Client error (4xx except 429) - don't retry
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text[:200]}"
                        return (url, None, last_error)

            except asyncio.TimeoutError:
                last_error = f"Timeout after {timeout}s"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue

            except aiohttp.ClientError as e:
                last_error = f"Connection error: {str(e)}"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue

        return (url, None, f"Failed after {max_retries} retries. Last error: {last_error}")


async def _fetch_all_stations_async(
    urls: list[str],
    max_concurrent: int = 10,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> dict:
    """
    Async implementation that fetches all stations concurrently with bounded concurrency.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, Any] = {"readings": {}, "errors": {}}

    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_single_station(
                session, url, semaphore,
                max_retries=max_retries,
                base_delay=base_delay,
                timeout=timeout,
            )
            for url in urls
        ]

        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                # This shouldn't normally happen since we catch exceptions inside
                # fetch_single_station, but handle it just in case
                results["errors"]["unknown"] = f"Task exception: {str(result)}"
            else:
                url, data, error = result
                if error is None and data is not None:
                    results["readings"][url] = data
                else:
                    results["errors"][url] = error or "Unknown error"

    return results


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch data from multiple weather stations concurrently.

    Args:
        urls: List of station API endpoint URLs.
        max_concurrent: Maximum number of concurrent requests.

    Returns:
        Dictionary with "readings" (successful responses) and "errors" (failed stations).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're already in an async context; create a new thread to run
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                _fetch_all_stations_async(urls, max_concurrent)
            )
            return future.result()
    else:
        return asyncio.run(_fetch_all_stations_async(urls, max_concurrent))


def main():
    """Demonstrate the concurrent station fetching with example URLs."""
    # Generate a large list of example URLs to demonstrate scale
    # Using httpbin.org and similar public test endpoints
    example_urls = []

    # Some URLs that should succeed (using httpbin)
    for i in range(20):
        example_urls.append(f"https://httpbin.org/get?station_id={i}")

    # Some URLs that will return specific status codes
    for code in [200, 200, 404, 500, 200]:
        example_urls.append(f"https://httpbin.org/status/{code}")

    # Some URLs with delays
    for delay in [1, 2, 1, 2, 1]:
        example_urls.append(f"https://httpbin.org/delay/{delay}")

    # Some URLs that won't resolve (to test connection errors)
    for i in range(5):
        example_urls.append(f"http://nonexistent-station-{i}.invalid/api/reading")

    print(f"Fetching data from {len(example_urls)} stations...")
    print(f"Using max_concurrent=10")
    print("-" * 60)

    start_time = time.time()
    results = fetch_all_stations(example_urls, max_concurrent=10)
    elapsed = time.time() - start_time

    successful = len(results["readings"])
    failed = len(results["errors"])

    print(f"\nResults Summary:")
    print(f"  Total stations: {len(example_urls)}")
    print(f"  Successful:     {successful}")
    print(f"  Failed:         {failed}")
    print(f"  Elapsed time:   {elapsed:.2f}s")
    print()

    if results["readings"]:
        print("Successful readings (first 5):")
        for i, (url, data) in enumerate(list(results["readings"].items())[:5]):
            # Truncate data display
            data_str = json.dumps(data)
            if len(data_str) > 100:
                data_str = data_str[:100] + "..."
            print(f"  [{i+1}] {url}")
            print(f"      -> {data_str}")
        if successful > 5:
            print(f"  ... and {successful - 5} more")
        print()

    if results["errors"]:
        print("Errors (first 10):")
        for i, (url, error) in enumerate(list(results["errors"].items())[:10]):
            print(f"  [{i+1}] {url}")
            print(f"      -> {error}")
        if failed > 10:
            print(f"  ... and {failed - 10} more")
        print()

    # Show the time advantage
    estimated_sequential = len(example_urls) * 2  # rough estimate
    print(f"Estimated sequential time: ~{estimated_sequential}s")
    print(f"Actual concurrent time:    {elapsed:.2f}s")
    if elapsed > 0:
        print(f"Speedup factor:            ~{estimated_sequential / elapsed:.1f}x")


if __name__ == "__main__":
    main()