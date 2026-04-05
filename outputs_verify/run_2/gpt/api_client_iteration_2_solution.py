import json
import time
from typing import Any
from urllib import error, request
from email.utils import parsedate_to_datetime


def _now() -> float:
    return time.time()


def _parse_retry_after(value: str | None) -> float:
    if not value:
        return 0.0
    value = value.strip()
    if not value:
        return 0.0
    if value.isdigit():
        return max(0.0, float(value))
    try:
        dt = parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - _now())
    except Exception:
        return 0.0


def _error_entry(url: str, error_type: str, message: str) -> dict:
    return {"url": url, "error_type": error_type, "message": message}


def _normalize_reading(url: str, payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("JSON payload is not an object")
    if "station" not in payload or "reading" not in payload:
        raise ValueError("JSON payload missing required keys: station, reading")
    return {
        "url": url,
        "station": payload["station"],
        "reading": payload["reading"],
        **{k: v for k, v in payload.items() if k not in {"station", "reading"}},
    }


def _fetch_single_station(
    url: str,
    *,
    timeout: float = 3.0,
    max_retries: int = 3,
    backoff_base: float = 0.5,
) -> dict:
    last_error: dict | None = None

    for attempt in range(max_retries + 1):
        try:
            with request.urlopen(url, timeout=timeout) as response:
                status = getattr(response, "status", response.getcode())
                if status == 429:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    if attempt < max_retries:
                        time.sleep(retry_after if retry_after > 0 else backoff_base * (2 ** attempt))
                        continue
                    return {
                        "ok": False,
                        "error": _error_entry(url, "RateLimitError", "Too many requests"),
                    }

                raw = response.read()
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError as e:
                    return {
                        "ok": False,
                        "error": _error_entry(url, "MalformedJSON", str(e)),
                    }

                try:
                    reading = _normalize_reading(url, payload)
                except ValueError as e:
                    return {
                        "ok": False,
                        "error": _error_entry(url, "InvalidPayload", str(e)),
                    }

                return {"ok": True, "reading": reading}

        except error.HTTPError as e:
            if e.code == 429:
                retry_after = _parse_retry_after(e.headers.get("Retry-After"))
                last_error = _error_entry(url, "RateLimitError", f"HTTP 429: {e.reason}")
                if attempt < max_retries:
                    time.sleep(retry_after if retry_after > 0 else backoff_base * (2 ** attempt))
                    continue
                return {"ok": False, "error": last_error}

            if 500 <= e.code <= 599:
                last_error = _error_entry(url, "TemporaryServerError", f"HTTP {e.code}: {e.reason}")
                if attempt < max_retries:
                    time.sleep(backoff_base * (2 ** attempt))
                    continue
                return {"ok": False, "error": last_error}

            return {
                "ok": False,
                "error": _error_entry(url, "HTTPError", f"HTTP {e.code}: {e.reason}"),
            }

        except error.URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, TimeoutError):
                last_error = _error_entry(url, "TimeoutError", str(reason))
            else:
                last_error = _error_entry(url, "URLError", str(reason))
            if attempt < max_retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            return {"ok": False, "error": last_error}

        except TimeoutError as e:
            last_error = _error_entry(url, "TimeoutError", str(e))
            if attempt < max_retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            return {"ok": False, "error": last_error}

        except Exception as e:
            return {
                "ok": False,
                "error": _error_entry(url, type(e).__name__, str(e)),
            }

    return {
        "ok": False,
        "error": last_error or _error_entry(url, "UnknownError", "Unknown failure"),
    }


def fetch_all_stations(urls: list[str]) -> dict:
    readings: list[dict] = []
    errors: list[dict] = []

    for url in urls:
        result = _fetch_single_station(url)
        if result["ok"]:
            readings.append(result["reading"])
        else:
            errors.append(result["error"])

    return {"readings": readings, "errors": errors}


class _MockHeaders(dict):
    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class _MockResponse:
    def __init__(self, status: int, body: str, headers: dict | None = None):
        self.status = status
        self._body = body.encode("utf-8")
        self.headers = _MockHeaders(headers or {})

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def main() -> None:
    original_urlopen = request.urlopen
    call_counts: dict[str, int] = {}

    def mock_urlopen(url: str, timeout: float = 0, *args, **kwargs):
        call_counts[url] = call_counts.get(url, 0) + 1
        n = call_counts[url]

        if "station-good-1" in url:
            return _MockResponse(200, json.dumps({"station": "station-good-1", "reading": 21.5}))

        if "station-good-2" in url:
            return _MockResponse(200, json.dumps({"station": "station-good-2", "reading": 18.2, "unit": "C"}))

        if "station-flaky-500" in url:
            if n < 3:
                raise error.HTTPError(url, 503, "Service Unavailable", hdrs=None, fp=None)
            return _MockResponse(200, json.dumps({"station": "station-flaky-500", "reading": 19.7}))

        if "station-timeout" in url:
            raise error.URLError(TimeoutError("request timed out"))

        if "station-malformed-json" in url:
            return _MockResponse(200, '{"station": "station-malformed-json", "reading": ')

        if "station-incomplete-json" in url:
            return _MockResponse(200, json.dumps({"station": "station-incomplete-json"}))

        if "station-rate-limit" in url:
            if n < 2:
                raise error.HTTPError(
                    url,
                    429,
                    "Too Many Requests",
                    hdrs=_MockHeaders({"Retry-After": "1"}),
                    fp=None,
                )
            return _MockResponse(200, json.dumps({"station": "station-rate-limit", "reading": 22.1}))

        raise error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    request.urlopen = mock_urlopen
    try:
        urls = [
            "https://example.test/station-good-1",
            "https://example.test/station-flaky-500",
            "https://example.test/station-timeout",
            "https://example.test/station-malformed-json",
            "https://example.test/station-incomplete-json",
            "https://example.test/station-rate-limit",
            "https://example.test/station-good-2",
            "https://example.test/station-missing",
        ]

        result = fetch_all_stations(urls)
        print("Readings:")
        print(json.dumps(result["readings"], indent=2))
        print("Errors:")
        print(json.dumps(result["errors"], indent=2))
    finally:
        request.urlopen = original_urlopen


if __name__ == "__main__":
    main()