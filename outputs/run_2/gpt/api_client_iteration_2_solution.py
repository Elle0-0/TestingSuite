import json
import time
from typing import Any
from urllib import error, request


def _parse_retry_after(headers) -> float | None:
    value = None
    if headers is not None:
        value = headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _read_response(response) -> Any:
    raw = response.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON payload is not an object")
    required = {"station", "reading"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    return data


def _classify_exception(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        if exc.code == 429:
            return "rate_limit"
        if 500 <= exc.code < 600:
            return "server_error"
        return "http_error"
    if isinstance(exc, error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return "timeout"
        return "network_error"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, json.JSONDecodeError):
        return "malformed_json"
    if isinstance(exc, ValueError):
        return "invalid_data"
    return "unknown_error"


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    if isinstance(exc, error.URLError):
        reason = getattr(exc, "reason", None)
        return isinstance(reason, TimeoutError)
    return isinstance(exc, TimeoutError)


def _fetch_with_retries(
    url: str,
    retries: int = 3,
    timeout: float = 2.0,
    backoff: float = 0.5,
) -> dict:
    last_exc = None
    for attempt in range(retries + 1):
        try:
            with request.urlopen(url, timeout=timeout) as response:
                return _read_response(response)
        except Exception as exc:
            last_exc = exc
            if attempt >= retries or not _is_retryable(exc):
                break
            wait_time = 0.0
            if isinstance(exc, error.HTTPError) and exc.code == 429:
                wait_time = _parse_retry_after(getattr(exc, "headers", None)) or backoff * (2 ** attempt)
            else:
                wait_time = backoff * (2 ** attempt)
            time.sleep(wait_time)
    raise last_exc


def fetch_all_stations(urls: list[str]) -> dict:
    readings = []
    errors = []
    for url in urls:
        try:
            result = _fetch_with_retries(url)
            readings.append(result)
        except Exception as exc:
            errors.append(
                {
                    "url": url,
                    "type": _classify_exception(exc),
                    "message": str(exc),
                }
            )
    return {"readings": readings, "errors": errors}


class MockHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class MockHTTPError(error.HTTPError):
    def __init__(self, url: str, code: int, msg: str, headers=None):
        super().__init__(url, code, msg, headers or MockHeaders(), None)


class MockResponse:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class MockUrlOpen:
    def __init__(self):
        self.calls: dict[str, int] = {}

    def __call__(self, url: str, timeout: float = 2.0):
        count = self.calls.get(url, 0) + 1
        self.calls[url] = count

        if url.endswith("/ok/1"):
            return MockResponse(json.dumps({"station": "alpha", "reading": 12.4}))
        if url.endswith("/ok/2"):
            return MockResponse(json.dumps({"station": "beta", "reading": 9.7}))
        if url.endswith("/server-error"):
            if count < 3:
                raise MockHTTPError(url, 503, "Service Unavailable")
            return MockResponse(json.dumps({"station": "gamma", "reading": 15.1}))
        if url.endswith("/timeout"):
            raise error.URLError(TimeoutError("timed out"))
        if url.endswith("/malformed"):
            return MockResponse('{"station": "delta", "reading": ')
        if url.endswith("/incomplete"):
            return MockResponse(json.dumps({"station": "epsilon"}))
        if url.endswith("/rate-limit"):
            if count < 2:
                raise MockHTTPError(url, 429, "Too Many Requests", MockHeaders({"Retry-After": "0.1"}))
            return MockResponse(json.dumps({"station": "zeta", "reading": 7.2}))

        raise MockHTTPError(url, 404, "Not Found")


def main():
    urls = [
        "mock://station/ok/1",
        "mock://station/server-error",
        "mock://station/timeout",
        "mock://station/malformed",
        "mock://station/incomplete",
        "mock://station/rate-limit",
        "mock://station/ok/2",
        "mock://station/missing",
    ]

    original_urlopen = request.urlopen
    request.urlopen = MockUrlOpen()
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