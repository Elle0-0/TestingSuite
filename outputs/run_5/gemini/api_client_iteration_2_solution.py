import concurrent.futures
import json
import time
import pprint
import requests
from typing import Any, List, Dict

MAX_RETRIES = 3
REQUEST_TIMEOUT = 4
BASE_BACKOFF_FACTOR = 1

def _fetch_station_with_retries(url: str) -> Any:
    for attempt in range(MAX_RETRIES):
        try:
            with requests.Session() as session:
                response = session.get(url, timeout=REQUEST_TIMEOUT)

                if response.status_code == 429:
                    if attempt + 1 >= MAX_RETRIES:
                        response.raise_for_status()
                    
                    retry_after_header = response.headers.get("Retry-After")
                    wait_time = int(retry_after_header) if retry_after_header else BASE_BACKOFF_FACTOR * (2 ** attempt)
                    time.sleep(wait_time)
                    continue

                response.raise_for_status()
                return response.json()

        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600 and attempt + 1 < MAX_RETRIES:
                time.sleep(BASE_BACKOFF_FACTOR * (2 ** attempt))
                continue
            else:
                raise e

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt + 1 < MAX_RETRIES:
                time.sleep(BASE_BACKOFF_FACTOR * (2 ** attempt))
                continue
            else:
                raise e

        except json.JSONDecodeError as e:
            new_msg = f"Failed to decode JSON from {url}. Reason: {e.msg}"
            raise json.JSONDecodeError(new_msg, e.doc, e.pos) from e
    
    raise RuntimeError(f"Failed to fetch {url} after all retries.")

def _worker(url: str) -> dict:
    try:
        data = _fetch_station_with_retries(url)
        return {"status": "success", "data": data}
    except Exception as e:
        error_details = {
            "url": url,
            "error_type": type(e).__name__,
            "message": str(e),
        }
        return {"status": "error", "data": error_details}

def fetch_all_stations(urls: List[str]) -> Dict:
    """
    Fetches data from a list of station URLs concurrently, handling failures.

    Args:
        urls: A list of URL strings to fetch data from.

    Returns:
        A dictionary containing "readings" (a list of successful results)
        and "errors" (a list of dicts with failure details).
    """
    readings = []
    errors = []
    
    max_workers = min(len(urls), 32)
    if not max_workers:
        return {"readings": [], "errors": []}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(_worker, url): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if result["status"] == "success":
                readings.append(result["data"])
            else:
                errors.append(result["data"])
                
    return {"readings": readings, "errors": errors}

def main():
    """
    Demonstrates the solution with example URLs including some that simulate failures.
    """
    example_urls = [
        "https://httpbin.org/json",
        "https://httpbin.org/status/503",
        f"https://httpbin.org/delay/{REQUEST_TIMEOUT + 1}",
        "https://httpbin.org/html",
        "https://httpbin.org/status/404",
        "https://httpbin.org/get?station_id=101",
        "http://this-is-not-a-real-domain.invalid/",
        "https://httpbin.org/status/429",
    ]

    print("Fetching data from stations...")
    results = fetch_all_stations(example_urls)
    print("\n--- Processing Complete ---")

    print("\n✅ Successful Readings:")
    if results["readings"]:
        pprint.pprint(results["readings"])
    else:
        print("None")

    print("\n❌ Error Reports:")
    if results["errors"]:
        sorted_errors = sorted(results["errors"], key=lambda x: x['url'])
        pprint.pprint(sorted_errors)
    else:
        print("None")

if __name__ == "__main__":
    main()