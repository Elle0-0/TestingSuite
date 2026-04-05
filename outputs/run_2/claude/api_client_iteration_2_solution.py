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
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        wait_time = min(float(retry_after), 2.0)
                    except ValueError:
                        wait_time = backoff
                else:
                    wait_time = backoff
                
                if attempt < max_retries:
                    time.sleep(wait_time)
                    backoff *= 2
                    continue
                else:
                    raise requests.exceptions.HTTPError(
                        f"Rate limited (429) after {max_retries + 1} attempts",
                        response=response
                    )
            
            # Handle server errors (5xx) - retryable
            if response.status_code >= 500:
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                else:
                    response.raise_for_status()
            
            # Handle client errors (4xx except 429) - not retryable
            if response.status_code >= 400:
                response.raise_for_status()
            
            # Try to parse JSON
            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"Malformed JSON response: {e}")
            
            # Validate that we got meaningful data
            if data is None:
                raise ValueError("Response returned null/empty JSON")
            
            return data
            
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                raise
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                raise
                
        except (requests.exceptions.HTTPError, ValueError):
            raise
            
        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                continue
            else:
                raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Failed to fetch {url} after {max_retries + 1} attempts")


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from all station URLs, handling failures gracefully.
    
    Returns a dictionary with:
    - "readings": list of successful results (each including the source url)
    - "errors": list of error dicts with url, error_type, and message
    """
    readings = []
    errors = []
    
    for url in urls:
        try:
            data = fetch_station_with_retries(url)
            reading = {
                "url": url,
                "data": data
            }
            readings.append(reading)
            
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
            errors.append({
                "url": url,
                "error_type": "HTTPError",
                "message": str(e)
            })
            
        except ValueError as e:
            errors.append({
                "url": url,
                "error_type": "ValueError",
                "message": str(e)
            })
            
        except requests.exceptions.RequestException as e:
            errors.append({
                "url": url,
                "error_type": type(e).__name__,
                "message": str(e)
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
    """Demonstrate the solution with example URLs including some that simulate failures."""
    
    # Use URLs that respond quickly or fail quickly to avoid timeout
    urls = [
        # Successful JSON response
        "https://jsonplaceholder.typicode.com/posts/1",
        # Another successful response
        "https://jsonplaceholder.typicode.com/posts/2",
        # 404 not found
        "https://jsonplaceholder.typicode.com/posts/99999999",
        # Non-existent host (connection error - fails quickly with short timeout)
        "https://this-station-does-not-exist.invalid/api/reading",
        # Simulate server error (500)
        "https://httpbin.org/status/500",
        # Simulate rate limiting (429)
        "https://httpbin.org/status/429",
        # Returns HTML instead of JSON
        "https://httpbin.org/html",
    ]
    
    print("Fetching station data from {} URLs...".format(len(urls)))
    print("=" * 60)
    
    result = fetch_all_stations(urls)
    
    # Print successful readings
    print("\nSuccessful Readings ({}/{}):".format(
        len(result["readings"]), len(urls)
    ))
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
    print("\nErrors ({}/{}):".format(
        len(result["errors"]), len(urls)
    ))
    print("-" * 40)
    for error in result["errors"]:
        print(f"  URL: {error['url']}")
        print(f"  Type: {error['error_type']}")
        message = error["message"]
        if len(message) > 150:
            message = message[:150] + "..."
        print(f"  Message: {message}")
        print()
    
    # Summary
    print("=" * 60)
    print(f"Summary: {len(result['readings'])} succeeded, {len(result['errors'])} failed out of {len(urls)} stations")


if __name__ == "__main__":
    main()