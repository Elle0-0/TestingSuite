import requests
import pprint
from unittest.mock import patch, Mock

def fetch_all_stations(urls: list[str]) -> list[dict]:
    all_readings = []
    for url in urls:
        response = requests.get(url)
        data = response.json()
        all_readings.append(data)
    return all_readings

def main():
    example_urls = [
        "http://station-alpha.example.com/api/reading",
        "http://station-beta.example.com/api/reading",
        "http://station-gamma.example.com/api/reading",
    ]

    mock_responses = [
        Mock(
            json=lambda: {
                "station_id": "alpha-001",
                "temperature": 23.5,
                "humidity": 45.2,
                "timestamp": "2023-10-27T10:00:00Z",
            }
        ),
        Mock(
            json=lambda: {
                "station_id": "beta-002",
                "temperature": 24.1,
                "humidity": 44.8,
                "timestamp": "2023-10-27T10:00:05Z",
            }
        ),
        Mock(
            json=lambda: {
                "station_id": "gamma-003",
                "temperature": 22.9,
                "humidity": 46.1,
                "timestamp": "2023-10-27T09:59:58Z",
            }
        ),
    ]

    with patch("requests.get", side_effect=mock_responses):
        collected_data = fetch_all_stations(example_urls)
        pprint.pprint(collected_data)

if __name__ == "__main__":
    main()