import asyncio
import aiohttp
import time
import json
from typing import Optional


async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> dict:
    """Fetch a single station URL with retry logic and exponential backoff."""
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"url": url, "success": True, "data": data}
                elif response.status == 429:
                    # Rate limited - respect Retry-After header
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        delay = float(retry_after)
                    else:
                        delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(f"Rate limited (429) at {url}")
                    continue
                elif response.status >= 500:
                    # Server error - retry with backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(f"Server error ({response.status}) at {url}")
                    continue
                else:
                    # Client error (4xx except 429) - don't retry
                    text = await response.text()
                    return {
                        "url": url,
                        "success": False,
                        "error": f"HTTP {response.status}: {text[:200]}",
                    }
        except asyncio.TimeoutError:
            delay = base_delay * (2 ** attempt)
            last_exception = Exception(f"Timeout fetching {url}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
        except aiohttp.ClientError as e:
            delay = base_delay * (2 ** attempt)
            last_exception = e
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
    
    return {
        "url": url,
        "success": False,
        "error": f"Failed after {max_retries} retries: {str(last_exception)}",
    }


async def fetch_station(
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    url: str,
    max_retries: int = 3,
) -> dict:
    """Fetch a single station with concurrency limiting via semaphore."""
    async with semaphore:
        return await fetch_with_retry(session, url, max_retries=max_retries)


async def _fetch_all_stations_async(
    urls: list[str], max_concurrent: int = 10
) -> dict:
    """Async implementation of fetch_all_stations."""
    readings = {}
    errors = {}
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    connector = aiohttp.TCPConnector(
        limit=max_concurrent,
        limit_per_host=5,
    )
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.create_task(fetch_station(semaphore, session, url))
            for url in urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            # Shouldn't happen since fetch_station catches exceptions, but handle anyway
            errors["unknown"] = str(result)
        elif result["success"]:
            readings[result["url"]] = result["data"]
        else:
            errors[result["url"]] = result["error"]
    
    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch data from multiple station URLs concurrently.
    
    Args:
        urls: List of station API endpoint URLs
        max_concurrent: Maximum number of concurrent requests
        
    Returns:
        Dictionary with "readings" (successful responses) and "errors" (failed responses)
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
    """Demonstrate the solution with a large list of example URLs."""
    # Generate a large list of example station URLs
    # Using httpbin.org and similar test endpoints to demonstrate
    example_urls = []
    
    # Mix of likely-working and likely-failing URLs for demonstration
    for i in range(50):
        example_urls.append(f"https://httpbin.org/json?station={i}")
    
    # Add some URLs that will produce errors
    for i in range(10):
        example_urls.append(f"https://httpbin.org/status/500?station=err_{i}")
    
    for i in range(5):
        example_urls.append(f"https://httpbin.org/status/404?station=notfound_{i}")
    
    for i in range(5):
        example_urls.append(f"https://nonexistent-domain-abc123xyz.com/station/{i}")
    
    # Add some timeout-prone URLs
    for i in range(5):
        example_urls.append(f"https://httpbin.org/delay/15?station=slow_{i}")
    
    total_urls = len(example_urls)
    print(f"Fetching data from {total_urls} stations with max 10 concurrent requests...")
    print("=" * 70)
    
    start_time = time.time()
    results = fetch_all_stations(example_urls, max_concurrent=10)
    elapsed = time.time() - start_time
    
    readings = results["readings"]
    errors = results["errors"]
    
    print(f"\nResults Summary:")
    print(f"  Total stations: {total_urls}")
    print(f"  Successful:     {len(readings)}")
    print(f"  Failed:         {len(errors)}")
    print(f"  Elapsed time:   {elapsed:.2f} seconds")
    print(f"  Avg per station: {elapsed / total_urls:.3f} seconds")
    print()
    
    # Show a few successful readings
    print("Sample successful readings:")
    for url in list(readings.keys())[:3]:
        data_str = json.dumps(readings[url], indent=2)
        if len(data_str) > 200:
            data_str = data_str[:200] + "..."
        print(f"  {url}:")
        print(f"    {data_str[:100]}...")
    
    print()
    
    # Show errors
    if errors:
        print("Errors encountered:")
        for url, error in list(errors.items())[:10]:
            print(f"  {url}:")
            print(f"    {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    print()
    print(f"Total elapsed time: {elapsed:.2f}s")
    
    # Estimate sequential time
    estimated_sequential = total_urls * (elapsed / total_urls) * 10  # rough estimate
    print(f"Estimated sequential time would be: ~{estimated_sequential:.0f}s")
    print(f"Speedup factor: ~{estimated_sequential / elapsed:.1f}x")


if __name__ == "__main__":
    main()