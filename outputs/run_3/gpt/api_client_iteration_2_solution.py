import json
import time
from typing import Any
from urllib import request, error


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def _is_valid_payload(data: Any) -> bool:
    return isinstance(data, dict) and "station" in data and "reading" in data


def _fetch_one(url: str, max_retries: int = 3, timeout: float = 2.0, backoff: float = 0.5) -> dict:
    last_error: dict | None = None

    for attempt in range(max_retries + 1):
        try:
            with request.urlopen(url, timeout=timeout) as response:
                status = getattr(response, "status", None) or response.getcode()
                body = response.read().decode("utf-8")

                if status == 429:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    if attempt < max_retries:
                        time.sleep(retry_after if retry_after is not None else backoff * (2 ** attempt))
                        continue
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "rate_limit",
                            "message": f"HTTP 429 Too Many Requests; retry_after={retry_after}",
                        },
                    }

                if 500 <= status < 600:
                    if attempt < max_retries:
                        time.sleep(backoff * (2 ** attempt))
                        continue
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "server_error",
                            "message": f"HTTP {status}",
                        },
                    }

                try:
                    data = json.loads(body)
                except json.JSONDecodeError as exc:
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "malformed_json",
                            "message": str(exc),
                        },
                    }

                if not _is_valid_payload(data):
                    return {
                        "ok": False,
                        "error": {
                            "url": url,
                            "type": "incomplete_data",
                            "message": "Expected keys: station, reading",
                        },
                    }

                return {"ok": True, "reading": data}

        except error.HTTPError as exc:
            if exc.code == 429:
                retry_after = _parse_retry_after(exc.headers.get("Retry-After"))
                if attempt < max_retries:
                    time.sleep(retry_after if retry_after is not None else backoff * (2 ** attempt))
                    continue
                return {
                    "ok": False,
                    "error": {
                        "url": url,
                        "type": "rate_limit",
                        "message": f"HTTP 429 Too Many Requests; retry_after={retry_after}",
                    },
                }

            if 500 <= exc.code < 600:
                if attempt < max_retries:
                    time.sleep(backoff * (2 ** attempt))
                    continue
                return {
                    "ok": False,
                    "error": {
                        "url": url,
                        "type": "server_error",
                        "message": f"HTTP {exc.code}",
                    },
                }

            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "http_error",
                    "message": f"HTTP {exc.code}: {exc.reason}",
                },
            }

        except error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError):
                if attempt < max_retries:
                    time.sleep(backoff * (2 ** attempt))
                    continue
                return {
                    "ok": False,
                    "error": {
                        "url": url,
                        "type": "timeout",
                        "message": str(exc),
                    },
                }

            last_error = {
                "url": url,
                "type": "network_error",
                "message": str(exc),
            }
            if attempt < max_retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            return {"ok": False, "error": last_error}

        except TimeoutError as exc:
            if attempt < max_retries:
                time.sleep(backoff * (2 ** attempt))
                continue
            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "timeout",
                    "message": str(exc),
                },
            }

        except Exception as exc:
            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "unexpected_error",
                    "message": str(exc),
                },
            }

    return {"ok": False, "error": last_error or {"url": url, "type": "unknown_error", "message": "Unknown failure"}}


def fetch_all_stations(urls: list[str]) -> dict:
    readings: list[dict] = []
    errors: list[dict] = []

    for url in urls:
        result = _fetch_one(url)
        if result["ok"]:
            readings.append(result["reading"])
        else:
            errors.append(result["error"])

    return {"readings": readings, "errors": errors}


def main() -> None:
    example_urls = [
        "https://example.com/station/ok-1",
        "https://example.com/station/server-error",
        "https://example.com/station/timeout",
        "https://example.com/station/malformed-json",
        "https://example.com/station/incomplete-json",
        "https://example.com/station/rate-limited",
        "https://example.com/station/ok-2",
    ]

    original_fetch_one = _fetch_one

    simulated_state = {"rate_limit_attempts": 0}

    def simulated_fetch_one(url: str, max_retries: int = 3, timeout: float = 2.0, backoff: float = 0.5) -> dict:
        if url.endswith("ok-1"):
            return {"ok": True, "reading": {"station": "ok-1", "reading": 21.4}}
        if url.endswith("ok-2"):
            return {"ok": True, "reading": {"station": "ok-2", "reading": 19.8}}
        if url.endswith("server-error"):
            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "server_error",
                    "message": "HTTP 503 after retries",
                },
            }
        if url.endswith("timeout"):
            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "timeout",
                    "message": "Request timed out after retries",
                },
            }
        if url.endswith("malformed-json"):
            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "malformed_json",
                    "message": "Expecting value: line 1 column 1 (char 0)",
                },
            }
        if url.endswith("incomplete-json"):
            return {
                "ok": False,
                "error": {
                    "url": url,
                    "type": "incomplete_data",
                    "message": "Expected keys: station, reading",
                },
            }
        if url.endswith("rate-limited"):
            simulated_state["rate_limit_attempts"] += 1
            if simulated_state["rate_limit_attempts"] < 2:
                time.sleep(0.1)
            return {"ok": True, "reading": {"station": "rate-limited", "reading": 22.1}}
        return original_fetch_one(url, max_retries=max_retries, timeout=timeout, backoff=backoff)

    globals()["_fetch_one"] = simulated_fetch_one
    try:
        result = fetch_all_stations(example_urls)
    finally:
        globals()["_fetch_one"] = original_fetch_one

    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("Errors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()