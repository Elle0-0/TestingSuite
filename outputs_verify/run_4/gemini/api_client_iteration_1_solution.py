import json
import pprint
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List

import requests


def fetch_all_stations(urls: List[str]) -> List[Dict]:
    """
    Fetches sensor readings from a list of station URLs.

    Args:
        urls: A list of URLs, each pointing to a station's JSON endpoint.

    Returns:
        A list of dictionaries, where each dictionary is a sensor reading.
    """
    readings = []
    for url in urls:
        response = requests.get(url)
        readings.append(response.json())
    return readings


# The following code is for demonstration purposes only.
# It sets up a temporary local web server to act as the weather stations.

MOCK_DATA = {
    "/station_alpha": {
        "station_id": "alpha-123",
        "temperature": 25.5,
        "humidity": 60.2,
        "timestamp": "2023-10-27T10:00:00Z",
    },
    "/station_beta": {
        "station_id": "beta-456",
        "temperature": 24.9,
        "humidity": 62.5,
        "timestamp": "2023-10-27T10:01:00Z",
    },
    "/station_gamma": {
        "station_id": "gamma-789",
        "temperature": 26.1,
        "humidity": 58.8,
        "timestamp": "2023-10-27T10:00:30Z",
    },
}


class MockHTTPRequestHandler(BaseHTTPRequestHandler):
    """A simple request handler to serve mock station data."""

    def do_GET(self):
        if self.path in MOCK_DATA:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_payload = json.dumps(MOCK_DATA[self.path])
            self.wfile.write(response_payload.encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        return


def main():
    """
    Demonstrates the fetch_all_stations function using a local mock server.
    """
    PORT = 8008
    SERVER_URL_BASE = f"http://localhost:{PORT}"

    # Set up and start the mock server in a background thread
    httpd = HTTPServer(("", PORT), MockHTTPRequestHandler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True  # Allows main thread to exit and kill server
    server_thread.start()
    time.sleep(0.1)  # Give the server a moment to start

    # Define the example URLs for the mock stations
    example_urls = [f"{SERVER_URL_BASE}{path}" for path in MOCK_DATA.keys()]

    # Fetch the data using the function
    all_readings = fetch_all_stations(example_urls)

    # Print the collected results
    pprint.pprint(all_readings)


if __name__ == "__main__":
    main()