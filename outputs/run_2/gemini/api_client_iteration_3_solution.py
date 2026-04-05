import asyncio
import time
from pprint import pprint
from typing import Any, Coroutine

import aiohttp

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1
REQUEST_TIMEOUT_SECONDS = 5

async def _fetch_one(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
) -> dict[str, Any]:
    """Fetches a single URL with retries and concurrency limiting."""
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status >= 500:
                        # Server error, worth retrying
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                        continue
                    else:
                        # Client error (4xx) or other non-retriable status
                        response.raise_for_status()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt >= MAX_RETRIES - 1:
                    raise e  # Raise the last exception after all retries fail
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
        
        # This line is reached if all retries on server errors fail
        raise aiohttp.ClientError(f"All {MAX_RETRIES} retries failed for {url}")


async def _run_concurrent_fetches(
    urls: list[str], max_concurrent: int
) -> dict[str, list]:
    """The asynchronous orchestrator for fetching all URLs."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, list] = {"readings": [], "errors": []}
    
    async with aiohttp.ClientSession() as session:
        tasks: list[Coroutine] = [
            _fetch_one(session, url, semaphore) for url in urls
        ]
        
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        for url, result in zip(urls, task_results):
            if isinstance(result, Exception):
                results["errors"].append(url)
            else:
                results["readings"].append(result)
                
    return results


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict[str, list]:
    """
    Fetches data from a list of station URLs concurrently.

    Args:
        urls: A list of URLs to fetch data from.
        max_concurrent: The maximum number of concurrent requests.

    Returns:
        A dictionary with two keys:
        - "readings": A list of successfully fetched and parsed JSON data.
        - "errors": A list of URLs that failed after all retries.
    """
    return asyncio.run(_run_concurrent_fetches(urls, max_concurrent))


def main() -> None:
    """
    Demonstrates the concurrent fetching of station data and reports results.
    """
    # A large list of URLs for demonstration, including valid, slow, and error-prone ones.
    locations = {
        "berlin": "latitude=52.52&longitude=13.41",
        "tokyo": "latitude=35.6895&longitude=139.6917",
        "new_york": "latitude=40.7128&longitude=-74.0060",
        "sydney": "latitude=-33.8688&longitude=151.2093",
        "cairo": "latitude=30.0444&longitude=31.2357",
        "beijing": "latitude=39.9042&longitude=116.4074",
        "moscow": "latitude=55.7558&longitude=37.6173",
        "rio": "latitude=-22.9068&longitude=-43.1729",
        "london": "latitude=51.5074&longitude=-0.1278",
        "los_angeles": "latitude=34.0522&longitude=-118.2437",
    }
    
    base_api_url = "https://api.open-meteo.com/v1/forecast?current_weather=true&"
    
    # Generate 50 valid URLs
    urls = [
        f"{base_api_url}{loc_params}"
        for _, loc_params in locations.items()
        for _ in range(5)
    ]
    
    # Add some URLs that are expected to fail
    urls.extend([
        "https://api.open-meteo.com/v1/invalid-endpoint",  # Will 404
        "http://httpstat.us/503",  # Simulates a server error (retriable)
        "http://httpstat.us/504",  # Simulates a gateway timeout (retriable)
        "http://non-existent-domain-12345.com/api/data",  # DNS error
        "https://api.open-meteo.com/v1/forecast?latitude=200&longitude=200", # Invalid input
    ])

    print(f"Fetching data from {len(urls)} stations with max {15} concurrent workers...")
    
    start_time = time.perf_counter()
    results = fetch_all_stations(urls, max_concurrent=15)
    end_time = time.perf_counter()

    print("\n--- Fetching Complete ---")
    print(f"Total elapsed time: {end_time - start_time:.2f} seconds")
    
    print("\n--- Summary ---")
    print(f"Successful readings: {len(results['readings'])}")
    print(f"Failed URLs: {len(results['errors'])}")

    if results['errors']:
        print("\n--- Failed URLs ---")
        for url in results['errors']:
            print(url)
            
    if results['readings']:
        print("\n--- Sample of Successful Readings ---")
        # Print up to 3 samples
        for reading in results['readings'][:3]:
            pprint(reading.get("current_weather", "No 'current_weather' key found"))


if __name__ == "__main__":
    main()