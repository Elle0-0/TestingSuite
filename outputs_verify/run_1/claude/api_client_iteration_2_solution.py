import requests
import time
import json
from typing import Any


def fetch_station_with_retries(url: str, max_retries: int = 3, base_delay: float = 1.0, timeout: float = 10.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Handles:
    - Temporary server errors (5xx) with retries
    - Timeouts with retries
    - Rate limiting (429) with Retry-After header respect
    - Malformed JSON
    - Other HTTP errors
    
    Returns the parsed JSON data on success.
    Raises an exception with details on permanent failure.
    """
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout)
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = float(retry_after)
                    except ValueError:
                        wait_time = base_delay * (2 ** attempt)
                else:
                    wait_time = base_delay * (2 ** attempt)
                
                if attempt < max_retries - 1:
                    time.sleep(wait_time)
                    continue
                else:
                    raise requests.exceptions.HTTPError(
                        f"Rate limited (429) after {max_retries} attempts",
                        response=response
                    )
            
            # Handle server errors (5xx) - retryable
            if 500 <= response.status_code < 600:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
                    continue
                else:
                    response.raise_for_status()
            
            # Handle client errors (4xx except 429) - not retryable
            if 400 <= response.status_code < 500:
                response.raise_for_status()
            
            # Try to parse JSON
            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Malformed JSON response: {e}")
            
            # Validate that we got meaningful data
            if data is None:
                raise ValueError("Response contained null/empty data")
            
            return data
            
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            else:
                raise
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            else:
                raise
                
        except (requests.exceptions.HTTPError, ValueError):
            raise
            
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            else:
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
    elif isinstance(exception, requests.exceptions.HTTPError):
        response = getattr(exception, 'response', None)
        if response is not None:
            status_code = response.status_code
            if status_code == 429:
                return "rate_limited"
            elif 500 <= status_code < 600:
                return "server_error"
            elif 400 <= status_code < 500:
                return "client_error"
        return "http_error"
    elif isinstance(exception, ValueError):
        return "malformed_response"
    elif isinstance(exception, json.JSONDecodeError):
        return "malformed_response"
    else:
        return "unknown_error"


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from all station URLs, handling failures gracefully.
    
    Returns a dictionary with:
    - "readings": list of successful results (dicts with url and data)
    - "errors": list of error records (dicts with url, error_type, and message)
    """
    readings = []
    errors = []
    
    for url in urls:
        try:
            data = fetch_station_with_retries(url)
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
    """Demonstrate the solution with example URLs including simulated failures."""
    # Using httpbin.org and similar services to demonstrate various scenarios
    # In a real scenario, these would be actual station API endpoints
    example_urls = [
        # Successful request
        "https://jsonplaceholder.typicode.com/posts/1",
        # Another successful request
        "https://jsonplaceholder.typicode.com/posts/2",
        # Will cause a 404 error (client error)
        "https://jsonplaceholder.typicode.com/posts/99999999",
        # Will cause a connection error (non-existent domain)
        "https://this-domain-does-not-exist-12345.com/api/station",
        # Another successful request
        "https://jsonplaceholder.typicode.com/users/1",
        # Will cause a timeout (using httpbin delay with short timeout)
        # Note: this uses a very long delay to simulate timeout
        "https://httpbin.org/delay/30",
    ]
    
    print("=" * 70)
    print("Fetching data from all stations...")
    print("=" * 70)
    print()
    
    # Use shorter timeout for demo purposes
    # Override the fetch to use shorter timeout for the demo
    original_fetch = fetch_station_with_retries
    
    results = {"readings": [], "errors": []}
    
    for url in example_urls:
        try:
            # Use shorter timeout and fewer retries for demo
            data = fetch_station_with_retries(url, max_retries=2, base_delay=0.5, timeout=5.0)
            results["readings"].append({
                "url": url,
                "data": data
            })
        except Exception as e:
            error_type = classify_error(e)
            results["errors"].append({
                "url": url,
                "error_type": error_type,
                "message": str(e)
            })
    
    # Print successful readings
    print(f"Successful readings: {len(results['readings'])}")
    print("-" * 50)
    for reading in results["readings"]:
        data = reading["data"]
        # Truncate data display for readability
        if isinstance(data, dict):
            preview = {k: v for i, (k, v) in enumerate(data.items()) if i < 3}
            if len(data) > 3:
                preview["..."] = f"({len(data) - 3} more fields)"
        else:
            preview = str(data)[:100]
        print(f"  URL: {reading['url']}")
        print(f"  Data: {preview}")
        print()
    
    # Print error reports
    print(f"\nErrors encountered: {len(results['errors'])}")
    print("-" * 50)
    for error in results["errors"]:
        print(f"  URL: {error['url']}")
        print(f"  Error Type: {error['error_type']}")
        print(f"  Message: {error['message'][:200]}")
        print()
    
    # Summary
    total = len(example_urls)
    successful = len(results["readings"])
    failed = len(results["errors"])
    print("=" * 70)
    print(f"Summary: {successful}/{total} stations fetched successfully, {failed} failures")
    print("=" * 70)
    
    return results


if __name__ == "__main__":
    main()