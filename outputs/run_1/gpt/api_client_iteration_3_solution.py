import concurrent.futures
import json
import random
import threading
import time
from typing import Any


class MockResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class MockRequests:
    def __init__(self):
        self._lock = threading.Lock()
        self._attempts: dict[str, int] = {}

    def get(self, url: str, timeout: float = 2.0) -> MockResponse:
        station_id = url.rstrip("/").split("/")[-1]
        with self._lock:
            attempt = self._attempts.get(url, 0) + 1
            self._attempts[url] = attempt

        delay = self._compute_delay(station_id, attempt)
        if delay > timeout:
            time.sleep(timeout)
            raise TimeoutError(f"Request timed out after {timeout}s")
        time.sleep(delay)

        behavior = self._behavior(station_id, attempt)
        if behavior == "timeout":
            raise TimeoutError(f"Request timed out after {timeout}s")
        if behavior == "connection":
            raise ConnectionError("Connection failed")
        if behavior == "rate_limit":
            return MockResponse(429, {"error": "rate limited"})
        if behavior == "server_error":
            return MockResponse(503, {"error": "service unavailable"})
        if behavior == "not_found":
            return MockResponse(404, {"error": "station not found"})
        if behavior == "bad_json":
            return MockResponse(200, {"invalid": True})

        seed = sum(ord(c) for c in station_id)
        temperature = round(10 + (seed % 200) / 10.0, 1)
        humidity = 30 + (seed % 60)
        return MockResponse(
            200,
            {
                "station": station_id,
                "temperature_c": temperature,
                "humidity_pct": humidity,
                "timestamp": int(time.time()),
            },
        )

    def _compute_delay(self, station_id: str, attempt: int) -> float:
        if "slow" in station_id:
            return 1.5 + (attempt - 1) * 0.1
        if "hang" in station_id:
            return 5.0
        return 0.05 + (sum(ord(c) for c in station_id) % 10) * 0.03

    def _behavior(self, station_id: str, attempt: int) -> str:
        if "ok" in station_id:
            return "ok"
        if "slow" in station_id:
            return "ok"
        if "hang" in station_id:
            return "timeout"
        if "missing" in station_id:
            return "not_found"
        if "badjson" in station_id:
            return "bad_json"
        if "flaky" in station_id:
            return "connection" if attempt < 3 else "ok"
        if "ratelimit" in station_id:
            return "rate_limit" if attempt < 2 else "ok"
        if "server" in station_id:
            return "server_error" if attempt < 3 else "ok"
        if "dead" in station_id:
            return "connection"
        return "ok"


requests = MockRequests()

MAX_RETRIES = 3
REQUEST_TIMEOUT = 2.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BACKOFF_BASE = 0.2


def fetch_station(url: str) -> tuple[str, dict[str, Any] | None, dict[str, Any] | None]:
    last_error: dict[str, Any] | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            status = response.status_code

            if status == 200:
                payload = response.json()
                if not isinstance(payload, dict) or "station" not in payload:
                    last_error = {
                        "url": url,
                        "type": "invalid_response",
                        "message": "Missing expected station data",
                        "attempts": attempt,
                    }
                else:
                    return url, payload, None
            elif status in RETRYABLE_STATUS and attempt < MAX_RETRIES:
                last_error = {
                    "url": url,
                    "type": "http_error",
                    "status_code": status,
                    "message": f"Retryable HTTP status {status}",
                    "attempts": attempt,
                }
            else:
                return url, None, {
                    "url": url,
                    "type": "http_error",
                    "status_code": status,
                    "message": f"HTTP status {status}",
                    "attempts": attempt,
                }
        except TimeoutError as exc:
            last_error = {
                "url": url,
                "type": "timeout",
                "message": str(exc),
                "attempts": attempt,
            }
        except ConnectionError as exc:
            last_error = {
                "url": url,
                "type": "connection_error",
                "message": str(exc),
                "attempts": attempt,
            }
        except Exception as exc:
            return url, None, {
                "url": url,
                "type": "unexpected_error",
                "message": str(exc),
                "attempts": attempt,
            }

        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE * (2 ** (attempt - 1)))

    if last_error is None:
        last_error = {
            "url": url,
            "type": "unknown_error",
            "message": "Unknown failure",
            "attempts": MAX_RETRIES,
        }
    else:
        last_error = dict(last_error)
        last_error["attempts"] = MAX_RETRIES
    return url, None, last_error


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    readings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {executor.submit(fetch_station, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                _, reading, error = future.result()
                if reading is not None:
                    readings.append(reading)
                elif error is not None:
                    errors.append(error)
                else:
                    errors.append(
                        {
                            "url": url,
                            "type": "unknown_error",
                            "message": "No reading or error returned",
                            "attempts": MAX_RETRIES,
                        }
                    )
            except Exception as exc:
                errors.append(
                    {
                        "url": url,
                        "type": "worker_failure",
                        "message": str(exc),
                        "attempts": 0,
                    }
                )

    readings.sort(key=lambda r: r.get("station", ""))
    errors.sort(key=lambda e: e.get("url", ""))
    return {"readings": readings, "errors": errors}


def build_example_urls() -> list[str]:
    urls: list[str] = []
    base = "https://api.example.com/stations"

    for i in range(1, 41):
        urls.append(f"{base}/ok-{i:03d}")
    for i in range(1, 11):
        urls.append(f"{base}/slow-{i:03d}")
    for i in range(1, 9):
        urls.append(f"{base}/flaky-{i:03d}")
    for i in range(1, 7):
        urls.append(f"{base}/ratelimit-{i:03d}")
    for i in range(1, 6):
        urls.append(f"{base}/server-{i:03d}")
    for i in range(1, 5):
        urls.append(f"{base}/missing-{i:03d}")
    for i in range(1, 4):
        urls.append(f"{base}/badjson-{i:03d}")
    for i in range(1, 4):
        urls.append(f"{base}/dead-{i:03d}")
    for i in range(1, 4):
        urls.append(f"{base}/hang-{i:03d}")

    random.seed(42)
    random.shuffle(urls)
    return urls


def main() -> None:
    urls = build_example_urls()
    start = time.perf_counter()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print(json.dumps(results, indent=2, sort_keys=True))
    print(f"Total stations: {len(urls)}")
    print(f"Successful readings: {len(results['readings'])}")
    print(f"Errors: {len(results['errors'])}")
    print(f"Elapsed time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()