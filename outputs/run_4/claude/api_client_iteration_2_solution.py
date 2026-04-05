import requests
import time
import json


def fetch_station_data(url: str, max_retries: int = 3, initial_backoff: float = 1.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Returns the parsed JSON data on success.
    Raises an exception on permanent failure after retries are exhausted.
    """
    backoff = initial_backoff
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            
            # Handle rate limiting (429 Too Many Requests)
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
            
            # Handle temporary server errors (500, 502, 503, 504)
            if response.status_code in (500, 502, 503, 504):
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    response.raise_for_status()
            
            # Handle other HTTP errors (4xx except 429) - no retry
            if response.status_code >= 400:
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
            # Malformed JSON - could retry in case it's a transient issue
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
    elif isinstance(exception, requests.exceptions.RequestException):
        return "request_error"
    else:
        return "unknown_error"


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from all station URLs, handling failures gracefully.
    
    Returns a dictionary with:
        - "readings": list of successful results (each a dict with 'url' and 'data')
        - "errors": list of error dicts (each with 'url', 'error_type', and 'message')
    """
    readings = []
    errors = []
    
    for url in urls:
        try:
            data = fetch_station_data(url)
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
    # Using httpbin.org and similar services to simulate various conditions
    urls = [
        # Successful request
        "https://httpbin.org/json",
        # Simulates a 500 server error
        "https://httpbin.org/status/500",
        # Simulates a 404 not found
        "https://httpbin.org/status/404",
        # Simulates a timeout (delays 15 seconds, our timeout is 10)
        "https://httpbin.org/delay/15",
        # Simulates a 429 rate limit
        "https://httpbin.org/status/429",
        # Returns HTML instead of JSON (malformed JSON scenario)
        "https://httpbin.org/html",
        # Another successful request
        "https://httpbin.org/get",
        # Non-existent host (connection error)
        "https://this-station-does-not-exist.example.com/data",
    ]
    
    print("Fetching data from all stations...")
    print(f"Total stations to query: {len(urls)}")
    print("=" * 60)
    
    results = fetch_all_stations(urls)
    
    # Print successful readings
    print(f"\nSuccessful readings: {len(results['readings'])}")
    print("-" * 40)
    for reading in results["readings"]:
        print(f"  URL: {reading['url']}")
        data = reading["data"]
        # Truncate data display if it's too long
        data_str = json.dumps(data, indent=2)
        if len(data_str) > 200:
            data_str = data_str[:200] + "..."
        print(f"  Data: {data_str}")
        print()
    
    # Print error reports
    print(f"\nErrors encountered: {len(results['errors'])}")
    print("-" * 40)
    for error in results["errors"]:
        print(f"  URL: {error['url']}")
        print(f"  Error Type: {error['error_type']}")
        message = error["message"]
        if len(message) > 150:
            message = message[:150] + "..."
        print(f"  Message: {message}")
        print()
    
    # Summary
    total = len(urls)
    success = len(results["readings"])
    failed = len(results["errors"])
    print("=" * 60)
    print(f"Summary: {success}/{total} succeeded, {failed}/{total} failed")
    
    # Group errors by type
    if results["errors"]:
        error_types = {}
        for error in results["errors"]:
            etype = error["error_type"]
            error_types[etype] = error_types.get(etype, 0) + 1
        print("\nError breakdown:")
        for etype, count in sorted(error_types.items()):
            print(f"  {etype}: {count}")


if __name__ == "__main__":
    main()