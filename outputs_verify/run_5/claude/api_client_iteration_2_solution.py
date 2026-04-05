import requests
import time
import json


def fetch_station_data(url: str, max_retries: int = 3, base_delay: float = 1.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Returns the parsed JSON data on success.
    Raises an exception on permanent failure after retries are exhausted.
    """
    last_exception = None
    
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
            
            # Handle server errors (5xx) - these are retryable
            if response.status_code >= 500:
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
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
                time.sleep(base_delay * (2 ** attempt))
                continue
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
                
        except json.JSONDecodeError as e:
            # Malformed JSON - may not be worth retrying but we try anyway
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
                
        except requests.exceptions.HTTPError as e:
            last_exception = e
            # Client errors (4xx) are not retried
            if e.response is not None and 400 <= e.response.status_code < 500:
                raise
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
    
    # All retries exhausted
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from multiple station URLs, collecting successes and errors.
    
    Returns a dictionary with:
        - "readings": list of successful results (each includes url and data)
        - "errors": list of error dicts (each with url, error_type, and message)
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
        except requests.exceptions.Timeout as e:
            errors.append({
                "url": url,
                "error_type": "Timeout",
                "message": str(e)
            })
        except requests.exceptions.ConnectionError as e:
            errors.append({
                "url": url,
                "error_type": "ConnectionError",
                "message": str(e)
            })
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            errors.append({
                "url": url,
                "error_type": "HTTPError",
                "message": f"Status {status_code}: {str(e)}"
            })
        except json.JSONDecodeError as e:
            errors.append({
                "url": url,
                "error_type": "JSONDecodeError",
                "message": f"Malformed JSON: {str(e)}"
            })
        except Exception as e:
            errors.append({
                "url": url,
                "error_type": type(e).__name__,
                "message": str(e)
            })
    
    return {
        "readings": readings,
        "errors": errors
    }


def main():
    """Demonstrate the solution with example URLs including simulated failures."""
    # Using httpbin.org and similar services to demonstrate various scenarios
    urls = [
        # Successful JSON response
        "https://httpbin.org/json",
        # Simulates a server error (500)
        "https://httpbin.org/status/500",
        # Simulates a not found error (404)
        "https://httpbin.org/status/404",
        # Simulates a timeout (delays 15 seconds, our timeout is 10)
        "https://httpbin.org/delay/15",
        # Another successful response
        "https://httpbin.org/get",
        # Non-existent host to simulate connection error
        "https://this-station-does-not-exist.example.com/data",
        # Simulates rate limiting (429)
        "https://httpbin.org/status/429",
    ]
    
    print("Fetching data from stations...")
    print("=" * 60)
    
    result = fetch_all_stations(urls)
    
    print(f"\nSuccessful readings: {len(result['readings'])}")
    print("-" * 40)
    for reading in result["readings"]:
        print(f"  URL: {reading['url']}")
        data_preview = str(reading["data"])
        if len(data_preview) > 100:
            data_preview = data_preview[:100] + "..."
        print(f"  Data: {data_preview}")
        print()
    
    print(f"\nErrors encountered: {len(result['errors'])}")
    print("-" * 40)
    for error in result["errors"]:
        print(f"  URL: {error['url']}")
        print(f"  Type: {error['error_type']}")
        message = error["message"]
        if len(message) > 150:
            message = message[:150] + "..."
        print(f"  Message: {message}")
        print()


if __name__ == "__main__":
    main()