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
                                delay = float(retry_after)
                            except ValueError:
                                delay = base_delay * (2 ** attempt)
                        else:
                            delay = base_delay * (2 ** attempt)
                        last_error = f"Rate limited (429) on attempt {attempt + 1}"
                        await asyncio.sleep(delay)
                        continue
                    elif response.status >= 500:
                        # Server error - retry with backoff
                        last_error = f"Server error ({response.status}) on attempt {attempt + 1}"
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Client error (4xx except 429) - don't retry
                        error_text = await response.text()
                        last_error = f"HTTP {response.status}: {error_text[:200]}"
                        return (url, None, last_error)

            except asyncio.TimeoutError:
                last_error = f"Timeout on attempt {attempt + 1}"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                continue
            except aiohttp.ClientError as e:
                last_error = f"Connection error on attempt {attempt + 1}: {str(e)}"
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                continue
            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                return (url, None, last_error)

        return (url, None, f"Failed after {max_retries} retries. Last error: {last_error}")


async def _fetch_all_stations_async(
    urls: list[str], max_concurrent: int = 10
) -> dict:
    """
    Async implementation that fetches from multiple stations concurrently.
    """
    readings = {}
    errors = {}
    semaphore = asyncio.Semaphore(max_concurrent)

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
                # fetch_single_station, but handle it as a safeguard
                errors["unknown"] = f"Unexpected task exception: {str(result)}"
                continue

            url, data, error = result
            if data is not None:
                readings[url] = data
            if error is not None:
                errors[url] = error

    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch data from multiple station URLs concurrently.
    
    Returns a dict with:
      - "readings": dict mapping URL -> response data for successful fetches
      - "errors": dict mapping URL -> error message for failed fetches
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
    Demonstrate the concurrent station fetching solution with a large list of URLs.
    """
    # Generate a large list of example station URLs
    # Using httpbin.org and similar public endpoints for demonstration
    base_urls = [
        "https://httpbin.org/get",
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
        # Most URLs are valid endpoints
        if i % 10 == 0:
            urls.append(f"https://httpbin.org/status/500?station={i}")
        elif i % 15 == 0:
            urls.append(f"https://httpbin.org/status/429?station={i}")
        elif i % 7 == 0:
            urls.append(f"https://httpbin.org/delay/3?station={i}")
        elif i % 13 == 0:
            urls.append(f"https://invalid-host-that-does-not-exist.example.com/station/{i}")
        else:
            urls.append(f"https://httpbin.org/get?station={i}")

    print(f"Fetching data from {len(urls)} stations with max_concurrent=10...")
    print("=" * 70)

    start_time = time.time()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.time() - start_time

    successful = results["readings"]
    failed = results["errors"]

    print(f"\nResults Summary:")
    print(f"  Total stations:     {len(urls)}")
    print(f"  Successful:         {len(successful)}")
    print(f"  Failed:             {len(failed)}")
    print(f"  Total elapsed time: {elapsed:.2f} seconds")
    print(f"  Avg time/station:   {elapsed / len(urls):.3f} seconds")
    print()

    # Show a few successful readings
    print("Sample successful readings:")
    for i, (url, data) in enumerate(successful.items()):
        if i >= 3:
            print(f"  ... and {len(successful) - 3} more")
            break
        # Truncate data for display
        data_str = json.dumps(data)
        if len(data_str) > 100:
            data_str = data_str[:100] + "..."
        print(f"  {url}")
        print(f"    -> {data_str}")
    print()

    # Show errors
    if failed:
        print("Errors encountered:")
        for i, (url, error) in enumerate(failed.items()):
            if i >= 5:
                print(f"  ... and {len(failed) - 5} more errors")
                break
            print(f"  {url}")
            print(f"    -> {error}")
    else:
        print("No errors encountered.")

    print()
    print(f"Done in {elapsed:.2f}s (would take ~{len(urls) * 2:.0f}s+ sequentially)")

    return results


if __name__ == "__main__":
    main()