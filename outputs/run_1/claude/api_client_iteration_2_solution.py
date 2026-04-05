import requests
import time
import json
from typing import Any


def fetch_station_data(url: str, max_retries: int = 3, initial_backoff: float = 1.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Returns the parsed JSON data on success.
    Raises an exception on permanent failure after retries are exhausted.
    """
    last_exception = None
    backoff = initial_backoff
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            
            # Handle rate limiting (429 Too Many Requests)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = backoff
                else:
                    wait_time = backoff
                
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    backoff *= 2
                    continue
                else:
                    raise requests.exceptions.HTTPError(
                        f"Rate limited (429) after {max_retries} attempts", response=response
                    )
            
            # Handle temporary server errors (500, 502, 503, 504)
            if response.status_code in (500, 502, 503, 504):
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    response.raise_for_status()
            
            # Handle other HTTP errors (4xx that aren't 429, etc.) - don't retry
            response.raise_for_status()
            
            # Attempt to parse JSON
            data = response.json()
            return data
            
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                raise
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                raise
                
        except json.JSONDecodeError as e:
            # Malformed JSON - no point retrying
            raise
            
        except requests.exceptions.HTTPError:
            # Non-retryable HTTP errors were already handled above
            raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")


def classify_error(exception: Exception) -> str:
    """Classify an exception into an error type string."""
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
    else:
        return type(exception).__name__


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from all station URLs, handling failures gracefully.
    
    Returns a dictionary with:
        - "readings": list of successfully fetched data
        - "errors": list of dicts with "url", "error_type", and "message"
    """
    readings = []
    errors = []
    
    for url in urls:
        try:
            data = fetch_station_data(url)
            readings.append(data)
        except Exception as e:
            error_type = classify_error(e)
            error_record = {
                "url": url,
                "error_type": error_type,
                "message": str(e)
            }
            errors.append(error_record)
    
    return {
        "readings": readings,
        "errors": errors
    }


def main():
    """Demonstrate the solution with example URLs including some that simulate failures."""
    # Using httpbin.org and similar services to simulate various conditions
    urls = [
        # Successful request
        "https://jsonplaceholder.typicode.com/posts/1",
        # Another successful request
        "https://jsonplaceholder.typicode.com/posts/2",
        # Will cause a connection error (non-existent domain)
        "https://nonexistent-station-abc123.example.com/data",
        # Will return 404 (client error)
        "https://jsonplaceholder.typicode.com/posts/99999999",
        # Another successful request
        "https://jsonplaceholder.typicode.com/users/1",
        # Will cause a timeout (using a non-routable IP)
        # "https://10.255.255.1/data",  # Commented out to avoid long waits in demo
        # Simulated server error
        "https://httpbin.org/status/500",
    ]
    
    print("Fetching data from stations...")
    print("=" * 60)
    
    result = fetch_all_stations(urls)
    
    print(f"\nSuccessful readings: {len(result['readings'])}")
    print("-" * 40)
    for i, reading in enumerate(result["readings"], 1):
        # Print a summary of each reading
        if isinstance(reading, dict):
            keys = list(reading.keys())[:5]
            summary = {k: reading[k] for k in keys}
            print(f"  Reading {i}: {summary}")
        else:
            print(f"  Reading {i}: {reading}")
    
    print(f"\nErrors encountered: {len(result['errors'])}")
    print("-" * 40)
    for i, error in enumerate(result["errors"], 1):
        print(f"  Error {i}:")
        print(f"    URL: {error['url']}")
        print(f"    Type: {error['error_type']}")
        print(f"    Message: {error['message'][:100]}...")
    
    print("\n" + "=" * 60)
    print(f"Summary: {len(result['readings'])} succeeded, {len(result['errors'])} failed "
          f"out of {len(urls)} total stations")


if __name__ == "__main__":
    main()