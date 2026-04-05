import requests
import time
import json
from typing import Any


def fetch_station_with_retries(url: str, max_retries: int = 3, base_delay: float = 1.0, timeout: float = 10.0) -> dict:
    """
    Fetch data from a single station URL with retry logic.
    
    Returns the parsed JSON data on success.
    Raises an exception with details on final failure.
    """
    last_exception = None
    
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
            else:
                raise
                
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            else:
                raise
                
        except json.JSONDecodeError as e:
            # Malformed JSON - may or may not be retryable
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            else:
                raise
                
        except requests.exceptions.HTTPError:
            raise
            
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            else:
                raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts")


def fetch_all_stations(urls: list[str], max_retries: int = 3, base_delay: float = 1.0, timeout: float = 10.0) -> dict:
    """
    Fetch data from all station URLs, collecting successful readings and errors.
    
    Returns a dictionary with:
        - "readings": list of successful results (each with url and data)
        - "errors": list of error dicts (each with url, error_type, and message)
    """
    readings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    
    for url in urls:
        try:
            data = fetch_station_with_retries(
                url, 
                max_retries=max_retries, 
                base_delay=base_delay, 
                timeout=timeout
            )
            readings.append({
                "url": url,
                "data": data
            })
        except requests.exceptions.Timeout as e:
            errors.append({
                "url": url,
                "error_type": "Timeout",
                "message": f"Request timed out after {max_retries} attempts: {str(e)}"
            })
        except requests.exceptions.ConnectionError as e:
            errors.append({
                "url": url,
                "error_type": "ConnectionError",
                "message": f"Connection failed after {max_retries} attempts: {str(e)}"
            })
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            errors.append({
                "url": url,
                "error_type": "HTTPError",
                "message": f"HTTP {status_code}: {str(e)}"
            })
        except json.JSONDecodeError as e:
            errors.append({
                "url": url,
                "error_type": "JSONDecodeError",
                "message": f"Malformed JSON response: {str(e)}"
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
    """
    Demonstrate fetch_all_stations with example URLs including simulated failures.
    Uses httpbin.org and similar services for demonstration.
    """
    urls = [
        # Successful JSON endpoint
        "https://jsonplaceholder.typicode.com/posts/1",
        # Another successful endpoint
        "https://jsonplaceholder.typicode.com/posts/2",
        # Simulated server error (500)
        "https://httpbin.org/status/500",
        # Simulated timeout (will be very slow)
        "https://httpbin.org/delay/30",
        # Non-existent domain (connection error)
        "https://this-station-does-not-exist-12345.example.com/data",
        # 404 not found
        "https://jsonplaceholder.typicode.com/posts/99999999",
        # Another successful endpoint
        "https://jsonplaceholder.typicode.com/posts/3",
    ]
    
    print("=" * 70)
    print("Fetching data from stations...")
    print("=" * 70)
    
    results = fetch_all_stations(urls, max_retries=2, base_delay=0.5, timeout=5.0)
    
    print(f"\n{'=' * 70}")
    print(f"SUCCESSFUL READINGS: {len(results['readings'])}")
    print(f"{'=' * 70}")
    
    for reading in results["readings"]:
        print(f"\n  URL: {reading['url']}")
        data = reading["data"]
        # Print a summary of the data
        if isinstance(data, dict):
            keys = list(data.keys())[:5]
            print(f"  Keys: {keys}")
            for key in keys[:3]:
                value = str(data[key])
                if len(value) > 80:
                    value = value[:80] + "..."
                print(f"    {key}: {value}")
        else:
            summary = str(data)[:100]
            print(f"  Data: {summary}")
    
    print(f"\n{'=' * 70}")
    print(f"ERRORS: {len(results['errors'])}")
    print(f"{'=' * 70}")
    
    for error in results["errors"]:
        print(f"\n  URL: {error['url']}")
        print(f"  Type: {error['error_type']}")
        message = error["message"]
        if len(message) > 120:
            message = message[:120] + "..."
        print(f"  Message: {message}")
    
    print(f"\n{'=' * 70}")
    print(f"Summary: {len(results['readings'])} successful, {len(results['errors'])} failed out of {len(urls)} stations")
    print(f"{'=' * 70}")
    
    return results


if __name__ == "__main__":
    main()