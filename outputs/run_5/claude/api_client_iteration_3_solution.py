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
                    last_exception = Exception(f"HTTP 429: Rate limited (attempt {attempt + 1})")
                    continue
                elif response.status >= 500:
                    # Server error - retry with backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(f"HTTP {response.status}: Server error (attempt {attempt + 1})")
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
            last_exception = Exception(f"Timeout after {timeout}s (attempt {attempt + 1})")
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
) -> dict:
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


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetch data from multiple station URLs concurrently.
    
    Args:
        urls: List of station API URLs to fetch
        max_concurrent: Maximum number of concurrent requests
    
    Returns:
        dict with "readings" (successful responses) and "errors" (failed requests)
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
                asyncio.run, _fetch_all_stations_async(urls, max_concurrent)
            )
            return future.result()
    else:
        return asyncio.run(_fetch_all_stations_async(urls, max_concurrent))


def main():
    """Demonstrate the concurrent station fetching with a large list of URLs."""
    # Generate a large list of example URLs simulating many weather stations
    base_urls = [
        "https://api.weather.gov/stations/KJFK/observations/latest",
        "https://api.weather.gov/stations/KLAX/observations/latest",
        "https://api.weather.gov/stations/KORD/observations/latest",
        "https://api.weather.gov/stations/KATL/observations/latest",
        "https://api.weather.gov/stations/KDFW/observations/latest",
        "https://api.weather.gov/stations/KDEN/observations/latest",
        "https://api.weather.gov/stations/KSFO/observations/latest",
        "https://api.weather.gov/stations/KSEA/observations/latest",
        "https://api.weather.gov/stations/KMIA/observations/latest",
        "https://api.weather.gov/stations/KBOS/observations/latest",
        "https://api.weather.gov/stations/KPHX/observations/latest",
        "https://api.weather.gov/stations/KMSP/observations/latest",
        "https://api.weather.gov/stations/KDTW/observations/latest",
        "https://api.weather.gov/stations/KPHL/observations/latest",
        "https://api.weather.gov/stations/KIAH/observations/latest",
        "https://api.weather.gov/stations/KMCO/observations/latest",
        "https://api.weather.gov/stations/KBWI/observations/latest",
        "https://api.weather.gov/stations/KSLC/observations/latest",
        "https://api.weather.gov/stations/KPDX/observations/latest",
        "https://api.weather.gov/stations/KCLT/observations/latest",
    ]
    
    # Include some intentionally bad URLs to demonstrate error handling
    bad_urls = [
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/404",
        "https://nonexistent.invalid/api/data",
        "https://httpbin.org/delay/30",  # Will timeout
    ]
    
    # Create a larger set by repeating and mixing
    urls = base_urls + bad_urls
    
    print(f"Fetching data from {len(urls)} stations concurrently...")
    print(f"Max concurrent requests: 10")
    print("-" * 60)
    
    start_time = time.time()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.time() - start_time
    
    readings = results["readings"]
    errors = results["errors"]
    
    print(f"\nResults Summary:")
    print(f"  Total stations: {len(urls)}")
    print(f"  Successful:     {len(readings)}")
    print(f"  Failed:         {len(errors)}")
    print(f"  Total time:     {elapsed:.2f}s")
    print(f"  Avg per station: {elapsed / len(urls):.3f}s (concurrent)")
    print(f"  Estimated sequential time: ~{len(urls) * 2:.0f}s+ (at ~2s each)")
    
    if readings:
        print(f"\nSuccessful readings ({len(readings)}):")
        for url in sorted(readings.keys()):
            data = readings[url]
            # Try to extract station identifier from URL
            station = url.split("/stations/")[1].split("/")[0] if "/stations/" in url else url
            if isinstance(data, dict):
                props = data.get("properties", {})
                temp = props.get("temperature", {})
                temp_val = temp.get("value") if isinstance(temp, dict) else None
                desc = props.get("textDescription", "N/A")
                if temp_val is not None:
                    print(f"    {station}: {temp_val}°C - {desc}")
                else:
                    print(f"    {station}: (data retrieved, temp not available)")
            else:
                print(f"    {station}: {str(data)[:80]}")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for url, error in sorted(errors.items()):
            short_url = url if len(url) <= 60 else url[:57] + "..."
            print(f"    {short_url}: {error[:100]}")
    
    print(f"\nDone in {elapsed:.2f}s")
    return results


if __name__ == "__main__":
    main()