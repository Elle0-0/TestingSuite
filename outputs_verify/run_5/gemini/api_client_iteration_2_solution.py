import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import pprint
import sys
from contextlib import closing

RATE_LIMIT_STATE = {"requests": 0, "limit_until": 0}

class UnreliableServiceHandler(BaseHTTPRequestHandler):
    """A mock server to simulate various failure modes."""
    def do_GET(self):
        if self.path == "/success":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"station_id": "ST01", "status": "OK"}).encode('utf-8'))
        elif self.path == "/retry_then_success":
            # Simulate a temporary server error that resolves on retry
            if RATE_LIMIT_STATE.get("/retry_then_success", 0) < 2:
                RATE_LIMIT_STATE["/retry_then_success"] = RATE_LIMIT_STATE.get("/retry_then_success", 0) + 1
                self.send_error(503, "Service Unavailable")
            else:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"station_id": "ST02", "status": "OK"}).encode('utf-8'))
        elif self.path == "/timeout":
            time.sleep(2) # Client timeout is 1.5s, so this will always time out
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"should have timed out")
        elif self.path == "/bad_json":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"station_id": "ST03", "status": "OK"') # Malformed
        elif self.path == "/permanent_fail":
            self.send_error(500, "Internal Server Error")
        elif self.path == "/rate_limit":
            now = time.time()
            if RATE_LIMIT_STATE["requests"] < 3:
                RATE_LIMIT_STATE["requests"] += 1
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"station_id": "ST04", "request_num": RATE_LIMIT_STATE["requests"]}).encode('utf-8'))
            elif now < RATE_LIMIT_STATE["limit_until"]:
                self.send_response(429)
                self.send_header("Retry-After", "2")
                self.end_headers()
                self.wfile.write(b"Rate limit exceeded")
            else:
                RATE_LIMIT_STATE["requests"] = 1
                RATE_LIMIT_STATE["limit_until"] = now + 5 # Reset and block for 5s
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"station_id": "ST04", "request_num": RATE_LIMIT_STATE["requests"]}).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")
    
    def log_message(self, format, *args):
        # Suppress server logging to keep output clean
        return

def run_server(port, server_stop_event):
    with HTTPServer(("", port), UnreliableServiceHandler) as httpd:
        while not server_stop_event.is_set():
            httpd.handle_request()

def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetches data from a list of URLs with retries for temporary failures.
    """
    readings = []
    errors = []

    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        backoff_factor=0.5,
        respect_retry_after_header=True
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    
    with requests.Session() as session:
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        for url in urls:
            try:
                response = session.get(url, timeout=1.5)
                response.raise_for_status()
                data = response.json()
                readings.append(data)
            except requests.exceptions.JSONDecodeError as e:
                errors.append({
                    "url": url,
                    "error_type": "JSONDecodeError",
                    "message": f"Failed to decode JSON: {e}"
                })
            except requests.exceptions.RequestException as e:
                # This catches ConnectionError, Timeout, HTTPError after retries, etc.
                errors.append({
                    "url": url,
                    "error_type": type(e).__name__,
                    "message": str(e)
                })
            except Exception as e:
                # Catch any other unexpected errors
                errors.append({
                    "url": url,
                    "error_type": type(e).__name__,
                    "message": str(e)
                })

    return {"readings": readings, "errors": errors}

def main():
    """
    Demonstrates the solution with a mock server and example URLs.
    """
    PORT = 8000
    BASE_URL = f"http://127.0.0.1:{PORT}"

    server_stop_event = threading.Event()
    server_thread = threading.Thread(target=run_server, args=(PORT, server_stop_event))
    server_thread.daemon = True
    server_thread.start()
    time.sleep(0.1) # Give the server a moment to start up

    urls = [
        f"{BASE_URL}/success",                # Should succeed
        f"{BASE_URL}/retry_then_success",     # Should retry and then succeed
        f"{BASE_URL}/rate_limit",             # First success
        f"{BASE_URL}/rate_limit",             # Second success
        f"{BASE_URL}/rate_limit",             # Third success
        f"{BASE_URL}/rate_limit",             # Fourth should hit rate limit, retry, then fail
        f"{BASE_URL}/bad_json",               # Should fail with JSONDecodeError
        f"{BASE_URL}/timeout",                # Should fail with Timeout
        f"{BASE_URL}/permanent_fail",         # Should retry and then fail with HTTPError
        f"{BASE_URL}/not_a_real_url"         # Should fail with HTTPError (404)
    ]

    results = fetch_all_stations(urls)
    
    print("--- Successful Readings ---")
    pprint.pprint(results["readings"])
    print("\n--- Error Reports ---")
    pprint.pprint(results["errors"])

    # Signal the server thread to stop
    server_stop_event.set()
    # To unblock the server thread's handle_request()
    try:
        with closing(requests.get(f"{BASE_URL}/shutdown", timeout=0.1)):
            pass
    except requests.exceptions.RequestException:
        pass

if __name__ == "__main__":
    main()