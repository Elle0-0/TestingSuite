import json
import time
from typing import Any
from urllib import error, request


MAX_RETRIES = 3
DEFAULT_TIMEOUT = 5.0
USER_AGENT = "station-client/2.0"


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class MalformedResponseError(Exception):
    pass


class IncompleteResponseError(Exception):
    pass


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
        return max(0.0, seconds)
    except (ValueError, TypeError):
        return None


def classify_http_error(exc: error.HTTPError) -> Exception:
    if exc.code == 429:
        retry_after = parse_retry_after(exc.headers.get("Retry-After"))
        return RateLimitError(f"rate limited: HTTP {exc.code}", retry_after=retry_after)
    if 500 <= exc.code <= 599:
        return RuntimeError(f"temporary server error: HTTP {exc.code}")
    return exc


def validate_station_payload(data: Any) -> dict:
    if not isinstance(data, dict):
        raise MalformedResponseError("response is not a JSON object")

    required = ["station", "temperature"]
    missing = [key for key in required if key not in data]
    if missing:
        raise IncompleteResponseError(f"missing required fields: {', '.join(missing)}")

    return data


def fetch_station_once(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except error.HTTPError as exc:
        raise classify_http_error(exc) from exc
    except error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            raise TimeoutError("request timed out") from exc
        raise ConnectionError(str(reason)) from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MalformedResponseError(f"invalid JSON: {exc}") from exc

    return validate_station_payload(payload)


def is_retryable(exc: Exception) -> bool:
    return isinstance(exc, (TimeoutError, ConnectionError, RuntimeError, RateLimitError))


def fetch_with_retries(url: str, retries: int = MAX_RETRIES) -> dict:
    attempt = 0
    last_exc: Exception | None = None

    while attempt <= retries:
        try:
            return fetch_station_once(url)
        except Exception as exc:
            last_exc = exc
            if not is_retryable(exc) or attempt == retries:
                break

            wait_seconds = 0.5 * (2 ** attempt)
            if isinstance(exc, RateLimitError) and exc.retry_after is not None:
                wait_seconds = max(wait_seconds, exc.retry_after)

            time.sleep(wait_seconds)
            attempt += 1

    assert last_exc is not None
    raise last_exc


def fetch_all_stations(urls: list[str]) -> dict:
    readings: list[dict] = []
    errors: list[dict] = []

    for url in urls:
        try:
            reading = fetch_with_retries(url)
            readings.append(reading)
        except Exception as exc:
            errors.append(
                {
                    "url": url,
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    return {"readings": readings, "errors": errors}


def main() -> None:
    urls = [
        "https://example.com/stations/alpha",
        "https://example.com/stations/temporary-500",
        "https://example.com/stations/rate-limited",
        "https://example.com/stations/malformed-json",
        "https://example.com/stations/timeout",
        "https://example.com/stations/incomplete",
    ]

    result = fetch_all_stations(urls)
    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("Errors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()