import asyncio
import time
import json
from typing import Any

# Note: This solution requires the 'aiohttp' library.
# Install it using: pip install aiohttp
import aiohttp

def _parse_and_validate(json_data: dict, url: str) -> dict:
    required_keys = {
        "station_id": int, "s_no": int, "ms_no": int, "last_updated": int,
        "last_reported": int, "num_bikes_available": int, "num_docks_available": int,
        "is_installed": int, "is_renting": int, "is_returning": int,
    }

    if not isinstance(json_data, dict):
        raise ValueError("Response is not a JSON object")

    data = json_data.get("data")
    if not isinstance(data, dict):
        raise ValueError("Missing 'data' key in response")

    stations = data.get("stations")
    if not isinstance(stations, list) or not stations:
        raise ValueError("Missing or empty 'stations' list in response")

    station_data = stations[0]
    if not isinstance(station_data, dict):
        raise ValueError("Station data is not a valid object")

    for key, expected_type in required_keys.items():
        if key not in station_data:
            raise ValueError(f"Missing required key: {key}")
        if not isinstance(station_data[key], expected_type):
            raise TypeError(f"Key '{key}' has incorrect type. "
                            f"Expected {expected_type.__name__}, "
                            f"got {type(station_data[key]).__name__}")

    return station_data

async def _fetch_one_station(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
    retries: int = 3,
    delay: float = 1.0,
    timeout: int = 10
) -> tuple[str, Any]:
    last_exception = None
    async with semaphore:
        for attempt in range(retries):
            try:
                async with session.get(url, timeout=timeout) as response:
                    response.raise_for_status()
                    json_data = await response.json()
                    parsed_data = _parse_and_validate(json_data, url)
                    return (url, parsed_data)
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, ValueError, TypeError) as e:
                last_exception = e
                if attempt < retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))
                else:
                    error_message = f"{type(e).__name__}: {e}"
                    return (url, error_message)
    return (url, f"Unknown error after {retries} retries")

def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    async def _run_concurrently():
        semaphore = asyncio.Semaphore(max_concurrent)
        async with aiohttp.ClientSession() as session:
            tasks = [_fetch_one_station(session, semaphore, url) for url in urls]
            results = await asyncio.gather(*tasks)
        return results

    all_results = asyncio.run(_run_concurrently())

    final_report = {"readings": {}, "errors": {}}
    for url, result in all_results:
        if isinstance(result, dict):
            station_id = str(result["station_id"])
            final_report["readings"][station_id] = result
        else:
            final_report["errors"][url] = str(result)
            
    return final_report

def main():
    # A large list of example URLs, including some that are intentionally invalid
    # or will time out to demonstrate robustness.
    # The base URL points to a real, but unofficial, Citibike API endpoint.
    base_url = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json?station_id="
    station_ids = [
        "72", "79", "82", "83", "116", "119", "120", "127", "128", "143", "144",
        "146", "147", "150", "151", "152", "153", "157", "161", "164", "167",
        "168", "173", "174", "195", "212", "216", "217", "218", "223", "224",
        "225", "228", "229", "232", "233", "236", "237", "238", "239", "241",
        "242", "243", "244", "245", "247", "248", "249", "250", "251", "252",
        "253", "254", "257", "258", "259", "260", "261", "262", "263", "264",
        "265", "266", "267", "268", "270", "271", "274", "275", "276", "278",
        "999999", # Invalid station ID
        "http://httpbin.org/delay/15", # Will time out
        "http://invalid.url/data.json", # Will fail to connect
        "http://httpbin.org/status/500", # Server error
        "http://httpbin.org/html", # Not JSON
    ]
    urls = [f"{base_url}{sid}" if sid.isdigit() else sid for sid in station_ids]

    print(f"Fetching data for {len(urls)} stations...")
    start_time = time.perf_counter()

    results = fetch_all_stations(urls, max_concurrent=20)

    end_time = time.perf_counter()
    elapsed_time = end_time - start_time

    print("\n--- Fetched Readings ---")
    for station_id, data in results["readings"].items():
        print(f"Station {station_id}: {data['num_bikes_available']} bikes, "
              f"{data['num_docks_available']} docks")

    print("\n--- Errors ---")
    if not results["errors"]:
        print("No errors.")
    else:
        for url, error in results["errors"].items():
            print(f"URL: {url}\n  Error: {error}")

    print(f"\nSuccessfully fetched: {len(results['readings'])} stations")
    print(f"Failed to fetch: {len(results['errors'])} stations")
    print(f"Total execution time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()