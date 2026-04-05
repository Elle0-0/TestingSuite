import requests
from unittest.mock import patch, Mock

def fetch_all_stations(urls: list[str]) -> list[dict]:
    readings = []
    for url in urls:
        response = requests.get(url)
        readings.append(response.json())
    return readings

def main():
    station_urls = [
        "http://station-alpha.example.com/api/reading",
        "http://station-beta.example.com/api/reading",
        "http://station-gamma.example.com/api/reading",
    ]

    mock_data_map = {
        "http://station-alpha.example.com/api/reading": {
            "station_id": "alpha-001",
            "temperature": 23.5,
            "humidity": 55.2,
            "timestamp": "2023-10-27T10:00:00Z",
        },
        "http://station-beta.example.com/api/reading": {
            "station_id": "beta-001",
            "temperature": 19.8,
            "humidity": 62.0,
            "timestamp": "2023-10-27T10:01:00Z",
        },
        "http://station-gamma.example.com/api/reading": {
            "station_id": "gamma-001",
            "temperature": 25.1,
            "humidity": 48.5,
            "timestamp": "2023-10-27T10:02:00Z",
        },
    }

    def mock_requests_get(url, *args, **kwargs):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data_map[url]
        return mock_response

    with patch('requests.get', side_effect=mock_requests_get):
        all_readings = fetch_all_stations(station_urls)
        print(all_readings)

if __name__ == "__main__":
    main()