import json
import time
import requests
from typing import Any, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, Mock

MAX_RETRIES = 3
DEFAULT_RETRY_AFTER_SECONDS = 1

class StationFetchError(Exception):
    """Custom exception for station data fetching errors."""
    def __init__(self, message: str, url: str, error_type: str):
        super().__init__(message)
        self.url = url
        self.error_type = error_type

def _fetch_single_station_with_retries(url: str) -> Dict[str, Any]:
    """
    Fetches data for a single station, with retries for temporary failures.
    Raises StationFetchError on unrecoverable failure.
    """
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=5)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", DEFAULT_RETRY_AFTER_SECONDS))
                last_exception = StationFetchError(
                    f"Rate limited. Waiting {retry_after}s.",
                    url,
                    "RateLimitError"
                )
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()
            return data

        except requests.exceptions.HTTPError as e:
            if 500 <= e.response.status_code < 600:
                wait_time = DEFAULT_RETRY_AFTER_SECONDS * (attempt + 1)
                last_exception = StationFetchError(
                    f"Server error: {e.response.status_code}. Retrying in {wait_time}s.",
                    url,
                    "ServerError"
                )
                time.sleep(wait_time)
                continue
            else:
                raise StationFetchError(
                    f"Client error: {e.response.status_code} {e.response.reason}",
                    url,
                    "ClientError"
                ) from e
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            wait_time = DEFAULT_RETRY_AFTER_SECONDS * (attempt + 1)
            last_exception = StationFetchError(
                f"Network error: {type(e).__name__}. Retrying in {wait_time}s.",
                url,
                "NetworkError"
            )
            time.sleep(wait_time)
            continue
        except json.JSONDecodeError as e:
            raise StationFetchError(
                f"Malformed JSON response: {e}",
                url,
                "JSONDecodeError"
            ) from e

    raise last_exception or StationFetchError(
        f"All {MAX_RETRIES} retries failed.",
        url,
        "RetryLimitExceeded"
    )

def fetch_all_stations(urls: List[str]) -> Dict[str, List[Any]]:
    """
    Fetches data from a list of station URLs concurrently, handling failures.

    Returns a dictionary with "readings" for successes and "errors" for failures.
    """
    readings = []
    errors = []

    with ThreadPoolExecutor(max_workers=len(urls) or 1) as executor:
        future_to_url = {
            executor.submit(_fetch_single_station_with_retries, url): url
            for url in urls
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                readings.append(data)
            except StationFetchError as e:
                errors.append({
                    "url": e.url,
                    "error_type": e.error_type,
                    "message": str(e),
                })
            except Exception as e:
                errors.append({
                    "url": url,
                    "error_type": type(e).__name__,
                    "message": str(e),
                })

    return {"readings": readings, "errors": errors}

def main():
    """
    Demonstrates the solution with simulated failing URLs and prints results.
    """
    class MockState:
        def __init__(self):
            self.call_counts = {}
        def get_count(self, url):
            return self.call_counts.get(url, 0)
        def increment(self, url):
            self.call_counts[url] = self.call_counts.get(url, 0) + 1

    mock_state = MockState()

    def patched_requests_get(url, timeout=5):
        mock_state.increment(url)
        call_count = mock_state.get_count(url)
        response = Mock()
        response.headers = {}

        if url == "http://mock/ok":
            response.status_code = 200
            response.json.return_value = {"station_id": "OK", "data": "all_good"}
        elif url == "http://mock/temp_fail":
            if call_count < 2:
                response.status_code = 503
                response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=response)
            else:
                response.status_code = 200
                response.json.return_value = {"station_id": "TEMP_FAIL", "data": "recovered"}
        elif url == "http://mock/timeout":
            if call_count < 2:
                raise requests.exceptions.Timeout("Simulated timeout")
            else:
                response.status_code = 200
                response.json.return_value = {"station_id": "TIMEOUT", "data": "finally_connected"}
        elif url == "http://mock/bad_json":
            response.status_code = 200
            response.json.side_effect = json.JSONDecodeError("Syntax error", "<- invalid ->", 0)
        elif url == "http://mock/rate_limit":
            if call_count < 2:
                response.status_code = 429
                response.headers["Retry-After"] = "0.1"
            else:
                response.status_code = 200
                response.json.return_value = {"station_id": "RATE_LIMIT", "data": "request_accepted"}
        elif url == "http://mock/not_found":
            response.status_code = 404
            response.reason = "Not Found"
            response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=response)
        elif url == "http://mock/permanent_fail":
            response.status_code = 500
            response.reason = "Internal Server Error"
            response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=response)
        else:
            response.status_code = 404
            response.reason = "Unknown Mock"
            response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=response)
        
        return response

    urls_to_test = [
        "http://mock/ok",
        "http://mock/temp_fail",
        "http://mock/timeout",
        "http://mock/bad_json",
        "http://mock/rate_limit",
        "http://mock/not_found",
        "http://mock/permanent_fail",
    ]

    with patch('requests.get', side_effect=patched_requests_get):
        results = fetch_all_stations(urls_to_test)

    print("--- Successful Readings ---")
    sorted_readings = sorted(results["readings"], key=lambda r: r.get("station_id", ""))
    if sorted_readings:
        for reading in sorted_readings:
            print(reading)
    else:
        print("None")

    print("\n--- Error Reports ---")
    sorted_errors = sorted(results["errors"], key=lambda e: e.get("url", ""))
    if sorted_errors:
        for error in sorted_errors:
            print(error)
    else:
        print("None")


if __name__ == "__main__":
    main()