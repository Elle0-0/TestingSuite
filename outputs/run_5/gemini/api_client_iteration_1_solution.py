import requests
import json
import time
import threading
import pprint
from http.server import BaseHTTPRequestHandler, HTTPServer

MOCK_STATIONS = {
    8001: {
        "station_id": "station-north-1",
        "temperature": 15.4,
        "humidity": 67.2,
        "timestamp": "2023-04-01T10:00:00Z"
    },
    8002: {
        "station_id": "station-west-2",
        "temperature": 18.1,
        "humidity": 55.9,
        "timestamp": "2023-04-01T10:01:00Z"
    },
    8003: {
        "station_id": "station-south-1",
        "temperature": 22.8,
        "humidity": 45.5,
        "timestamp": "2023-04-01T09:59:30Z"
    },
}

class _MockStationHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        port = self.server.server_address[1]
        data = MOCK_STATIONS.get(port)
        if data:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response_body = json.dumps(data)
            self.wfile.write(response_body.encode('utf-8'))
        else:
            self.send_error(404, "Station not found")

    def log_message(self, format: str, *args) -> None:
        return

def fetch_all_stations(urls: list[str]) -> list[dict]:
    all_readings = []
    for url in urls:
        response = requests.get(url)
        all_readings.append(response.json())
    return all_readings

def main():
    servers = []
    threads = []
    urls = []

    for port in MOCK_STATIONS.keys():
        server_address = ('localhost', port)
        server = HTTPServer(server_address, _MockStationHandler)
        servers.append(server)

        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        threads.append(thread)
        urls.append(f"http://{server_address[0]}:{server_address[1]}")

    for thread in threads:
        thread.start()

    time.sleep(0.1)

    try:
        station_data = fetch_all_stations(urls)
        pprint.pprint(station_data)
    finally:
        for server in servers:
            server.shutdown()

if __name__ == "__main__":
    main()