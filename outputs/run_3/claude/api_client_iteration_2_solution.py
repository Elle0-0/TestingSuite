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
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = initial_backoff * (2 ** attempt)
                else:
                    wait_time = initial_backoff * (2 ** attempt)
                
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue
                else:
                    raise requests.exceptions.HTTPError(
                        f"Rate limited (429) after {max_retries} attempts",
                        response=response
                    )
            
            # Handle server errors (5xx) - these are retryable
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    wait_time = initial_backoff * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    response.raise_for_status()
            
            # Handle client errors (4xx except 429) - not retryable
            if 400 <= response.status_code < 500:
                response.raise_for_status()
            
            # Try to parse JSON
            data = response.json()
            return data
            
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = initial_backoff * (2 ** attempt)
                time.sleep(wait_time)
                continue
            else:
                raise
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = initial_backoff * (2 ** attempt)
                time.sleep(wait_time)
                continue
            else:
                raise
                
        except json.JSONDecodeError as e:
            # Malformed JSON - may or may not be retryable
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = initial_backoff * (2 ** attempt)
                time.sleep(wait_time)
                continue
            else:
                raise
                
        except requests.exceptions.HTTPError:
            raise
            
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = initial_backoff * (2 ** attempt)
                time.sleep(wait_time)
                continue
            else:
                raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")


def classify_error(exception: Exception) -> str:
    """Classify an exception into a human-readable error type."""
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
            elif response.status_code == 404:
                return "not_found"
            else:
                return f"http_error_{response.status_code}"
        return "http_error"
    elif isinstance(exception, ValueError):
        return "value_error"
    else:
        return type(exception).__name__


def fetch_all_stations(urls: list[str], max_retries: int = 3, initial_backoff: float = 1.0) -> dict:
    """
    Fetch data from multiple station URLs.
    
    Returns a dictionary with:
    - "readings": list of successful results (dicts with 'url' and 'data')
    - "errors": list of error records (dicts with 'url', 'error_type', and 'message')
    """
    readings = []
    errors = []
    
    for url in urls:
        try:
            data = fetch_station_data(url, max_retries=max_retries, initial_backoff=initial_backoff)
            readings.append({
                "url": url,
                "data": data
            })
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
    # Using httpbin.org and similar services to simulate various scenarios
    urls = [
        # Successful request
        "https://httpbin.org/json",
        # Successful request with delay (but within timeout)
        "https://httpbin.org/delay/1",
        # 404 - Not Found
        "https://httpbin.org/status/404",
        # 500 - Server Error (will trigger retries)
        "https://httpbin.org/status/500",
        # 429 - Rate Limited
        "https://httpbin.org/status/429",
        # Invalid URL - connection error
        "https://this-station-does-not-exist-12345.example.com/data",
        # Returns HTML instead of JSON (malformed JSON scenario)
        "https://httpbin.org/html",
    ]
    
    print("Fetching data from stations...")
    print(f"Total stations to query: {len(urls)}")
    print("-" * 60)
    
    # Use small backoff for demo purposes
    results = fetch_all_stations(urls, max_retries=2, initial_backoff=0.5)
    
    # Print successful readings
    print(f"\nSuccessful readings: {len(results['readings'])}")
    print("=" * 60)
    for reading in results["readings"]:
        print(f"\n  URL: {reading['url']}")
        data = reading["data"]
        # Truncate data display if too long
        data_str = json.dumps(data, indent=2)
        if len(data_str) > 200:
            data_str = data_str[:200] + "..."
        print(f"  Data: {data_str}")
    
    # Print error reports
    print(f"\nErrors encountered: {len(results['errors'])}")
    print("=" * 60)
    for error in results["errors"]:
        print(f"\n  URL: {error['url']}")
        print(f"  Error Type: {error['error_type']}")
        message = error["message"]
        if len(message) > 150:
            message = message[:150] + "..."
        print(f"  Message: {message}")
    
    # Summary
    print("\n" + "-" * 60)
    total = len(urls)
    successful = len(results["readings"])
    failed = len(results["errors"])
    print(f"Summary: {successful}/{total} successful, {failed}/{total} failed")
    
    return results


if __name__ == "__main__":
    main()