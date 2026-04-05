import urllib.request
import json
from typing import Any


def fetch_station(url: str) -> dict[str, Any]:
    """Fetch a single station's reading from the given URL."""
    with urllib.request.urlopen(url) as response:
        data = response.read().decode("utf-8")
        reading = json.loads(data)
    return reading


def fetch_all_stations(urls: list[str]) -> list[dict]:
    """Fetch readings from all station URLs and return them as a list of dicts.

    Each dict contains: station_id, temperature, humidity, and timestamp.
    """
    readings = []
    for url in urls:
        reading = fetch_station(url)
        readings.append(reading)
    return readings


def main():
    """Demonstrate the solution with example URLs and print the results."""
    # Example URLs pointing to weather station endpoints.
    # In a real deployment these would be actual station API endpoints.
    # For demonstration purposes we use JSONPlaceholder-style URLs or
    # a local mock server. Here we use httpbin.org to show structure,
    # but we'll simulate with a simple built-in HTTP server approach.

    # Since we need a working demo, we'll start a tiny local server
    # that serves fake station data.
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import time

    sample_stations = [
        {
            "station_id": "WS-001",
            "temperature": 22.5,
            "humidity": 65.3,
            "timestamp": "2024-01-15T10:30:00Z",
        },
        {
            "station_id": "WS-002",
            "temperature": 18.2,
            "humidity": 72.1,
            "timestamp": "2024-01-15T10:30:05Z",
        },
        {
            "station_id": "WS-003",
            "temperature": 25.8,
            "humidity": 55.7,
            "timestamp": "2024-01-15T10:30:10Z",
        },
    ]

    class StationHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Extract station index from path, e.g., /station/0
            parts = self.path.strip("/").split("/")
            if len(parts) == 2 and parts[0] == "station":
                try:
                    index = int(parts[1])
                    if 0 <= index < len(sample_stations):
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(
                            json.dumps(sample_stations[index]).encode("utf-8")
                        )
                        return
                except ValueError:
                    pass
            self.send_response(404)
            self.end_headers()

        def log_message(self, format, *args):
            # Suppress request logging for cleaner output
            pass

    # Start a local mock server
    server = HTTPServer(("127.0.0.1", 0), StationHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Give server a moment to start
    time.sleep(0.1)

    # Build URLs for each station
    urls = [
        f"http://127.0.0.1:{port}/station/{i}"
        for i in range(len(sample_stations))
    ]

    print(f"Fetching data from {len(urls)} weather stations...\n")

    # Fetch all station readings
    readings = fetch_all_stations(urls)

    # Display results
    print(f"Successfully collected {len(readings)} readings:\n")
    for reading in readings:
        print(f"  Station: {reading['station_id']}")
        print(f"    Temperature: {reading['temperature']}°C")
        print(f"    Humidity:    {reading['humidity']}%")
        print(f"    Timestamp:   {reading['timestamp']}")
        print()

    # Print the raw combined JSON
    print("Combined JSON output:")
    print(json.dumps(readings, indent=2))

    # Clean up
    server.shutdown()


if __name__ == "__main__":
    main()