import json
import time
from typing import Any
from urllib import error, request
from email.utils import parsedate_to_datetime


def parse_retry_after(value: str | None) -> float:
    if not value:
        return 0.0
    value = value.strip()
    if not value:
        return 0.0
    try:
        return max(0.0, float(int(value)))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - time.time())
    except Exception:
        return 0.0


def should_retry_http(status: int) -> bool:
    return status == 429 or 500 <= status < 600


def fetch_station(url: str, max_retries: int = 3, timeout: float = 2.0, backoff_base: float = 0.5) -> dict[str, Any]:
    last_error: dict[str, Any] | None = None

    for attempt in range(max_retries + 1):
        try:
            with request.urlopen(url, timeout=timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                if should_retry_http(status):
                    retry_after = parse_retry_after(response.headers.get("Retry-After"))
                    if attempt < max_retries:
                        wait_time = retry_after if retry_after > 0 else backoff_base * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "HTTPError",
                            "message": f"HTTP {status}",
                        },
                    }

                body = response.read()
                try:
                    data = json.loads(body.decode("utf-8"))
                except Exception as exc:
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "JSONError",
                            "message": str(exc),
                        },
                    }

                if not isinstance(data, dict):
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "ValidationError",
                            "message": "Expected JSON object",
                        },
                    }

                required = ["station", "temperature"]
                missing = [key for key in required if key not in data]
                if missing:
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "ValidationError",
                            "message": f"Missing fields: {', '.join(missing)}",
                        },
                    }

                return {"ok": True, "reading": data}

        except error.HTTPError as exc:
            if should_retry_http(exc.code) and attempt < max_retries:
                retry_after = parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
                wait_time = retry_after if retry_after > 0 else backoff_base * (2 ** attempt)
                time.sleep(wait_time)
                continue
            last_error = {
                "url": url,
                "type": "HTTPError",
                "message": f"HTTP {exc.code}: {exc.reason}",
            }

        except error.URLError as exc:
            reason = exc.reason
            error_type = "TimeoutError" if isinstance(reason, TimeoutError) else "URLError"
            if attempt < max_retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            last_error = {
                "url": url,
                "type": error_type,
                "message": str(reason),
            }

        except TimeoutError as exc:
            if attempt < max_retries:
                time.sleep(backoff_base * (2 ** attempt))
                continue
            last_error = {
                "url": url,
                "type": "TimeoutError",
                "message": str(exc),
            }

        except Exception as exc:
            last_error = {
                "url": url,
                "type": type(exc).__name__,
                "message": str(exc),
            }
            break

    return {"ok": False, "error": last_error or {"url": url, "type": "UnknownError", "message": "Unknown failure"}}


def fetch_all_stations(urls: list[str]) -> dict:
    readings: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for url in urls:
        result = fetch_station(url)
        if result["ok"]:
            readings.append(result["reading"])
        else:
            errors.append(result["error"])

    return {"readings": readings, "errors": errors}


def main() -> None:
    urls = [
        "https://example.com/stations/alpha",
        "https://example.com/stations/retry-later",
        "https://example.com/stations/timeout",
        "https://example.com/stations/malformed-json",
        "https://example.com/stations/missing-fields",
        "https://example.com/stations/server-error",
    ]

    result = fetch_all_stations(urls)
    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("Errors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()