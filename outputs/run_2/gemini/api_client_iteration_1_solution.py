import requests
from typing import Any
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver


def fetch_all_stations(urls: list[str]) -> list[dict[str, Any]]:
    readings = []
    for url in urls:
        response = requests.get(url)
        readings.append(response.json())
    return readings


def main():
    mock_data = {
        "/v1/data/1": {
            "station_id": 1,
            "temperature": 15.2,
            "humidity": 88.1,
            "timestamp": "2024-05-21T11:00:00Z",
        },
        "/v1/data/2": {
            "station_id": 2,
            "temperature": 16.5,
            "humidity": 85.5,
            "timestamp": "2024-05-21T11:01:00Z",
        },
        "/v1/data/3": {
            "station_id": 3,
            "temperature": 14.8,
            "humidity": 90.3,
            "timestamp": "2024-05-21T11:02:00Z",
        },
    }

    class MockRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in mock_data:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(mock_data[self.path]).encode("utf-8"))
            else:
                self.send_error(404)

        def log_message(self, format, *args):
            return  # Suppress logging

    # Use a TCP server that allows address reuse
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    # Let the OS pick an available port by passing 0
    server_address = ("localhost", 0)
    httpd = ReusableTCPServer(server_address, MockRequestHandler)
    port = httpd.server_address[1] # Get the actual port number

    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    station_urls = [
        f"http://localhost:{port}/v1/data/1",
        f"http://localhost:{port}/v1/data/2",
        f"http://localhost:{port}/v1/data/3",
    ]

    try:
        all_readings = fetch_all_stations(station_urls)
        print(all_readings)
    finally:
        httpd.shutdown()
        httpd.server_close()
        server_thread.join()


if __name__ == "__main__":
    main()