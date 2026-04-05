import http.server
import json
import socketserver
import threading
import time
from typing import Dict, List

import requests


def fetch_all_stations(urls: List[str]) -> List[Dict]:
    """
    Fetches sensor readings from a list of station URLs.

    Args:
        urls: A list of string URLs for the station endpoints.

    Returns:
        A list of dictionaries, where each dictionary represents a sensor reading.
    """
    readings = []
    for url in urls:
        response = requests.get(url)
        readings.append(response.json())
    return readings


def main():
    """
    Sets up mock servers, demonstrates fetching data, and prints the results.
    """
    station_data = {
        8001: {
            "station_id": "st-15b",
            "temperature": 23.4,
            "humidity": 55.1,
            "timestamp": "2023-09-28T14:30:00Z",
        },
        8002: {
            "station_id": "st-23c",
            "temperature": 21.9,
            "humidity": 60.5,
            "timestamp": "2023-09-28T14:32:15Z",
        },
        8003: {
            "station_id": "st-42d",
            "temperature": 25.1,
            "humidity": 51.7,
            "timestamp": "2023-09-28T14:29:45Z",
        },
    }

    class StationHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            port = self.server.server_address[1]
            if port in station_data:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                response_data = json.dumps(station_data[port])
                self.wfile.write(response_data.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

    server_threads = []
    for port in station_data:
        server = socketserver.TCPServer(("", port), StationHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        server_threads.append(server)

    time.sleep(0.1)

    station_urls = [f"http://localhost:{port}" for port in station_data]

    try:
        all_readings = fetch_all_stations(station_urls)
        import pprint
        pprint.pprint(all_readings)
    finally:
        for server in server_threads:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()