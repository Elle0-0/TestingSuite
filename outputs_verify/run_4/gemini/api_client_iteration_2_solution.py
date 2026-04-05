import requests
import json
import time
from typing import List, Dict, Any, Tuple, Optional

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.5
REQUEST_TIMEOUT = 2
RETRYABLE_STATUSES = {500, 502, 503, 504}

def _fetch_with_retries(
    url: str, session: requests.Session
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            return data, None

        except requests.exceptions.HTTPError as e:
            last_exception = e
            status_code = e.response.status_code

            if status_code == 429:
                try:
                    wait_time = int(e.response.headers.get("Retry-After", 0))
                except (ValueError, TypeError):
                    wait_time = RETRY_BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(wait_time)
                continue

            if status_code in RETRYABLE_STATUSES:
                time.sleep(RETRY_BACKOFF_FACTOR * (2 ** attempt))
                continue

            return None, {
                "url": url,
                "error_type": "HTTPError",
                "message": f"Client or server error: {status_code} {e.response.reason}",
            }

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_exception = e
            time.sleep(RETRY_BACKOFF_FACTOR * (2 ** attempt))
            continue

        except json.JSONDecodeError as e:
            return None, {
                "url": url,
                "error_type": "JSONDecodeError",
                "message": f"Failed to parse JSON response: {e}",
            }
        
        except requests.exceptions.RequestException as e:
            last_exception = e
            time.sleep(RETRY_BACKOFF_FACTOR * (2 ** attempt))
            continue

    error_type = last_exception.__class__.__name__ if last_exception else "MaxRetriesExceeded"
    return None, {
        "url": url,
        "error_type": error_type,
        "message": f"Max retries exceeded for temporary issue. Last error: {last_exception}",
    }

def fetch_all_stations(urls: List[str]) -> Dict[str, List[Any]]:
    readings = []
    errors = []

    with requests.Session() as session:
        for url in urls:
            data, error_details = _fetch_with_retries(url, session)
            if data is not None:
                readings.append(data)
            elif error_details is not None:
                errors.append(error_details)
    
    return {"readings": readings, "errors": errors}

def main():
    BASE_URL = "https://httpbin.org"
    
    test_urls = [
        f"{BASE_URL}/json",
        f"{BASE_URL}/status/503",
        f"{BASE_URL}/delay/{REQUEST_TIMEOUT + 1}",
        f"{BASE_URL}/html",
        f"{BASE_URL}/status/429",
        f"{BASE_URL}/status/404",
        "http://this.is.not.a.real.domain/api",
        f"{BASE_URL}/get?source=second_success",
    ]

    results = fetch_all_stations(test_urls)

    print("--- Successful Readings ---")
    if results["readings"]:
        for i, reading in enumerate(results["readings"], 1):
            print(f"{i}: {reading}")
    else:
        print("No successful readings.")

    print("\n--- Error Reports ---")
    if results["errors"]:
        for i, error in enumerate(results["errors"], 1):
            print(f"{i}: URL: {error['url']}")
            print(f"   Type: {error['error_type']}")
            print(f"   Message: {error['message']}")
    else:
        print("No errors reported.")

if __name__ == "__main__":
    main()