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
                    # Rate limited - respect Retry-After header if present
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        delay = float(retry_after)
                    else:
                        delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(f"Rate limited (429) from {url}")
                    continue
                elif response.status >= 500:
                    # Server error - retry with backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(f"Server error ({response.status}) from {url}")
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
            last_exception = Exception(f"Timeout fetching {url} (attempt {attempt + 1})")
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
        "error": f"Failed after {max_retries} retries: {last_exception}",
    }


async def fetch_station(
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> dict:
    """Fetch a single station with concurrency limiting via semaphore."""
    async with semaphore:
        return await fetch_with_retry(session, url, max_retries, base_delay, timeout)


async def _fetch_all_stations_async(
    urls: list[str],
    max_concurrent: int = 10,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> dict:
    """Async implementation of fetch_all_stations."""
    readings = {}
    errors = {}
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=5)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            fetch_station(semaphore, session, url, max_retries, base_delay, timeout)
            for url in urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                # Shouldn't happen since we catch exceptions in fetch_station,
                # but handle it defensively
                errors["unknown"] = str(result)
                continue
            
            url = result["url"]
            if result["success"]:
                readings[url] = result["data"]
            else:
                errors[url] = result["error"]
    
    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch readings from multiple station URLs concurrently.
    
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
    """Demonstrate the solution with a large list of example URLs."""
    # Generate a large list of example station URLs
    # Using httpbin.org and similar test endpoints to demonstrate
    example_urls = []
    
    # Some URLs that should succeed (using public APIs)
    for i in range(50):
        example_urls.append(f"https://jsonplaceholder.typicode.com/posts/{(i % 100) + 1}")
    
    # Some URLs that will fail (non-existent endpoints)
    for i in range(10):
        example_urls.append(f"https://httpbin.org/status/500")
    
    # Some URLs that will timeout or fail to connect
    for i in range(5):
        example_urls.append(f"http://192.0.2.1:9999/station/{i}")  # Non-routable address
    
    # Some URLs with 404 errors
    for i in range(5):
        example_urls.append(f"https://jsonplaceholder.typicode.com/nonexistent/{i}")
    
    total_stations = len(example_urls)
    print(f"Fetching data from {total_stations} stations with max_concurrent=10...")
    print("=" * 60)
    
    start_time = time.time()
    results = fetch_all_stations(example_urls, max_concurrent=10)
    elapsed = time.time() - start_time
    
    successful = len(results["readings"])
    failed = len(results["errors"])
    
    print(f"\nResults Summary:")
    print(f"  Total stations:  {total_stations}")
    print(f"  Successful:      {successful}")
    print(f"  Failed:          {failed}")
    print(f"  Elapsed time:    {elapsed:.2f}s")
    print(f"  Avg per station: {elapsed / total_stations * 1000:.1f}ms")
    
    # Show a few successful readings
    print(f"\nSample successful readings (first 3):")
    for i, (url, data) in enumerate(list(results["readings"].items())[:3]):
        print(f"  [{i+1}] {url}")
        if isinstance(data, dict):
            # Show truncated data
            preview = json.dumps(data, indent=None)[:100]
            print(f"      Data: {preview}...")
        else:
            print(f"      Data: {str(data)[:100]}...")
    
    # Show a few errors
    print(f"\nSample errors (first 5):")
    for i, (url, error) in enumerate(list(results["errors"].items())[:5]):
        print(f"  [{i+1}] {url}")
        print(f"      Error: {error[:100]}")
    
    print(f"\n{'=' * 60}")
    print(f"Total elapsed time: {elapsed:.2f} seconds")
    
    return results


if __name__ == "__main__":
    main()