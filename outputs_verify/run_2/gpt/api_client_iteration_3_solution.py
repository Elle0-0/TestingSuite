import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


DEFAULT_TIMEOUT = 1.5
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.2


def simulated_station_request(url: str, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
    start = time.perf_counter()

    if "forbidden" in url:
        time.sleep(0.05)
        raise PermissionError("403 Forbidden")

    if "notfound" in url:
        time.sleep(0.05)
        raise FileNotFoundError("404 Not Found")

    if "unstable" in url:
        delay = random.uniform(0.05, 1.0)
        time.sleep(delay)
        if random.random() < 0.5:
            raise ConnectionError("Transient network failure")
        return {
            "station": url,
            "value": round(random.uniform(10, 100), 2),
            "unit": "kWh",
            "latency_s": round(time.perf_counter() - start, 3),
        }

    if "slow" in url:
        delay = random.uniform(timeout * 0.8, timeout * 1.8)
        time.sleep(min(delay, timeout + 0.2))
        if delay > timeout:
            raise TimeoutError(f"Request timed out after {timeout:.1f}s")
        return {
            "station": url,
            "value": round(random.uniform(10, 100), 2),
            "unit": "kWh",
            "latency_s": round(time.perf_counter() - start, 3),
        }

    if "flaky" in url:
        delay = random.uniform(0.05, 0.4)
        time.sleep(delay)
        roll = random.random()
        if roll < 0.25:
            raise TimeoutError(f"Request timed out after {timeout:.1f}s")
        if roll < 0.5:
            raise ConnectionError("Temporary upstream error")
        return {
            "station": url,
            "value": round(random.uniform(10, 100), 2),
            "unit": "kWh",
            "latency_s": round(time.perf_counter() - start, 3),
        }

    delay = random.uniform(0.05, 0.3)
    time.sleep(delay)
    return {
        "station": url,
        "value": round(random.uniform(10, 100), 2),
        "unit": "kWh",
        "latency_s": round(time.perf_counter() - start, 3),
    }


def fetch_station(
    url: str,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
    backoff_base: float = DEFAULT_BACKOFF_BASE,
) -> tuple[bool, dict[str, Any]]:
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            data = simulated_station_request(url, timeout=timeout)
            return True, data
        except (PermissionError, FileNotFoundError) as exc:
            return False, {
                "station": url,
                "error": str(exc),
                "type": exc.__class__.__name__,
                "attempts": attempt,
                "retryable": False,
            }
        except (TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt < retries:
                sleep_for = backoff_base * (2 ** (attempt - 1))
                time.sleep(sleep_for)
            else:
                return False, {
                    "station": url,
                    "error": str(last_error),
                    "type": last_error.__class__.__name__,
                    "attempts": attempt,
                    "retryable": True,
                }
        except Exception as exc:
            return False, {
                "station": url,
                "error": str(exc),
                "type": exc.__class__.__name__,
                "attempts": attempt,
                "retryable": False,
            }

    return False, {
        "station": url,
        "error": str(last_error) if last_error else "Unknown failure",
        "type": last_error.__class__.__name__ if last_error else "UnknownError",
        "attempts": retries,
        "retryable": True,
    }


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    readings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {executor.submit(fetch_station, url): url for url in urls}

        for future in as_completed(future_to_url):
            success, payload = future.result()
            with lock:
                if success:
                    readings.append(payload)
                else:
                    errors.append(payload)

    readings.sort(key=lambda x: x["station"])
    errors.sort(key=lambda x: x["station"])

    return {
        "readings": readings,
        "errors": errors,
    }


def build_example_urls(count: int = 60) -> list[str]:
    urls = []
    patterns = [
        "ok",
        "ok",
        "ok",
        "unstable",
        "flaky",
        "slow",
        "forbidden",
        "notfound",
    ]
    for i in range(count):
        kind = patterns[i % len(patterns)]
        urls.append(f"https://api.example.com/stations/{kind}/{i:03d}")
    random.shuffle(urls)
    return urls


def main() -> None:
    random.seed(42)
    urls = build_example_urls(80)

    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print(json.dumps(result, indent=2))
    print(f"Total elapsed time: {elapsed:.3f}s")
    print(f"Successful readings: {len(result['readings'])}")
    print(f"Errors: {len(result['errors'])}")


if __name__ == "__main__":
    main()