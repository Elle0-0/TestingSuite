import requests
import time
import json
from pprint import pprint
from typing import Optional, Any, Tuple, Dict, List

MAX_RETRIES = 3
BACKOFF_FACTOR = 0.5
REQUEST_TIMEOUT = 2  # seconds


def _fetch_station_data(
    url: str, session: requests.Session
) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Fetches data for a single station with retries for temporary errors.

    Returns a tuple (data, error). One of the two will be None.
    """
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 429:
                # Respect Retry-After header if present
                retry_after = int(response.headers.get("Retry-After", "1"))
                message = f"Rate limited (429). Retrying after {retry_after}s."
                last_exception = requests.exceptions.HTTPError(message, response=response)
                time.sleep(retry_after)
                continue

            response.raise_for_status()

            data = response.json()
            return data, None

        except requests.exceptions.Timeout as e:
            last_exception = e
            wait_time = BACKOFF_FACTOR * (2 ** attempt)
            time.sleep(wait_time)
            continue
        except requests.exceptions.HTTPError as e:
            last_exception = e
            if 500 <= e.response.status_code < 600:
                # Retry on 5xx server errors
                wait_time = BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(wait_time)
                continue
            else:
                # Non-retriable client error (e.g., 404)
                error_report = {
                    "url": url,
                    "error_type": "HTTPError",
                    "message": str(e),
                }
                return None, error_report
        except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
            # Non-retriable network errors
            last_exception = e
            break  # Exit retry loop
        except json.JSONDecodeError as e:
            # Non-retriable malformed JSON
            error_report = {
                "url": url,
                "error_type": "JSONDecodeError",
                "message": f"Failed to decode JSON: {str(e)}",
            }
            return None, error_report

    # If all retries failed
    final_error_report = {
        "url": url,
        "error_type": type(last_exception).__name__,
        "message": str(last_exception),
    }
    return None, final_error_report


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetches data from a list of station URLs, handling failures and retries.

    Args:
        urls: A list of URL strings to fetch data from.

    Returns:
        A dictionary with two keys:
        - "readings": A list of successfully fetched and parsed station data.
        - "errors": A list of dictionaries detailing the failures.
    """
    readings = []
    errors = []

    with requests.Session() as session:
        for url in urls:
            data, error = _fetch_station_data(url, session)
            if data is not None:
                readings.append(data)
            if error is not None:
                errors.append(error)

    return {"readings": readings, "errors": errors}


def main():
    """
    Demonstrates the solution with example URLs simulating various failures.
    """
    # Using httpbin.org to simulate various HTTP scenarios
    SAMPLE_URLS = [
        # A successful request
        "https://httpbin.org/json",
        # A successful request to a different endpoint
        "https://httpbin.org/get?station=alpha",
        # This will time out (delay is > REQUEST_TIMEOUT)
        "https://httpbin.org/delay/3",
        # This will return a 503 Server Error, which is retriable
        "https://httpbin.org/status/503",
        # This will return a 429 Rate Limit error, which is retriable
        "https://httpbin.org/status/429",
        # This returns HTML, which will cause a JSONDecodeError
        "https://httpbin.org/html",
        # This URL does not exist and will cause a 404 Not Found error
        "https://httpbin.org/status/404",
        # Invalid URL format
        "https://httpbin.org/invalid-url-that-will-fail",
        # Another successful request
        "https://httpbin.org/get?station=beta"
    ]

    print(f"Fetching data from {len(SAMPLE_URLS)} stations...")
    results = fetch_all_stations(SAMPLE_URLS)

    print("\n--- Successfully fetched readings ---")
    pprint(results["readings"])

    print("\n--- Failed requests ---")
    pprint(results["errors"])


if __name__ == "__main__":
    main()