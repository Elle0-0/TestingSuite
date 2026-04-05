import json
import requests
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Dict

# --- Mock Server Setup (for demonstration purposes) ---
# This part simulates the remote weather station endpoints.

STATION_DATA = {
    "station-1": {
        "station_id": "station-1",
        "temperature": 25.5,
        "humidity": 60.1,
        "timestamp": "2023-10-27T10:00:00Z",
    },
    "station-2": {
        "station_id": "station-2",
        "temperature": 24.9,
        "humidity": 62.5,
        "timestamp": "2023-10-27T10:01:00Z",
    },
    "station-3": {
        "station_id": "station-3",
        "temperature": 26.1,
        "humidity": 58.9,
        "timestamp": "2023-10-27T09:59:00Z",
    },
}

class MockStationHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        station_id = self.path.strip("/")
        if station_id in STATION_DATA:
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response_payload = json.dumps(STATION_DATA[station_id])
            self.wfile.write(response_payload.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "Station not found"}')

    def log_message(self, format, *args):
        # Suppress logging to keep the output clean for the demonstration
        return

def start_mock_server(port: int):
    server = HTTPServer(("localhost", port), MockStationHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

# --- API Client Implementation ---

def fetch_all_stations(urls: List[str]) -> List[Dict]:
    """
    Fetches data from a list of station URLs and returns a list of readings.
    """
    collected_readings = []
    for url in urls:
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            collected_readings.append(response.json())
        except requests.exceptions.RequestException as e:
            # In a real-world scenario, you would handle errors gracefully.
            # For this version, we assume success as per requirements.
            # This is here for good practice.
            print(f"Could not fetch data from {url}: {e}")
    return collected_readings

def main():
    """
    Demonstrates the solution with example URLs and prints the results.
    """
    # Start mock servers in the background
    ports = [8001, 8002, 8003]
    for i, port in enumerate(ports):
        start_mock_server(port)

    # Create a list of URLs for the mock stations
    base_url = "http://localhost"
    station_urls = [
        f"{base_url}:{ports[0]}/station-1",
        f"{base_url}:{ports[1]}/station-2",
        f"{base_url}:{ports[2]}/station-3",
    ]

    # Fetch data from all stations
    all_readings = fetch_all_stations(station_urls)

    # Print the combined results
    print(json.dumps(all_readings, indent=2))

if __name__ == "__main__":
    main()