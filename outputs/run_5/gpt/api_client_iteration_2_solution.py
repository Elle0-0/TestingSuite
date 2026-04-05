from __future__ import annotations

import json
import time
from typing import Any
from urllib import error, request


def fetch_station_data(url: str, timeout: float = 5.0) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout) as response:
        status = getattr(response, "status", None)
        if status is not None and status >= 400:
            raise error.HTTPError(url, status, f"HTTP {status}", response.headers, None)

        raw = response.read()
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Malformed JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Incomplete JSON: expected object")

        required_keys = {"station", "temperature", "humidity"}
        missing = required_keys - data.keys()
        if missing:
            raise ValueError(f"Incomplete JSON: missing fields {sorted(missing)}")

        return data


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
        return max(0.0, seconds)
    except ValueError:
        return None


def fetch_all_stations(urls: list[str]) -> dict[str, list[dict[str, Any]]]:
    readings: list[dict[str, Any]] = []
    errors_list: list[dict[str, str]] = []

    max_retries = 3
    base_backoff = 0.5
    timeout = 3.0

    for url in urls:
        last_error: dict[str, str] | None = None

        for attempt in range(max_retries + 1):
            try:
                data = fetch_station_data(url, timeout=timeout)
                readings.append(data)
                last_error = None
                break

            except error.HTTPError as exc:
                status = getattr(exc, "code", None)

                if status == 429:
                    retry_after = _parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
                    if attempt < max_retries:
                        time.sleep(retry_after if retry_after is not None else base_backoff * (2 ** attempt))
                        continue
                    last_error = {
                        "url": url,
                        "error_type": "rate_limit",
                        "message": f"HTTP 429 Too Many Requests",
                    }
                    break

                if status is not None and 500 <= status < 600:
                    if attempt < max_retries:
                        time.sleep(base_backoff * (2 ** attempt))
                        continue
                    last_error = {
                        "url": url,
                        "error_type": "server_error",
                        "message": f"HTTP {status}: temporary server error",
                    }
                    break

                last_error = {
                    "url": url,
                    "error_type": "http_error",
                    "message": f"HTTP {status}: {exc.reason}",
                }
                break

            except error.URLError as exc:
                reason = exc.reason
                if attempt < max_retries:
                    time.sleep(base_backoff * (2 ** attempt))
                    continue
                last_error = {
                    "url": url,
                    "error_type": "network_error",
                    "message": str(reason),
                }
                break

            except TimeoutError as exc:
                if attempt < max_retries:
                    time.sleep(base_backoff * (2 ** attempt))
                    continue
                last_error = {
                    "url": url,
                    "error_type": "timeout",
                    "message": str(exc),
                }
                break

            except ValueError as exc:
                last_error = {
                    "url": url,
                    "error_type": "invalid_response",
                    "message": str(exc),
                }
                break

            except Exception as exc:
                last_error = {
                    "url": url,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
                break

        if last_error is not None:
            errors_list.append(last_error)

    return {"readings": readings, "errors": errors_list}


def main() -> None:
    example_urls = [
        "https://example.com/stations/alpha",
        "https://example.com/stations/beta",
        "https://example.com/stations/fail-500",
        "https://example.com/stations/timeout",
        "https://example.com/stations/malformed",
        "https://example.com/stations/rate-limited",
    ]

    result = fetch_all_stations(example_urls)

    print("Readings:")
    for reading in result["readings"]:
        print(reading)

    print("\nErrors:")
    for err in result["errors"]:
        print(err)


if __name__ == "__main__":
    main()