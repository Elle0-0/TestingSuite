import requests
import json
import threading
import http.server
import socketserver
import time

def fetch_all_stations(urls: list[str]) -> list[dict]:
    """
    Fetches the latest reading from a list of station URLs.

    Args:
        urls: A list of URL strings for the station endpoints.

    Returns:
        A list of dictionaries, where each dictionary is a sensor reading.
    """
    collected_readings = []
    for url in urls:
        response = requests.get(url)
        # Per the prompt, we assume all stations respond correctly
        # and return valid data.
        reading = response.json()
        collected_readings.append(reading)
    return collected_readings

def main():
    """
    Demonstrates the solution with example URLs and prints the results.
    A temporary local server is created to simulate the weather station endpoints.
    """
    # Configuration for the mock server
    MOCK_DATA = {
        "/station_alpha": {
            "station_id": "alpha-123",
            "temperature": 15.5,
            "humidity": 65.2,
            "timestamp": "2023-10-27T10:00:00Z"
        },
        "/station_beta": {
            "station_id": "beta-456",
            "temperature": 18.2,
            "humidity": 55.0,
            "timestamp": "2023-10-27T10:01:00Z"
        },
        "/station_gamma": {
            "station_id": "gamma-789",
            "temperature": 12.8,
            "humidity": 72.8,
            "timestamp": "2023-10-27T09:59:00Z"
        }
    }

    # A custom request handler to serve the mock JSON data
    class MockStationHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path in MOCK_DATA:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                payload = json.dumps(MOCK_DATA[self.path])
                self.wfile.write(payload.encode("utf-8"))
            else:
                self.send_error(404, "Not Found")
        
        # Suppress server log messages for cleaner output
        def log_message(self, format, *args):
            return

    # Allow the server to reuse the address to avoid "Address already in use" errors
    # during rapid restarts. This is a common setting for development servers.
    socketserver.TCPServer.allow_reuse_address = True
    # Use port 0 to let the OS automatically select a free port
    httpd = socketserver.TCPServer(("", 0), MockStationHandler)
    port = httpd.server_address[1] # Get the port number assigned by the OS

    # Set up and start the server in a background thread
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True  # Allows main thread to exit even if server thread is running
    server_thread.start()
    
    # Give the server a moment to start up
    time.sleep(0.1) 

    try:
        # Generate the list of URLs for the mock endpoints using the dynamically assigned port
        station_urls = [f"http://localhost:{port}{path}" for path in MOCK_DATA.keys()]
        
        # Call the function to fetch data from all stations
        all_data = fetch_all_stations(station_urls)
        
        # Print the final combined list of readings
        print(all_data)

    finally:
        # Ensure the server is shut down cleanly
        httpd.shutdown()
        httpd.server_close()

if __name__ == "__main__":
    main()