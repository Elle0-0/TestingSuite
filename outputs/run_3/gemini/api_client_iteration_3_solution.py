import asyncio
import time
import json
from typing import Any, Coroutine

import aiohttp

def _process_reading(reading: dict) -> dict:
    """Processes a single reading, converting temperature and adding status."""
    celsius = reading.get("temperature", 0.0)
    if celsius < -5:
        status = "ice"
    elif -5 <= celsius < 0:
        status = "snow"
    elif 0 <= celsius < 10:
        status = "cold"
    elif 10 <= celsius < 20:
        status = "moderate"
    else:
        status = "hot"

    return {
        "station_id": reading.get("station_id"),
        "temperature_celsius": celsius,
        "temperature_fahrenheit": (celsius * 9/5) + 32,
        "status": status,
        "timestamp": reading.get("timestamp"),
    }

async def _fetch_single_station(
    session: aiohttp.ClientSession, url: str, retries: int = 3, delay: float = 1.0
) -> dict | str:
    """
    Fetches and processes data for a single station asynchronously with retries.
    Returns processed data on success or an error string on failure.
    """
    last_exception = None
    for attempt in range(retries):
        try:
            async with session.get(url, timeout=5.0) as response:
                response.raise_for_status()
                data = await response.json()

                if data.get("service") == "unavailable":
                    raise aiohttp.ClientError("Service temporarily unavailable")

                return _process_reading(data)
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            last_exception = e
            if attempt < retries - 1:
                await asyncio.sleep(delay * (2**attempt))
            else:
                return f"Failed after {retries} attempts: {type(e).__name__}"
    # This line should not be reachable if logic is correct, but acts as a safeguard.
    return f"Failed after {retries} attempts. Last error: {last_exception}"

async def _fetch_and_process_url(
    session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, url: str
) -> tuple[str, dict | str]:
    """Acquires semaphore, fetches data, and returns url-result pair."""
    async with semaphore:
        result = await _fetch_single_station(session, url)
        return (url, result)

async def _fetch_all_stations_async(
    urls: list[str], max_concurrent: int = 10
) -> dict:
    """Asynchronous implementation to fetch data from all stations concurrently."""
    readings = {}
    errors = {}
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async with aiohttp.ClientSession() as session:
        tasks: list[Coroutine[Any, Any, tuple[str, dict[Any, Any] | str]]] = [
            _fetch_and_process_url(session, semaphore, url) for url in urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, res in enumerate(results):
        url = urls[i]
        if isinstance(res, Exception):
            errors[url] = f"Unhandled exception: {type(res).__name__}"
        else:
            _, data = res
            if isinstance(data, dict):
                readings[url] = data
            else:
                errors[url] = str(data)

    return {"readings": readings, "errors": errors}

def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Public-facing synchronous wrapper for the async implementation.
    """
    return asyncio.run(_fetch_all_stations_async(urls, max_concurrent))

def main() -> None:
    """Demonstrates the concurrent solution with example URLs."""
    # In a real scenario, these would be actual URLs.
    # We use a file-based mock server or placeholders for demonstration.
    # For this example, we assume a local server is running.
    # To simulate, one can run `python -m http.server 8000` in a directory
    # with JSON files named station_001.json, station_002.json, etc.
    base_url = "http://localhost:8000/station_{:03d}.json"
    
    # Create some representative JSON files for testing:
    # station_001.json: {"station_id": 1, "temperature": 15.5, "timestamp": "..."}
    # station_002.json: {"station_id": 2, "temperature": -10.0, "timestamp": "..."}
    # station_003.json: (invalid json) "{"
    # station_004.json: {"service": "unavailable"}
    # station_999.json: (does not exist, will cause 404)
    
    urls = (
        [base_url.format(i) for i in range(1, 51)] +
        [base_url.format(999)] + # A non-existent station
        ["http://localhost:8000/station_003.json"] + # Invalid JSON
        ["http://localhost:8000/station_004.json"] # Service unavailable
    )

    print(f"Fetching data from {len(urls)} stations concurrently...")
    start_time = time.perf_counter()

    # The synchronous public function is called here
    results = fetch_all_stations(urls, max_concurrent=20)
    
    end_time = time.perf_counter()

    print("\n--- Summary ---")
    print(f"Total stations processed: {len(urls)}")
    print(f"Successful readings: {len(results.get('readings', {}))}")
    print(f"Failed attempts: {len(results.get('errors', {}))}")
    print(f"Total elapsed time: {end_time - start_time:.2f} seconds")
    
    print("\n--- Successful Readings (first 5) ---")
    for i, (url, data) in enumerate(results.get("readings", {}).items()):
        if i >= 5:
            break
        print(f"{url}: {data}")

    print("\n--- Errors ---")
    if not results.get("errors"):
        print("No errors.")
    else:
        for url, error in results.get("errors", {}).items():
            print(f"{url}: {error}")

if __name__ == "__main__":
    # Create dummy files for local testing
    # This setup allows the main() function to run without a live web server
    # if you run this script directly.
    import os
    if not os.path.exists("station_001.json"):
        print("Creating dummy station data files for demonstration...")
        for i in range(1, 51):
            with open(f"station_{i:03d}.json", "w") as f:
                temp = (i * 1.5) - 20 # Range of temperatures
                f.write(json.dumps({
                    "station_id": i,
                    "temperature": temp,
                    "timestamp": "2023-01-01T12:00:00Z"
                }))
        with open("station_003.json", "w") as f: # Overwrite 003 with invalid json
            f.write('{"station_id": 3, "temperature": 5.0, "timestamp": "..."')
        with open("station_004.json", "w") as f: # Overwrite 004 with service error
            f.write('{"service": "unavailable"}')

    main()