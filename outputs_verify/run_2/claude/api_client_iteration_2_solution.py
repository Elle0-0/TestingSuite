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
                        wait_time = min(float(retry_after), 5.0)
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
            
            # Handle server errors (5xx) - these are retryable
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
                raise ValueError("Response returned null/None")
            
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
    
    if last_exception:
        raise last_exception
    raise RuntimeError(f"Failed to fetch {url} after {max_retries + 1} attempts")


def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetch data from all station URLs, handling failures gracefully.
    
    Returns a dictionary with:
        - "readings": list of successful results (dicts with 'url' and 'data')
        - "errors": list of error records (dicts with 'url', 'error_type', and 'message')
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
    urls = [
        # Successful JSON responses
        "https://jsonplaceholder.typicode.com/posts/1",
        "https://jsonplaceholder.typicode.com/posts/2",
        # Will return 404 (client error, not retried)
        "https://jsonplaceholder.typicode.com/posts/999999",
        # Non-existent domain (connection error)
        "https://this-station-does-not-exist-12345.invalid/data",
        # Another successful response
        "https://jsonplaceholder.typicode.com/users/1",
    ]
    
    print("Fetching data from stations...")
    print(f"Total stations to query: {len(urls)}")
    print("-" * 60)
    
    results = fetch_all_stations(urls)
    
    # Print successful readings
    print(f"\nSuccessful readings: {len(results['readings'])}")
    print("=" * 60)
    for reading in results['readings']:
        print(f"\n  URL: {reading['url']}")
        data = reading['data']
        if isinstance(data, dict):
            keys = list(data.keys())[:5]
            print(f"  Keys: {keys}")
            if 'id' in data:
                print(f"  ID: {data['id']}")
            if 'title' in data:
                title = data['title']
                print(f"  Title: {title[:50]}{'...' if len(title) > 50 else ''}")
            if 'name' in data:
                print(f"  Name: {data['name']}")
        else:
            print(f"  Data type: {type(data).__name__}")
    
    # Print error reports
    print(f"\nFailed stations: {len(results['errors'])}")
    print("=" * 60)
    for error in results['errors']:
        print(f"\n  URL: {error['url']}")
        print(f"  Error Type: {error['error_type']}")
        msg = error['message']
        print(f"  Message: {msg[:100]}{'...' if len(msg) > 100 else ''}")
    
    # Summary
    print("\n" + "=" * 60)
    total = len(urls)
    success = len(results['readings'])
    failed = len(results['errors'])
    print(f"Summary: {success}/{total} successful, {failed}/{total} failed")


if __name__ == "__main__":
    main()