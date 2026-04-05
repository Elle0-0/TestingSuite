import requests
import time
import json
from typing import Any


def fetch_station_with_retries(url: str, max_retries: int = 3, initial_backoff: float = 1.0, timeout: float = 10.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Returns the parsed JSON data on success.
    Raises an exception on permanent failure after retries are exhausted.
    """
    last_exception = None
    backoff = initial_backoff
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
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
                        f"Rate limited (429) after {max_retries} attempts",
                        response=response
                    )
            
            # Handle server errors (5xx) - these are retryable
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
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
            # Malformed JSON - could retry in case it was a transient issue
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                raise
                
        except requests.exceptions.HTTPError:
            raise
    
    # Should not normally reach here, but just in case
    if last_exception:
        raise last_exception


def classify_error(exception: Exception) -> tuple[str, str]:
    """
    Classify an exception into an error type and message.
    Returns (error_type, message).
    """
    if isinstance(exception, requests.exceptions.Timeout):
        return ("timeout", str(exception))
    elif isinstance(exception, requests.exceptions.ConnectionError):
        return ("connection_error", str(exception))
    elif isinstance(exception, json.JSONDecodeError):
        return ("malformed_json", f"JSON decode error: {exception.msg} at line {exception.lineno} col {exception.colno}")
    elif isinstance(exception, requests.exceptions.HTTPError):
        status_code = None
        if exception.response is not None:
            status_code = exception.response.status_code
        if status_code == 429:
            return ("rate_limited", str(exception))
        elif status_code and status_code >= 500:
            return ("server_error", f"HTTP {status_code}: {str(exception)}")
        elif status_code and status_code >= 400:
            return ("client_error", f"HTTP {status_code}: {str(exception)}")
        else:
            return ("http_error", str(exception))
    elif isinstance(exception, requests.exceptions.RequestException):
        return ("request_error", str(exception))
    else:
        return ("unknown_error", str(exception))


def fetch_all_stations(urls: list[str], max_retries: int = 3, initial_backoff: float = 1.0, timeout: float = 10.0) -> dict:
    """
    Fetch data from all station URLs. Failures from one station do not
    terminate processing of remaining stations.
    
    Returns a dictionary with:
        - "readings": list of successful results (each a dict with 'url' and 'data')
        - "errors": list of error dicts (each with 'url', 'error_type', and 'message')
    """
    readings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    
    for url in urls:
        try:
            data = fetch_station_with_retries(
                url,
                max_retries=max_retries,
                initial_backoff=initial_backoff,
                timeout=timeout
            )
            readings.append({
                "url": url,
                "data": data
            })
        except Exception as e:
            error_type, message = classify_error(e)
            errors.append({
                "url": url,
                "error_type": error_type,
                "message": message
            })
    
    return {
        "readings": readings,
        "errors": errors
    }


def main():
    """
    Demonstrate the solution with example URLs including some that simulate failures.
    Uses httpbin.org and similar services for demonstration.
    """
    # Example URLs - mix of working and failing endpoints
    urls = [
        # Successful JSON endpoint
        "https://jsonplaceholder.typicode.com/posts/1",
        # Another successful endpoint
        "https://jsonplaceholder.typicode.com/posts/2",
        # Non-existent endpoint (404 - client error)
        "https://jsonplaceholder.typicode.com/posts/999999999",
        # Invalid domain (connection error)
        "https://this-domain-does-not-exist-12345.com/api/data",
        # Simulated server error (httpbin returns 500)
        "https://httpbin.org/status/500",
        # Simulated timeout (httpbin delays 30s, but our timeout is shorter)
        "https://httpbin.org/delay/30",
        # Simulated rate limit (429)
        "https://httpbin.org/status/429",
        # Another successful endpoint
        "https://jsonplaceholder.typicode.com/users/1",
    ]
    
    print("=" * 70)
    print("Fetching data from multiple stations...")
    print("=" * 70)
    print()
    
    # Use short timeouts and backoffs for demonstration
    results = fetch_all_stations(urls, max_retries=2, initial_backoff=0.5, timeout=5.0)
    
    # Print successful readings
    print(f"Successful readings: {len(results['readings'])}")
    print("-" * 50)
    for reading in results["readings"]:
        data = reading["data"]
        # Truncate data display for readability
        if isinstance(data, dict):
            keys = list(data.keys())
            preview = {k: data[k] for k in keys[:3]}
            if len(keys) > 3:
                print(f"  URL: {reading['url']}")
                print(f"  Data (preview): {preview} ... ({len(keys)} total keys)")
            else:
                print(f"  URL: {reading['url']}")
                print(f"  Data: {preview}")
        else:
            print(f"  URL: {reading['url']}")
            print(f"  Data: {str(data)[:200]}")
        print()
    
    # Print error reports
    print(f"\nFailed stations: {len(results['errors'])}")
    print("-" * 50)
    for error in results["errors"]:
        print(f"  URL: {error['url']}")
        print(f"  Error Type: {error['error_type']}")
        print(f"  Message: {error['message'][:200]}")
        print()
    
    # Summary
    print("=" * 70)
    total = len(urls)
    success = len(results["readings"])
    failed = len(results["errors"])
    print(f"Summary: {success}/{total} stations succeeded, {failed}/{total} failed")
    print("=" * 70)


if __name__ == "__main__":
    main()