import json
import time
from typing import Any
from urllib import error, request


DEFAULT_TIMEOUT = 2.0
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 0.5


class TemporaryHTTPError(Exception):
    pass


class MalformedResponseError(Exception):
    pass


class IncompleteResponseError(Exception):
    pass


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value.strip())
        return max(0.0, seconds)
    except (TypeError, ValueError):
        return None


def _extract_error_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message if message else exc.__class__.__name__


def _validate_payload(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise MalformedResponseError("response is not a JSON object")

    required_keys = ["station", "temperature", "timestamp"]
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise IncompleteResponseError(f"missing required fields: {', '.join(missing)}")

    return payload


def _fetch_station(url: str) -> dict:
    req = request.Request(url, headers={"Accept": "application/json"})
    with request.urlopen(req, timeout=DEFAULT_TIMEOUT) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset)
        except Exception:
            text = raw.decode("utf-8", errors="replace")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MalformedResponseError(f"invalid JSON: {exc.msg}") from exc
        return _validate_payload(data)


def _fetch_with_retries(url: str, max_retries: int = MAX_RETRIES) -> dict:
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            return _fetch_station(url)
        except error.HTTPError as exc:
            status = exc.code
            if status == 429:
                if attempt == max_retries:
                    raise
                retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
                time.sleep(retry_after if retry_after is not None else BASE_BACKOFF_SECONDS * (2 ** attempt))
                last_error = exc
                continue
            if 500 <= status < 600:
                if attempt == max_retries:
                    raise TemporaryHTTPError(f"server error {status}") from exc
                retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
                time.sleep(retry_after if retry_after is not None else BASE_BACKOFF_SECONDS * (2 ** attempt))
                last_error = exc
                continue
            raise
        except error.URLError as exc:
            if attempt == max_retries:
                raise
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** attempt))
            last_error = exc
            continue
        except TimeoutError as exc:
            if attempt == max_retries:
                raise
            time.sleep(BASE_BACKOFF_SECONDS * (2 ** attempt))
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("unexpected retry flow")


def fetch_all_stations(urls: list[str]) -> dict:
    readings: list[dict] = []
    errors: list[dict[str, str]] = []

    for url in urls:
        try:
            readings.append(_fetch_with_retries(url))
        except Exception as exc:
            errors.append(
                {
                    "url": url,
                    "error_type": exc.__class__.__name__,
                    "message": _extract_error_message(exc),
                }
            )

    return {"readings": readings, "errors": errors}


def main() -> None:
    example_urls = [
        "https://example.com/stations/alpha",
        "https://example.com/stations/retry-500",
        "https://example.com/stations/rate-limit",
        "https://example.com/stations/malformed-json",
        "https://example.com/stations/incomplete",
        "https://example.com/stations/timeout",
    ]

    def mock_fetch_station(url: str) -> dict:
        if url.endswith("/alpha"):
            return {
                "station": "alpha",
                "temperature": 21.4,
                "timestamp": "2026-03-23T12:00:00Z",
            }
        if url.endswith("/retry-500"):
            count = mock_fetch_station.attempts.get(url, 0)
            mock_fetch_station.attempts[url] = count + 1
            if count < 2:
                raise error.HTTPError(
                    url=url,
                    code=503,
                    msg="Service Unavailable",
                    hdrs={},
                    fp=None,
                )
            return {
                "station": "retry-500",
                "temperature": 19.8,
                "timestamp": "2026-03-23T12:01:00Z",
            }
        if url.endswith("/rate-limit"):
            count = mock_fetch_station.attempts.get(url, 0)
            mock_fetch_station.attempts[url] = count + 1
            if count < 1:
                raise error.HTTPError(
                    url=url,
                    code=429,
                    msg="Too Many Requests",
                    hdrs={"Retry-After": "0"},
                    fp=None,
                )
            return {
                "station": "rate-limit",
                "temperature": 20.1,
                "timestamp": "2026-03-23T12:02:00Z",
            }
        if url.endswith("/malformed-json"):
            raise MalformedResponseError("invalid JSON: expecting value")
        if url.endswith("/incomplete"):
            raise IncompleteResponseError("missing required fields: temperature")
        if url.endswith("/timeout"):
            raise error.URLError("timed out")
        raise error.HTTPError(url=url, code=404, msg="Not Found", hdrs={}, fp=None)

    mock_fetch_station.attempts = {}

    global _fetch_station
    real_fetch_station = _fetch_station
    _fetch_station = mock_fetch_station
    try:
        result = fetch_all_stations(example_urls)
    finally:
        _fetch_station = real_fetch_station

    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("Errors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()