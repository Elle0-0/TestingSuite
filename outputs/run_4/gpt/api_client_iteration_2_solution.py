import json
import time
from urllib import request, error
from urllib.parse import urlparse, parse_qs


class FetchError(Exception):
    pass


class TemporaryServerError(FetchError):
    pass


class MalformedResponseError(FetchError):
    pass


class IncompleteResponseError(FetchError):
    pass


class TimeoutFetchError(FetchError):
    pass


class RateLimitError(FetchError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def _simulate_request(url: str):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    mode = params.get("mode", ["ok"])[0]
    station = params.get("station", ["unknown"])[0]
    attempt = int(params.get("attempt", ["1"])[0])

    if mode == "ok":
        return 200, json.dumps(
            {"station": station, "temperature": 21.5, "humidity": 48}
        ), {}

    if mode == "server_error":
        if attempt < 3:
            return 503, json.dumps({"error": "temporary outage"}), {}
        return 200, json.dumps(
            {"station": station, "temperature": 19.8, "humidity": 55}
        ), {}

    if mode == "timeout":
        raise TimeoutError("request timed out")

    if mode == "malformed":
        return 200, '{"station": "bad-json", "temperature": ', {}

    if mode == "incomplete":
        return 200, json.dumps({"station": station, "temperature": 18.2}), {}

    if mode == "rate_limit":
        if attempt < 2:
            return 429, json.dumps({"error": "too many requests"}), {"Retry-After": "1"}
        return 200, json.dumps(
            {"station": station, "temperature": 17.3, "humidity": 61}
        ), {}

    return 500, json.dumps({"error": "unknown simulation mode"}), {}


def _real_request(url: str, timeout: float = 2.0):
    with request.urlopen(url, timeout=timeout) as resp:
        status = getattr(resp, "status", resp.getcode())
        body = resp.read().decode("utf-8", errors="replace")
        headers = dict(resp.headers.items())
        return status, body, headers


def _request_url(url: str, timeout: float = 2.0):
    if url.startswith("simulate://"):
        return _simulate_request(url)
    try:
        return _real_request(url, timeout=timeout)
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        headers = dict(e.headers.items()) if e.headers else {}
        return e.code, body, headers
    except error.URLError as e:
        reason = getattr(e, "reason", None)
        if isinstance(reason, TimeoutError):
            raise TimeoutFetchError(str(reason))
        raise FetchError(str(e))
    except TimeoutError as e:
        raise TimeoutFetchError(str(e))


def _parse_reading(body: str):
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise MalformedResponseError(str(e))

    required = ["station", "temperature", "humidity"]
    missing = [k for k in required if k not in data]
    if missing:
        raise IncompleteResponseError(f"missing fields: {', '.join(missing)}")
    return data


def _fetch_station_with_retries(url: str, max_retries: int = 3, timeout: float = 2.0):
    last_error = None

    for attempt in range(1, max_retries + 1):
        actual_url = url
        separator = "&" if "?" in url else "?"
        actual_url = f"{url}{separator}attempt={attempt}"

        try:
            status, body, headers = _request_url(actual_url, timeout=timeout)

            if status == 429:
                retry_after_raw = headers.get("Retry-After", "1")
                try:
                    retry_after = float(retry_after_raw)
                except ValueError:
                    retry_after = 1.0
                if attempt < max_retries:
                    time.sleep(retry_after)
                    continue
                raise RateLimitError("rate limited", retry_after=retry_after)

            if 500 <= status < 600:
                if attempt < max_retries:
                    time.sleep(min(2 ** (attempt - 1), 4))
                    continue
                raise TemporaryServerError(f"server error status {status}")

            if not (200 <= status < 300):
                raise FetchError(f"unexpected status {status}")

            return _parse_reading(body)

        except TimeoutFetchError as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(min(2 ** (attempt - 1), 4))
                continue
            raise
        except (MalformedResponseError, IncompleteResponseError, FetchError) as e:
            last_error = e
            raise
        except Exception as e:
            last_error = e
            raise FetchError(str(e))

    if last_error:
        raise last_error
    raise FetchError("unknown failure")


def fetch_all_stations(urls: list[str]) -> dict:
    readings = []
    errors = []

    for url in urls:
        try:
            reading = _fetch_station_with_retries(url)
            readings.append(reading)
        except Exception as e:
            errors.append(
                {
                    "url": url,
                    "error_type": e.__class__.__name__,
                    "message": str(e),
                }
            )

    return {"readings": readings, "errors": errors}


def main():
    urls = [
        "simulate://station?station=alpha&mode=ok",
        "simulate://station?station=bravo&mode=server_error",
        "simulate://station?station=charlie&mode=rate_limit",
        "simulate://station?station=delta&mode=timeout",
        "simulate://station?station=echo&mode=malformed",
        "simulate://station?station=foxtrot&mode=incomplete",
    ]

    result = fetch_all_stations(urls)

    print("Readings:")
    print(json.dumps(result["readings"], indent=2))
    print("\nErrors:")
    print(json.dumps(result["errors"], indent=2))


if __name__ == "__main__":
    main()