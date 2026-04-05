import requests
from unittest.mock import patch, Mock
import pprint

def fetch_all_stations(urls: list[str]) -> list[dict]:
    """
    Takes a list of endpoint URLs, retrieves the data from each,
    and combines the results into a single list.

    Args:
        urls: A list of string URLs for the weather station endpoints.

    Returns:
        A list of dictionaries, where each dictionary is a sensor reading.
    """
    all_readings = []
    for url in urls:
        response = requests.get(url)
        # As per requirements, we assume all stations respond correctly.
        # In a real-world scenario, you would add error handling here, e.g.:
        # response.raise_for_status()
        all_readings.append(response.json())
    return all_readings

def main():
    """
    Demonstrates the solution with example URLs and prints the results.
    This function uses mocking to simulate the remote endpoints without
    making actual network calls.
    """
    example_urls = [
        "http://weather.station.local/api/reading/stn-alpha",
        "http://weather.station.local/api/reading/stn-beta",
        "http://weather.station.local/api/reading/stn-gamma",
    ]

    mock_readings = {
        "http://weather.station.local/api/reading/stn-alpha": {
            "station_id": "stn-alpha",
            "temperature": 23.4,
            "humidity": 65.1,
            "timestamp": "2023-10-27T10:00:00Z",
        },
        "http://weather.station.local/api/reading/stn-beta": {
            "station_id": "stn-beta",
            "temperature": 19.8,
            "humidity": 72.3,
            "timestamp": "2023-10-27T10:01:00Z",
        },
        "http://weather.station.local/api/reading/stn-gamma": {
            "station_id": "stn-gamma",
            "temperature": 25.0,
            "humidity": 59.8,
            "timestamp": "2023-10-27T09:59:00Z",
        },
    }

    def mock_get_side_effect(url, **kwargs):
        """A function to be used as the side_effect for the mock."""
        mock_response = Mock()
        mock_response.json.return_value = mock_readings.get(url)
        # We can also mock other attributes/methods if needed
        # mock_response.status_code = 200
        return mock_response

    # The 'with' block replaces 'requests.get' with our mock for its duration.
    with patch('requests.get', side_effect=mock_get_side_effect):
        # Call the function we want to test
        all_data = fetch_all_stations(example_urls)

        # Print the collected results in a readable format
        pprint.pprint(all_data)

if __name__ == "__main__":
    main()