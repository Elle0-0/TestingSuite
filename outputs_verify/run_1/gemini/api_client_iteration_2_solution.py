import asyncio
import json
import aiohttp
from typing import Any

# Configuration
MAX_RETRIES = 3
INITIAL_DELAY = 1.0
CLIENT_TIMEOUT_SECONDS = 5

async def _fetch_station_data(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    """Helper function to fetch data for a single station with retry logic."""
    delay = INITIAL_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            timeout = aiohttp.ClientTimeout(total=CLIENT_TIMEOUT_SECONDS)
            async with session.get(url, timeout=timeout) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", str(int(delay))))
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = await response.json(content_type=None)
                return data

        except aiohttp.ClientResponseError as e:
            if 500 <= e.status < 600 and attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
                continue
            else:
                return {
                    "url": url,
                    "error_type": "Client Response Error",
                    "message": f"HTTP {e.status}: {e.message}",
                }
        except (asyncio.TimeoutError, aiohttp.ClientConnectorError) as e:
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            else:
                return {
                    "url": url,
                    "error_type": "Connection/Timeout Error",
                    "message": str(e.__class__.__name__),
                }
        except (json.JSONDecodeError, aiohttp.ContentTypeError) as e:
            return {
                "url": url,
                "error_type": "JSON Decode Error",
                "message": f"Could not decode JSON from response. Details: {e}",
            }
        except Exception as e:
            return {
                "url": url,
                "error_type": "Unhandled Exception",
                "message": f"{e.__class__.__name__}: {e}",
            }

    return {
        "url": url,
        "error_type": "Max Retries Exceeded",
        "message": f"Failed to fetch after {MAX_RETRIES} attempts.",
    }

async def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetches data from a list of station URLs concurrently.

    Args:
        urls: A list of URLs to fetch.

    Returns:
        A dictionary containing two keys:
        - "readings": A list of successfully fetched and parsed JSON data.
        - "errors": A list of dictionaries, each detailing a failed request.
    """
    readings = []
    errors = []
    async with aiohttp.ClientSession() as session:
        tasks = [_fetch_station_data(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

        for result in results:
            if result and "error_type" in result:
                errors.append(result)
            elif result:
                readings.append(result)

    return {"readings": readings, "errors": errors}

def main():
    """
    Demonstrates fetching data from multiple URLs, including simulated failures,
    and prints the successful readings and error reports.
    """
    # Use httpbin.org to reliably simulate different failure modes
    example_urls = [
        # 1. Success
        "https://api.weather.gov/stations/KNYC/observations/latest",
        # 2. Temporary Server Error (will be retried and then fail)
        "https://httpbin.org/status/503",
        # 3. Timeout (client timeout is 5s, httpbin waits 10s)
        "https://httpbin.org/delay/10",
        # 4. Malformed JSON (returns HTML instead of JSON)
        "https://httpbin.org/html",
        # 5. Rate Limit (will be retried after delay and then fail)
        "https://httpbin.org/status/429",
        # 6. Permanent Client Error (not found)
        "https://api.weather.gov/stations/THIS_IS_NOT_A_REAL_STATION/observations",
        # 7. Another success
        "https://api.weather.gov/stations/KLAX/observations/latest",
    ]

    print(f"Fetching data from {len(example_urls)} stations...")
    results = asyncio.run(fetch_all_stations(example_urls))
    
    print("\n--- Successful Readings ---")
    if results["readings"]:
        print(json.dumps(results["readings"], indent=2))
    else:
        print("No successful readings.")

    print("\n--- Error Reports ---")
    if results["errors"]:
        print(json.dumps(results["errors"], indent=2))
    else:
        print("No errors reported.")

if __name__ == "__main__":
    main()