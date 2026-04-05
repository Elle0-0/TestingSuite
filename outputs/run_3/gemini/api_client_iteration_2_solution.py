import requests
import time
import json
from pprint import pprint

MAX_RETRIES = 3
REQUEST_TIMEOUT = 5  # seconds
BACKOFF_FACTOR = 1   # seconds

def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetches data from a list of URLs with retries and error handling.
    """
    readings = []
    errors = []

    for url in urls:
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, timeout=REQUEST_TIMEOUT)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "1"))
                    last_exception = requests.exceptions.HTTPError(
                        f"Rate limit exceeded. Waiting for {retry_after}s."
                    )
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()

                data = response.json()
                readings.append(data)
                last_exception = None
                break

            except requests.exceptions.HTTPError as e:
                last_exception = e
                if 400 <= response.status_code < 500:
                    break  # Don't retry client errors (e.g., 404)
                
                # Retry on server errors (5xx)
                wait_time = BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(wait_time)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                wait_time = BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(wait_time)

            except json.JSONDecodeError as e:
                last_exception = e
                break  # Don't retry malformed JSON

        if last_exception:
            error_report = {
                "url": url,
                "error_type": type(last_exception).__name__,
                "message": str(last_exception),
            }
            errors.append(error_report)

    return {"readings": readings, "errors": errors}

def main():
    """
    Demonstrates the solution with example URLs and prints the results.
    """
    # Using httpbin.org to simulate different scenarios
    example_urls = [
        "https://httpbin.org/json",  # Success
        "https://httpbin.org/status/503",  # Temporary server error
        "https://httpbin.org/delay/10",  # Timeout
        "https://httpbin.org/html",  # Malformed JSON
        "https://httpbin.org/status/404",  # Not found (permanent error)
        "http://non-existent-domain.xyz", # Connection error
        "https://httpbin.org/status/429", # Rate limit (simulated)
    ]

    print("Fetching station data...")
    results = fetch_all_stations(example_urls)
    print("\n--- Successful Readings ---")
    pprint(results["readings"])
    print("\n--- Error Reports ---")
    pprint(results["errors"])

if __name__ == "__main__":
    main()