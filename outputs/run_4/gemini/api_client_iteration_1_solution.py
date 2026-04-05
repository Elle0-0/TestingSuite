import requests
from unittest.mock import patch, MagicMock


def fetch_all_stations(urls: list[str]) -> list[dict]:
    all_readings = []
    for url in urls:
        response = requests.get(url)
        all_readings.append(response.json())
    return all_readings


def main():
    mock_station_data = {
        "http://weather.station.one/api/latest": {
            "station_id": "WS-01A",
            "temperature": 15.2,
            "humidity": 88.5,
            "timestamp": "2024-05-21T10:00:00Z"
        },
        "http://weather.station.two/api/latest": {
            "station_id": "WS-02B",
            "temperature": 16.1,
            "humidity": 87.0,
            "timestamp": "2024-05-21T10:01:00Z"
        },
        "http://weather.station.three/api/latest": {
            "station_id": "WS-03C",
            "temperature": 14.8,
            "humidity": 90.2,
            "timestamp": "2024-05-21T09:59:00Z"
        }
    }

    example_urls = list(mock_station_data.keys())

    def mock_get(url):
        response_mock = MagicMock()
        response_mock.status_code = 200
        response_mock.json.return_value = mock_station_data.get(url)
        return response_mock

    with patch('requests.get', side_effect=mock_get):
        collected_readings = fetch_all_stations(example_urls)
        print(collected_readings)


if __name__ == "__main__":
    main()