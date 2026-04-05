import json
import time
from typing import Any
from urllib import error, request


MAX_RETRIES = 3
DEFAULT_TIMEOUT = 2.0


class TemporaryServiceError(Exception):
    pass


class MalformedResponseError(Exception):
    pass


def should_retry_status(status_code: int) -> bool:
    return status_code == 429 or 500 <= status_code < 600


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except (TypeError, ValueError):
        return None


def validate_payload(payload: Any, url: str) -> dict:
    if not isinstance(payload, dict):
        raise MalformedResponseError("Response JSON is not an object")
    required = ["station", "temperature"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise MalformedResponseError(f"Missing required fields: {', '.join(missing)}")
    return {
        "url": url,
        "station": payload["station"],
        "temperature": payload["temperature"],
    }


def fetch_station(url: str, max_retries: int = MAX_RETRIES, timeout: float = DEFAULT_TIMEOUT) -> dict:
    attempt = 0
    last_error = None

    while attempt <= max_retries:
        try:
            with request.urlopen(url, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if should_retry_status(status):
                    retry_after = parse_retry_after(response.headers.get("Retry-After"))
                    if attempt == max_retries:
                        raise TemporaryServiceError(f"HTTP {status}")
                    time.sleep(retry_after if retry_after is not None else min(2 ** attempt, 5))
                    attempt += 1
                    continue

                raw = response.read()
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    raise MalformedResponseError(f"Invalid JSON: {e}") from e

                return validate_payload(payload, url)

        except error.HTTPError as e:
            status = getattr(e, "code", None)
            if status is not None and should_retry_status(status) and attempt < max_retries:
                retry_after = parse_retry_after(e.headers.get("Retry-After") if e.headers else None)
                time.sleep(retry_after if retry_after is not None else min(2 ** attempt, 5))
                attempt += 1
                last_error = e
                continue
            raise
        except error.URLError as e:
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 5))
                attempt += 1
                last_error = e
                continue
            raise TemporaryServiceError(f"Network error: {e.reason}") from e
        except TimeoutError as e:
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 5))
                attempt += 1
                last_error = e
                continue
            raise TemporaryServiceError("Request timed out") from e
        except MalformedResponseError:
            raise
        except Exception as e:
            if "timed out" in str(e).lower() and attempt < max_retries:
                time.sleep(min(2 ** attempt, 5))
                attempt += 1
                last_error = e
                continue
            raise TemporaryServiceError(str(e)) from e

    if last_error is not None:
        raise TemporaryServiceError(str(last_error))
    raise TemporaryServiceError("Unknown temporary failure")


def fetch_all_stations(urls: list[str]) -> dict:
    readings = []
    errors = []

    for url in urls:
        try:
            readings.append(fetch_station(url))
        except Exception as e:
            errors.append(
                {
                    "url": url,
                    "error_type": type(e).__name__,
                    "message": str(e),
                }
            )

    return {"readings": readings, "errors": errors}


def main() -> None:
    example_urls = [
        "https://example.com/stations/ok-alpha",
        "https://example.com/stations/timeout",
        "https://example.com/stations/rate-limited",
        "https://example.com/stations/malformed-json",
        "https://example.com/stations/server-error",
        "https://example.com/stations/ok-beta",
    ]

    result = fetch_all_stations(example_urls)
    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("Errors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()