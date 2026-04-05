import asyncio
import aiohttp
import time
import json
from typing import Optional


async def fetch_single_station(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> tuple[str, Optional[dict], Optional[str]]:
    """
    Fetch data from a single station with retries and exponential backoff.
    Returns (url, data_or_none, error_or_none).
    """
    async with semaphore:
        last_error = None
        for attempt in range(max_retries):
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return (url, data, None)
                    elif response.status == 429:
                        # Rate limited - respect Retry-After header if present
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait_time = float(retry_after)
                            except ValueError:
                                wait_time = base_delay * (2 ** attempt)
                        else:
                            wait_time = base_delay * (2 ** attempt)
                        last_error = f"HTTP 429 Too Many Requests"
                        if attempt < max_retries - 1:
                            await asyncio.sleep(wait_time)
                            continue
                    elif response.status >= 500:
                        # Server error - retry with backoff
                        last_error = f"HTTP {response.status}"
                        if attempt < max_retries - 1:
                            await asyncio.sleep(base_delay * (2 ** attempt))
                            continue
                    else:
                        # Client error (4xx except 429) - don't retry
                        last_error = f"HTTP {response.status}"
                        break
            except asyncio.TimeoutError:
                last_error = f"Timeout after {timeout}s"
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
            except aiohttp.ClientConnectionError as e:
                last_error = f"Connection error: {e}"
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
            except aiohttp.ClientError as e:
                last_error = f"Client error: {e}"
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                break

        return (url, None, last_error)


async def _fetch_all_stations_async(
    urls: list[str], max_concurrent: int = 10
) -> dict:
    """
    Async implementation that fetches all stations concurrently
    with bounded concurrency.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    readings = {}
    errors = {}

    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_single_station(session, url, semaphore)
            for url in urls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                # This shouldn't normally happen since we catch exceptions inside
                # fetch_single_station, but handle it just in case
                errors["unknown"] = f"Unexpected gather error: {result}"
                continue

            url, data, error = result
            if data is not None:
                readings[url] = data
            else:
                errors[url] = error or "Unknown error"

    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch data from multiple station URLs concurrently.
    
    Args:
        urls: List of station API endpoint URLs
        max_concurrent: Maximum number of concurrent requests
        
    Returns:
        dict with "readings" (url -> data) and "errors" (url -> error message)
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're already in an async context; create a new thread to run
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run,
                _fetch_all_stations_async(urls, max_concurrent)
            )
            return future.result()
    else:
        return asyncio.run(_fetch_all_stations_async(urls, max_concurrent))


def main():
    """Demonstrate concurrent station fetching with a large list of URLs."""
    
    # Generate a large list of example URLs simulating many weather stations
    # Using httpbin.org and similar services for demonstration
    base_urls = [
        # These will likely fail but demonstrate the concurrent fetching approach
        "https://httpbin.org/json",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/2",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/404",
        "https://httpbin.org/status/429",
    ]
    
    # Create a larger set of URLs to demonstrate scale
    urls = []
    for i in range(50):
        # Mix of various endpoints
        urls.append(f"https://httpbin.org/anything?station={i}")
    
    # Add some URLs that will definitely fail to demonstrate error handling
    urls.extend([
        "https://nonexistent-weather-station-12345.example.com/api/data",
        "https://another-fake-station-67890.example.com/api/readings",
        "http://localhost:19999/api/station/data",  # Likely nothing listening
    ])
    
    print(f"Fetching data from {len(urls)} stations concurrently...")
    print(f"Max concurrent requests: 10")
    print("-" * 60)
    
    start_time = time.time()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.time() - start_time
    
    readings = results["readings"]
    errors = results["errors"]
    
    print(f"\nResults Summary:")
    print(f"  Total stations:     {len(urls)}")
    print(f"  Successful:         {len(readings)}")
    print(f"  Failed:             {len(errors)}")
    print(f"  Total elapsed time: {elapsed:.2f}s")
    print(f"  Avg time/station:   {elapsed / len(urls):.3f}s")
    
    # Show a few successful readings
    if readings:
        print(f"\nSample successful readings (first 3):")
        for i, (url, data) in enumerate(list(readings.items())[:3]):
            print(f"  [{i+1}] {url}")
            # Truncate data display
            data_str = json.dumps(data)
            if len(data_str) > 100:
                data_str = data_str[:100] + "..."
            print(f"      Data: {data_str}")
    
    # Show error details
    if errors:
        print(f"\nSample errors (first 5):")
        for i, (url, error) in enumerate(list(errors.items())[:5]):
            print(f"  [{i+1}] {url}")
            print(f"      Error: {error}")
    
    print(f"\n{'=' * 60}")
    print(f"Done. Total time: {elapsed:.2f}s")
    
    return results


if __name__ == "__main__":
    main()