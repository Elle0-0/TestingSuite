import asyncio
import aiohttp
import time
import json
from typing import Any


async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> dict[str, Any]:
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
                    last_exception = Exception(f"Rate limited (429) at {url}")
                    continue
                elif response.status >= 500:
                    # Server error - retry with backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(
                        f"Server error {response.status} at {url}"
                    )
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
        "error": f"Failed after {max_retries} retries: {last_exception}",
    }


async def _fetch_all_stations_async(
    urls: list[str], max_concurrent: int = 10
) -> dict[str, Any]:
    """Async implementation of fetch_all_stations."""
    readings = {}
    errors = {}
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_fetch(session: aiohttp.ClientSession, url: str) -> dict:
        async with semaphore:
            return await fetch_with_retry(session, url)
    
    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=5)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [bounded_fetch(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, Exception):
            # This shouldn't normally happen since fetch_with_retry catches exceptions
            errors["unknown"] = str(result)
        elif result["success"]:
            readings[result["url"]] = result["data"]
        else:
            errors[result["url"]] = result["error"]
    
    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict[str, Any]:
    """
    Fetch data from multiple station URLs concurrently.
    
    Returns a dict with:
        - "readings": dict mapping URL -> data for successful fetches
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
    
    # Mix of potentially valid and invalid URLs to demonstrate error handling
    for i in range(50):
        example_urls.append(f"https://httpbin.org/json?station={i}")
    
    # Add some that will produce errors
    for i in range(10):
        example_urls.append(f"https://httpbin.org/status/500?station=err_{i}")
    
    for i in range(5):
        example_urls.append(f"https://httpbin.org/status/404?station=notfound_{i}")
    
    for i in range(5):
        example_urls.append(f"https://nonexistent-domain-xyz-{i}.example.com/api/data")
    
    total_urls = len(example_urls)
    print(f"Fetching data from {total_urls} stations with max concurrency of 10...")
    print("=" * 70)
    
    start_time = time.time()
    results = fetch_all_stations(example_urls, max_concurrent=10)
    elapsed = time.time() - start_time
    
    readings = results["readings"]
    errors = results["errors"]
    
    print(f"\nResults Summary:")
    print(f"  Total stations:     {total_urls}")
    print(f"  Successful:         {len(readings)}")
    print(f"  Failed:             {len(errors)}")
    print(f"  Total elapsed time: {elapsed:.2f}s")
    print(f"  Avg time/station:   {elapsed / total_urls:.3f}s")
    
    if readings:
        print(f"\nFirst 3 successful readings:")
        for i, (url, data) in enumerate(list(readings.items())[:3]):
            data_str = json.dumps(data, indent=2)
            if len(data_str) > 200:
                data_str = data_str[:200] + "..."
            print(f"  [{i+1}] {url}")
            print(f"      {data_str}")
    
    if errors:
        print(f"\nFirst 5 errors:")
        for i, (url, error) in enumerate(list(errors.items())[:5]):
            print(f"  [{i+1}] {url}")
            print(f"      Error: {error}")
    
    print(f"\n{'=' * 70}")
    print(f"Done. Total time: {elapsed:.2f}s")
    
    return results


if __name__ == "__main__":
    main()