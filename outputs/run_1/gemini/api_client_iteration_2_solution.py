import requests
import time
import json
from typing import List, Dict, Any

# --- Constants ---
MAX_RETRIES = 3
# Timeout for the initial connection and for receiving data
REQUEST_TIMEOUT = 5  # seconds
# Backoff factor for retries (e.g., 0.5s, 1s, 2s for attempts 1, 2, 3)
BACKOFF_FACTOR = 0.5  # seconds

def fetch_all_stations(urls: List[str]) -> Dict[str, List[Any]]:
    """
    Fetches data from a list of URLs with retry and error handling.

    Args:
        urls: A list of string URLs to fetch data from.

    Returns:
        A dictionary containing "readings" (a list of successful JSON
        payloads) and "errors" (a list of dictionaries detailing failures).
    """
    readings = []
    errors = []
    
    with requests.Session() as session:
        for url in urls:
            last_error_message = "Unknown error"
            for attempt in range(MAX_RETRIES):
                try:
                    response = session.get(url, timeout=REQUEST_TIMEOUT)

                    # 1. Handle rate limiting (429)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get("Retry-After", 1))
                        last_error_message = f"Rate limited. Waiting {retry_after}s."
                        time.sleep(retry_after)
                        continue

                    # 2. Handle temporary server errors (5xx)
                    if response.status_code >= 500:
                        sleep_time = BACKOFF_FACTOR * (2 ** attempt)
                        last_error_message = f"Server error ({response.status_code}). Retrying in {sleep_time:.2f}s."
                        time.sleep(sleep_time)
                        continue

                    # 3. Handle permanent client errors (4xx, but not 429)
                    if 400 <= response.status_code < 500:
                        errors.append({
                            "url": url,
                            "error_type": "ClientError",
                            "message": f"HTTP {response.status_code}: {response.reason}"
                        })
                        break  # Do not retry client errors

                    # 4. Handle success (200)
                    response.raise_for_status()  # Should be 200 at this point

                    try:
                        data = response.json()
                        readings.append(data)
                    except json.JSONDecodeError as e:
                        errors.append({
                            "url": url,
                            "error_type": "JSONDecodeError",
                            "message": str(e)
                        })
                    break  # Break on success or JSON error, no more retries needed

                except requests.exceptions.Timeout as e:
                    last_error_message = f"Request timed out: {e}"
                    sleep_time = BACKOFF_FACTOR * (2 ** attempt)
                    time.sleep(sleep_time)
                    # Continue to next retry attempt

                except requests.exceptions.RequestException as e:
                    # For other connection/DNS errors, treat as permanent failure
                    errors.append({
                        "url": url,
                        "error_type": "RequestException",
                        "message": str(e)
                    })
                    break  # Do not retry fundamental connection problems
            
            else:  # This 'else' belongs to the 'for' loop
                   # It executes if the loop completes without a 'break'
                errors.append({
                    "url": url,
                    "error_type": "MaxRetriesExceeded",
                    "message": f"Failed after {MAX_RETRIES} attempts. Last error: {last_error_message}"
                })

    return {"readings": readings, "errors": errors}

def main():
    """
    Demonstrates the fetch_all_stations function with example URLs
    and prints the successful readings and error reports.
    """
    urls_to_fetch = [
        # A successful request
        "https://api.weather.gov/stations/KNYC/observations/latest",
        # Another successful request
        "https://api.weather.gov/stations/KLAX/observations/latest",
        # This will result in a 404 Not Found client error
        "https://api.weather.gov/stations/THIS_IS_INVALID/observations/latest",
        # This non-routable IP will result in a connection timeout
        "http://10.255.255.1",
        # This will result in a DNS lookup error (RequestException)
        "http://non-existent-domain-for-testing-123.local/",
        # This URL serves malformed JSON (trailing comma)
        "https://gist.githubusercontent.com/dbgrandi/59846f535359b6620577764703a55a80/raw/ca4f3a7469772b14619f7062a7428f572979b08f/malformed.json"
    ]

    results = fetch_all_stations(urls_to_fetch)

    print("--- Successful Readings ---")
    if results["readings"]:
        for reading in results["readings"]:
            properties = reading.get("properties", {})
            station = properties.get("station", "N/A")
            description = properties.get("textDescription", "N/A")
            timestamp = properties.get("timestamp", "N/A")
            print(f"Station: {station} ({timestamp})")
            print(f"  -> {description}")
    else:
        print("No successful readings.")

    print("\n--- Error Report ---")
    if results["errors"]:
        for error in results["errors"]:
            print(f"URL: {error['url']}")
            print(f"  Type: {error['error_type']}")
            print(f"  Message: {error['message']}\n")
    else:
        print("No errors reported.")

if __name__ == "__main__":
    main()