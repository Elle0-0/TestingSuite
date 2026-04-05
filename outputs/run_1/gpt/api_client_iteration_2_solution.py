import json
import time
from typing import Any
from urllib import error, request


def _sleep_with_cap(seconds: float, cap: float = 5.0) -> None:
    if seconds < 0:
        seconds = 0
    time.sleep(min(seconds, cap))


def _extract_retry_after(headers: Any) -> float | None:
    if headers is None:
        return None
    value = None
    try:
        value = headers.get("Retry-After")
    except Exception:
        value = None
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _classify_http_error(status_code: int) -> str:
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code < 600:
        return "temporary_http_error"
    if 400 <= status_code < 500:
        return "client_http_error"
    return "http_error"


def _parse_json_response(body: bytes) -> dict:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Malformed JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Incomplete JSON: expected top-level object")

    if "station" not in payload or "reading" not in payload:
        raise ValueError("Incomplete JSON: required keys 'station' and 'reading' missing")

    return payload


def _fetch_station(url: str, timeout: float = 2.0, max_retries: int = 3, backoff: float = 0.5) -> dict:
    attempts = 0
    last_error: Exception | None = None

    while attempts <= max_retries:
        attempts += 1
        try:
            with request.urlopen(url, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                if status == 429:
                    retry_after = _extract_retry_after(getattr(response, "headers", None))
                    if attempts <= max_retries:
                        _sleep_with_cap(retry_after if retry_after is not None else backoff * (2 ** (attempts - 1)))
                        continue
                    raise RuntimeError("Rate limited")
                body = response.read()
                return _parse_json_response(body)

        except error.HTTPError as exc:
            status = getattr(exc, "code", None)
            if status == 429:
                retry_after = _extract_retry_after(getattr(exc, "headers", None))
                if attempts <= max_retries:
                    _sleep_with_cap(retry_after if retry_after is not None else backoff * (2 ** (attempts - 1)))
                    last_error = exc
                    continue
                raise RuntimeError(f"HTTP 429 Too Many Requests: {exc.reason}") from exc

            if status is not None and 500 <= status < 600 and attempts <= max_retries:
                _sleep_with_cap(backoff * (2 ** (attempts - 1)))
                last_error = exc
                continue

            kind = _classify_http_error(status if status is not None else 0)
            raise RuntimeError(f"{kind}: HTTP {status} {exc.reason}") from exc

        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if attempts <= max_retries:
                _sleep_with_cap(backoff * (2 ** (attempts - 1)))
                last_error = exc
                continue
            raise TimeoutError(f"Network error or timeout: {reason}") from exc

        except TimeoutError as exc:
            if attempts <= max_retries:
                _sleep_with_cap(backoff * (2 ** (attempts - 1)))
                last_error = exc
                continue
            raise

        except ValueError:
            raise

    if last_error is not None:
        raise RuntimeError(str(last_error))
    raise RuntimeError("Unknown failure")


def fetch_all_stations(urls: list[str]) -> dict:
    readings: list[dict] = []
    errors: list[dict] = []

    for url in urls:
        try:
            result = _fetch_station(url)
            readings.append(result)
        except Exception as exc:
            errors.append(
                {
                    "url": url,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    return {"readings": readings, "errors": errors}


def main() -> None:
    urls = [
        "https://example.com/station/ok-1",
        "https://example.com/station/timeout",
        "https://example.com/station/malformed-json",
        "https://example.com/station/http-500",
        "https://example.com/station/rate-limited",
        "https://example.com/station/ok-2",
    ]

    original_urlopen = request.urlopen

    class MockHeaders(dict):
        def get(self, key: str, default: Any = None) -> Any:
            return super().get(key, default)

    class MockResponse:
        def __init__(self, body: str, status: int = 200, headers: dict | None = None):
            self._body = body.encode("utf-8")
            self.status = status
            self.headers = MockHeaders(headers or {})

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    state: dict[str, int] = {}

    def mock_urlopen(url: str, timeout: float = 2.0):
        state[url] = state.get(url, 0) + 1
        attempt = state[url]

        if url.endswith("ok-1"):
            return MockResponse(json.dumps({"station": "ok-1", "reading": 21.5}))
        if url.endswith("ok-2"):
            return MockResponse(json.dumps({"station": "ok-2", "reading": 19.8}))
        if url.endswith("timeout"):
            raise error.URLError("timed out")
        if url.endswith("malformed-json"):
            return MockResponse('{"station": "bad-json", "reading": ')
        if url.endswith("http-500"):
            if attempt < 3:
                raise error.HTTPError(url, 500, "Internal Server Error", hdrs=None, fp=None)
            return MockResponse(json.dumps({"station": "recovered-500", "reading": 22.1}))
        if url.endswith("rate-limited"):
            if attempt < 2:
                raise error.HTTPError(url, 429, "Too Many Requests", hdrs=MockHeaders({"Retry-After": "0.1"}), fp=None)
            return MockResponse(json.dumps({"station": "rate-limited", "reading": 18.4}))
        raise error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    request.urlopen = mock_urlopen
    try:
        result = fetch_all_stations(urls)
    finally:
        request.urlopen = original_urlopen

    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("Errors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()