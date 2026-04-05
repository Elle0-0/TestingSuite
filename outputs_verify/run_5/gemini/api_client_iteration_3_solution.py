import asyncio
import time
import pprint
import aiohttp
from typing import Any, Coroutine

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds
REQUEST_TIMEOUT = 5  # seconds

async def _fetch_one_station(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
) -> dict:
    """Fetches data for a single station with retries."""
    last_exception = None
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=REQUEST_TIMEOUT) as response:
                    response.raise_for_status()
                    return await response.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
    raise ConnectionError(f"Failed to fetch {url} after {MAX_RETRIES} attempts") from last_exception

async def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetches data from a list of station URLs concurrently.
    """
    results = {"readings": [], "errors": []}
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession() as session:
        tasks: list[Coroutine[Any, Any, dict]] = [
            _fetch_one_station(session, url, semaphore) for url in urls
        ]
        
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(task_results):
            if isinstance(result, Exception):
                error_message = f"URL: {urls[i]} | Error: {type(result).__name__}: {result}"
                results["errors"].append(error_message)
            else:
                results["readings"].append(result)
                
    return results

async def main() -> None:
    """
    Demonstrates the concurrent fetching of station data and reports results.
    """
    base_url = "https://raw.githubusercontent.com/grid-tools/static-data/main/api-client-test-data/stations"
    
    # A larger list of URLs, including duplicates and invalid ones
    station_ids = list(range(1, 21)) * 2  # 40 stations
    urls = [f"{base_url}/{i}.json" for i in station_ids]
    
    # Add some known bad URLs
    urls.extend([
        f"{base_url}/999.json",  # Not Found
        "http://httpbin.org/delay/10", # Will timeout
        "https://invalid.domain/data.json" # Will fail to connect
    ])
    
    print(f"Fetching data for {len(urls)} stations...")
    start_time = time.monotonic()
    
    results = await fetch_all_stations(urls, max_concurrent=15)
    
    end_time = time.monotonic()
    elapsed_time = end_time - start_time
    
    print("\n--- Summary ---")
    print(f"Successful readings: {len(results['readings'])}")
    print(f"Failed attempts:     {len(results['errors'])}")
    
    print("\n--- Errors ---")
    if results['errors']:
        for error in results['errors']:
            print(error)
    else:
        print("No errors.")
        
    # Optionally print a small sample of readings to verify
    print("\n--- Sample of Readings (first 5) ---")
    pprint.pprint(results['readings'][:5])

    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main())