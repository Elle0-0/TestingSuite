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
    Fetch data from a single station URL with retries and exponential backoff.
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
                last_error = "Request timed out"
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
    Async implementation that fetches from multiple stations concurrently.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {"readings": {}, "errors": {}}

    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_single_station(session, url, semaphore)
            for url in urls
        ]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if isinstance(result, Exception):
                # If gather itself caught an exception (shouldn't happen with our error handling)
                results["errors"]["unknown"] = str(result)
            else:
                url, data, error = result
                if data is not None:
                    results["readings"][url] = data
                else:
                    results["errors"][url] = error or "Unknown error"

    return results


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch data from multiple station URLs concurrently.
    
    Returns a dict with:
        "readings": {url: data} for successful fetches
        "errors": {url: error_message} for failed fetches
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
    """
    Demonstrate the concurrent station fetching with a large list of example URLs.
    """
    # Generate a large list of example station URLs
    # Using httpbin.org and similar test endpoints for demonstration
    base_urls = [
        "https://httpbin.org/json",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/404",
        "https://httpbin.org/status/429",
    ]

    # Create a larger set of URLs to demonstrate scale
    urls = []
    for i in range(50):
        urls.append(f"https://httpbin.org/anything?station={i}")

    # Add some that will fail
    urls.extend([
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/404",
        "https://nonexistent.invalid/api/station/999",
        "https://httpbin.org/delay/15",  # Will timeout
    ])

    print(f"Fetching data from {len(urls)} stations with max 10 concurrent requests...")
    print("=" * 70)

    start_time = time.time()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.time() - start_time

    successful = len(results["readings"])
    failed = len(results["errors"])

    print(f"\nResults Summary:")
    print(f"  Total stations:     {len(urls)}")
    print(f"  Successful:         {successful}")
    print(f"  Failed:             {failed}")
    print(f"  Total elapsed time: {elapsed:.2f} seconds")
    print(f"  Avg time/station:   {elapsed / len(urls):.3f} seconds")
    print()

    # Print first few successful readings
    print("Sample successful readings:")
    for i, (url, data) in enumerate(results["readings"].items()):
        if i >= 3:
            print(f"  ... and {successful - 3} more")
            break
        print(f"  {url}: {json.dumps(data, indent=None)[:100]}...")

    print()

    # Print all errors
    if results["errors"]:
        print("Errors encountered:")
        for url, error in results["errors"].items():
            print(f"  {url}: {error}")

    print()
    print(f"Done in {elapsed:.2f}s")


if __name__ == "__main__":
    main()