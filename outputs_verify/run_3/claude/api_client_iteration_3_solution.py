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
    """Fetch a single station, respecting concurrency limits via semaphore."""
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
                # Unexpected exception that escaped our error handling
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
        # We're already in an async context; create a new thread
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
    # Using httpbin.org and similar test endpoints for demonstration
    base_urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/status/200",
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        "https://jsonplaceholder.typicode.com/posts/3",
    ]
    
    # Create a larger set by varying parameters
    urls = []
    for i in range(1, 51):
        urls.append(f"https://jsonplaceholder.typicode.com/posts/{i}")
    
    # Add some URLs that will likely fail to demonstrate error handling
    urls.extend([
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/404",
        "https://nonexistent.example.invalid/data",
        "https://httpbin.org/delay/30",  # Will likely timeout
    ])
    
    print(f"Fetching data from {len(urls)} stations...")
    print(f"Max concurrent requests: 10")
    print("-" * 60)
    
    start_time = time.time()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.time() - start_time
    
    successful = results["readings"]
    failed = results["errors"]
    
    print(f"\nResults Summary:")
    print(f"  Total stations:     {len(urls)}")
    print(f"  Successful:         {len(successful)}")
    print(f"  Failed:             {len(failed)}")
    print(f"  Total elapsed time: {elapsed:.2f}s")
    print(f"  Avg time/station:   {elapsed / len(urls):.3f}s")
    print()
    
    # Show a few successful readings
    print("Sample successful readings:")
    for url in list(successful.keys())[:3]:
        data = successful[url]
        preview = json.dumps(data, indent=None)[:100]
        print(f"  {url}")
        print(f"    -> {preview}...")
    
    # Show all errors
    if failed:
        print(f"\nErrors ({len(failed)}):")
        for url, error in failed.items():
            print(f"  {url}")
            print(f"    -> {error}")


if __name__ == "__main__":
    main()