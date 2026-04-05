import asyncio
import time
import json
import aiohttp
from typing import Any

MAX_RETRIES = 2  # Results in 3 total attempts
RETRY_DELAY = 1  # In seconds


def get_station_id(url: str) -> str:
    """Extracts the station ID from a URL."""
    try:
        return url.split("/stations/")[1].split("/")[0]
    except IndexError:
        return url


async def fetch_station_data(
    session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore
) -> tuple[str, dict[str, Any] | str]:
    """
    Fetches data for a single station with retries and concurrency limiting.
    """
    station_id = get_station_id(url)
    last_error_message = "Unknown error"

    async with semaphore:
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with session.get(url, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "properties" not in data:
                            last_error_message = "Malformed response: missing 'properties'"
                            continue # Potentially retry a malformed but successful response
                        return station_id, data["properties"]

                    # Do not retry on client-side errors indicating a permanent issue
                    if response.status in (403, 404, 429):
                        return station_id, f"Service error: HTTP {response.status}"

                    last_error_message = f"HTTP {response.status}"

            except aiohttp.ClientConnectorError:
                last_error_message = "Network error: Connection failed"
            except aiohttp.ClientError as e:
                last_error_message = f"Network error: {type(e).__name__}"
            except asyncio.TimeoutError:
                last_error_message = "Network error: Request timed out"
            except json.JSONDecodeError:
                last_error_message = "Invalid JSON in response"

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)

    return station_id, f"Failed after {MAX_RETRIES + 1} attempts: {last_error_message}"


async def fetch_all_stations(
    urls: list[str], max_concurrent: int = 10
) -> dict[str, Any]:
    """
    Fetches data from a list of station URLs concurrently.
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    final_report: dict[str, Any] = {"readings": {}, "errors": {}}

    async with aiohttp.ClientSession(
        headers={"User-Agent": "Python Weather Client/3.0"}
    ) as session:
        tasks = [fetch_station_data(session, url, semaphore) for url in urls]
        results = await asyncio.gather(*tasks)

    for station_id, result in results:
        if isinstance(result, dict):
            final_report["readings"][station_id] = result
        else:
            final_report["errors"][station_id] = str(result)

    return final_report


async def main() -> None:
    """
    Demonstrates the concurrent station data fetching solution.
    """
    BASE_URL = "https://api.weather.gov/stations/{}/observations/latest"
    STATIONS = [
        "KNYC", "KLAX", "KORD", "KDCA", "KSFO", "KEWR", "KJFK", "KBOS",
        "KSEA", "KDEN", "KATL", "KDFW", "KMIA", "KIAD", "KPHX", "KLAS",
        "KSTL", "KMSP", "KDTW", "KCLT", "KPHL", "KBWI", "KSAN", "KTPA",
        "KPDX", "KHOU", "KDAL", "KMDW", "KLGA", "KBDL", "KCLE", "KMCI",
        "PANC", "PHNL", "KIND", "KSLC", "KCVG", "KSMF", "KSJC", "KOAK",
        "KBUR", "KLGB", "KONT", "KSNA", "KABQ", "KBNA", "KRDU", "KMCO",
        "KFLL", "KPIT", "KCMH", "KMEM", "KOKC", "KSAT", "KELP", "KOMA",
        "KBUF", "KALB", "KSYR", "KROC", "KRIC", "KORF", "KGSO", "KCHS",
        "KSAV", "KJAX", "KRSW", "KMSY", "KJAN", "KLIT", "KSHV", "KTUL",
        "KWIC", "KDSM", "KFSD", "KFAR", "KBIL", "KBOI", "KGEG", "KRNO",
        # Intentionally invalid/problematic stations
        "EGLL",      # Invalid for this API (London)
        "INVALID",   # Malformed station ID
        "KZZZ",      # Guaranteed 404
        "http://baddomain.invalid/test", # Connection Error
    ]

    urls = [BASE_URL.format(s) if "http" not in s else s for s in STATIONS]

    print(f"Fetching data for {len(urls)} stations...")
    start_time = time.monotonic()

    results = await fetch_all_stations(urls, max_concurrent=20)

    end_time = time.monotonic()
    elapsed_time = end_time - start_time

    print("\n--- Successful Readings ---")
    for station, data in results["readings"].items():
        temp_info = data.get("temperature", {}).get("value")
        temp_str = f"{temp_info}°C" if temp_info is not None else "N/A"
        print(f"  {station}: {temp_str}")

    print("\n--- Errors ---")
    for station, error_message in results["errors"].items():
        print(f"  {station}: {error_message}")

    print("\n--- Summary ---")
    print(f"Total stations:      {len(urls)}")
    print(f"Successful readings: {len(results['readings'])}")
    print(f"Failed attempts:     {len(results['errors'])}")
    print(f"Total elapsed time:  {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())