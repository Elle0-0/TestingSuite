import requests
import time
import json
import threading
import http.server
import socketserver
from typing import List, Dict, Any, Union

# --- Solution ---

def fetch_all_stations(urls: List[str]) -> Dict[str, List[Any]]:
    """
    Fetches data from a list of URLs with retries and error handling.

    Args:
        urls: A list of URL strings to fetch data from.

    Returns:
        A dictionary containing two keys:
        'readings': A list of successfully parsed JSON data.
        'errors': A list of dictionaries, each detailing a failed request.
    """
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 5  # seconds
    BACKOFF_FACTOR = 0.5 # seconds

    readings: List[Dict[str, Any]] = []
    errors: List[Dict[str, Union[str, int]]] = []
    
    session = requests.Session()

    for url in urls:
        last_exception_details = None
        for attempt in range(MAX_RETRIES):
            try:
                response = session.get(url, timeout=REQUEST_TIMEOUT)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "1"))
                    message = f"Rate limit hit. Waiting {retry_after}s."
                    last_exception_details = {
                        "url": url,
                        "error": "RateLimitError",
                        "message": message,
                    }
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()

                data = response.json()
                readings.append(data)
                last_exception_details = None 
                break 

            except requests.exceptions.HTTPError as e:
                # Non-retryable client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    last_exception_details = {
                        "url": url,
                        "error": "ClientError",
                        "message": str(e),
                    }
                    break
                # Retryable server errors (5xx)
                else:
                    last_exception_details = {
                        "url": url,
                        "error": "ServerError",
                        "message": str(e),
                    }
            
            except requests.exceptions.Timeout as e:
                last_exception_details = {
                    "url": url,
                    "error": "Timeout",
                    "message": f"Request timed out after {REQUEST_TIMEOUT}s.",
                }
                
            except requests.exceptions.ConnectionError as e:
                last_exception_details = {
                    "url": url,
                    "error": "ConnectionError",
                    "message": "Failed to establish a connection.",
                }

            except json.JSONDecodeError as e:
                last_exception_details = {
                    "url": url,
                    "error": "JSONDecodeError",
                    "message": "Failed to decode JSON from response.",
                }
                break
            
            except requests.exceptions.RequestException as e:
                last_exception_details = {
                    "url": url,
                    "error": "RequestException",
                    "message": str(e),
                }
                break

            # If we're here, it's a retryable error. Wait before the next attempt.
            wait_time = BACKOFF_FACTOR * (2 ** attempt)
            time.sleep(wait_time)

        if last_exception_details:
            errors.append(last_exception_details)
    
    return {"readings": readings, "errors": errors}

# --- Demonstration ---

def main():
    """
    Demonstrates the fetch_all_stations function using a local mock server
    that simulates various failure scenarios.
    """
    
    # State for our mock server to simulate transient errors
    server_state = {
        "server_error_attempts": 0,
        "rate_limit_attempts": 0,
    }

    class MockHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/ok":
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"station_id": "ok_station", "status": "ok"}')
            elif self.path == "/server_error":
                server_state["server_error_attempts"] += 1
                if server_state["server_error_attempts"] < 2:
                    self.send_error(503, "Service Unavailable")
                else:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"station_id": "flaky_station", "status": "ok"}')
            elif self.path == "/timeout":
                time.sleep(6) # Longer than client timeout
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"station_id": "timeout_station", "status": "ok"}')
            elif self.path == "/malformed_json":
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b'{"station_id": "bad_json", "status": "ok",}')
            elif self.path == "/rate_limit":
                server_state["rate_limit_attempts"] += 1
                if server_state["rate_limit_attempts"] < 2:
                    self.send_response(429)
                    self.send_header("Retry-After", "1")
                    self.end_headers()
                else:
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"station_id": "rate_limited_station", "status": "ok"}')
            elif self.path == "/permanent_fail":
                self.send_error(500, "Internal Server Error")
            else:
                self.send_error(404, "Not Found")

    PORT = 8012
    with socketserver.TCPServer(("", PORT), MockHandler) as httpd:
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        base_url = f"http://localhost:{PORT}"
        urls_to_fetch = [
            f"{base_url}/ok",
            f"{base_url}/server_error",      # Should fail once, then succeed
            f"{base_url}/rate_limit",        # Should hit rate limit, wait, then succeed
            f"{base_url}/timeout",           # Should fail due to timeout
            f"{base_url}/malformed_json",    # Should fail due to JSON parsing error
            f"{base_url}/permanent_fail",    # Should fail after all retries
            f"{base_url}/not_found",         # Should fail with 404 client error
            f"{base_url}/ok?id=2",           # Another successful call
        ]

        print("Fetching data from stations...")
        results = fetch_all_stations(urls_to_fetch)
        
        print("\n--- Successful Readings ---")
        if results["readings"]:
            for reading in results["readings"]:
                print(reading)
        else:
            print("No successful readings.")

        print("\n--- Error Report ---")
        if results["errors"]:
            for error in results["errors"]:
                print(f"URL: {error['url']}")
                print(f"  Error Type: {error['error']}")
                print(f"  Message: {error['message']}\n")
        else:
            print("No errors reported.")

        httpd.shutdown()

if __name__ == "__main__":
    main()