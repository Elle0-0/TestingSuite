import requests
import time
import json
from typing import Any


def fetch_station_with_retries(url: str, max_retries: int = 3, initial_backoff: float = 0.5, timeout: float = 5.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Returns the parsed JSON data on success.
    Raises an exception on permanent failure after retries are exhausted.
    """
    last_exception = None
    backoff = initial_backoff
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = min(float(retry_after), 2.0)
                    except ValueError:
                        wait_time = backoff
                else:
                    wait_time = backoff
                
                if attempt < max_retries:
                    time.sleep(wait_time)
                    backoff = min(backoff * 2, 4.0)
                    continue
                else:
                    raise requests.exceptions.HTTPError(
                        f"Rate limited (429) after {max_retries + 1} attempts",
                        response=response
                    )
            
            # Handle server errors (5xx) - these are retryable
            if response.status_code >= 500:
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 4.0)
                    continue
                else:
                    response.raise_for_status()
            
            # Handle client errors (4xx except 429) - not retryable
            if response.status_code >= 400:
                response.raise_for_status()
            
            # Try to parse JSON
            data = response.json()
            return data
            
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 4.0)
                continue
            else:
                raise
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff = min(backoff * 2, 4.0)
                continue
            else:
                raise
                
        except json.JSONDecodeError as e:
            # Malformed JSON - not likely transient, don't retry
            raise
                
        except requests.exceptions.HTTPError:
            raise
    
    if last_exception:
        raise last_exception


def classify_error(exception: Exception) -> str:
    """Classify the error type for reporting."""
    if isinstance(exception, requests.exceptions.Timeout):
        return "timeout"
    elif isinstance(exception, requests.exceptions.ConnectionError):
        return "connection_error"
    elif isinstance(exception, json.JSONDecodeError):
        return "malformed_json"
    elif isinstance(exception, requests.exceptions.HTTPError):
        response = getattr(exception, 'response', None)
        if response is not None:
            if response.status_code == 429:
                return "rate_limited"
            elif response.status_code >= 500:
                return "server_error"
            elif response.status_code >= 400:
                return "client_error"
        return "http_error"
    elif isinstance(exception, ValueError):
        return "malformed_json"
    else:
        return type(exception).__name__


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from all station URLs, handling failures gracefully.
    
    Returns a dictionary with:
      - "readings": list of successful results (each with url and data)
      - "errors": list of error dicts (each with url, error_type, and message)
    """
    readings = []
    errors = []
    
    for url in urls:
        try:
            data = fetch_station_with_retries(url, max_retries=2, initial_backoff=0.3, timeout=3.0)
            readings.append({
                "url": url,
                "data": data
            })
        except Exception as e:
            error_type = classify_error(e)
            errors.append({
                "url": url,
                "error_type": error_type,
                "message": str(e)
            })
    
    return {
        "readings": readings,
        "errors": errors
    }


def main():
    """Demonstrate the solution with example URLs including some that simulate failures."""
    urls = [
        # Successful request returning JSON
        "https://jsonplaceholder.typicode.com/posts/1",
        # Another successful request
        "https://jsonplaceholder.typicode.com/posts/2",
        # 404 not found (client error, no retry)
        "https://jsonplaceholder.typicode.com/posts/99999999",
        # Non-existent host (connection error)
        "https://this-station-does-not-exist.invalid/api/reading",
        # Another successful request
        "https://jsonplaceholder.typicode.com/users/1",
    ]
    
    print("Fetching data from all stations...")
    print(f"Total stations to query: {len(urls)}")
    print("=" * 60)
    
    result = fetch_all_stations(urls)
    
    # Print successful readings
    print(f"\nSuccessful readings: {len(result['readings'])}")
    print("-" * 40)
    for reading in result["readings"]:
        print(f"  URL: {reading['url']}")
        data = reading["data"]
        data_str = json.dumps(data, indent=2)
        if len(data_str) > 200:
            data_str = data_str[:200] + "..."
        print(f"  Data: {data_str}")
        print()
    
    # Print error reports
    print(f"\nFailed stations: {len(result['errors'])}")
    print("-" * 40)
    for error in result["errors"]:
        print(f"  URL: {error['url']}")
        print(f"  Error Type: {error['error_type']}")
        message = error["message"]
        if len(message) > 150:
            message = message[:150] + "..."
        print(f"  Message: {message}")
        print()
    
    # Summary
    print("=" * 60)
    total = len(urls)
    success = len(result["readings"])
    failed = len(result["errors"])
    print(f"Summary: {success}/{total} successful, {failed}/{total} failed")
    
    if result["errors"]:
        print("\nError type breakdown:")
        error_types = {}
        for error in result["errors"]:
            et = error["error_type"]
            error_types[et] = error_types.get(et, 0) + 1
        for et, count in sorted(error_types.items()):
            print(f"  {et}: {count}")


if __name__ == "__main__":
    main()