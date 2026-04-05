import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs


class TemporaryError(Exception):
    pass


class PermanentError(Exception):
    pass


def mock_fetch_station(url: str) -> dict:
    parsed = urlparse(url)
    station_id = parsed.path.rstrip("/").split("/")[-1] or "unknown"
    params = parse_qs(parsed.query)

    if "delay" in params:
        try:
            delay = float(params["delay"][0])
        except (ValueError, TypeError):
            delay = 0.1
    else:
        delay = random.uniform(0.05, 0.4)

    time.sleep(delay)

    mode = params.get("mode", ["ok"])[0]

    if mode == "ok":
        value = params.get("value", [None])[0]
        if value is None:
            reading = round(random.uniform(10.0, 99.9), 2)
        else:
            reading = float(value)
        return {"station": station_id, "reading": reading}

    if mode == "temporary":
        raise TemporaryError(f"temporary failure from {station_id}")

    if mode == "flaky":
        fail_count = int(params.get("failures", ["1"])[0])
        counter = int(params.get("attempt", ["0"])[0])
        if counter < fail_count:
            raise TemporaryError(f"flaky temporary failure from {station_id}")
        value = round(random.uniform(10.0, 99.9), 2)
        return {"station": station_id, "reading": value}

    if mode == "permanent":
        raise PermanentError(f"permanent failure from {station_id}")

    if mode == "restricted":
        raise PermanentError(f"service restriction for {station_id}")

    raise PermanentError(f"unknown mode for {station_id}")


def fetch_station_with_retries(url: str, max_retries: int = 3, backoff_base: float = 0.1) -> tuple[str, dict | None, dict | None]:
    parsed = urlparse(url)
    station_id = parsed.path.rstrip("/").split("/")[-1] or url
    params = parse_qs(parsed.query)

    mode = params.get("mode", ["ok"])[0]
    fail_count = int(params.get("failures", ["0"])[0])

    for attempt in range(1, max_retries + 2):
        try:
            effective_url = url
            if mode == "flaky":
                sep = "&" if "?" in url else "?"
                effective_url = f"{url}{sep}attempt={attempt - 1}"
            result = mock_fetch_station(effective_url)
            return station_id, result, None
        except TemporaryError as exc:
            if attempt > max_retries:
                return station_id, None, {"type": "temporary", "message": str(exc), "attempts": attempt}
            time.sleep(backoff_base * (2 ** (attempt - 1)))
        except PermanentError as exc:
            return station_id, None, {"type": "permanent", "message": str(exc), "attempts": attempt}
        except Exception as exc:
            return station_id, None, {"type": "unexpected", "message": str(exc), "attempts": attempt}

    return station_id, None, {"type": "temporary", "message": f"failed after {max_retries + 1} attempts", "attempts": max_retries + 1}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    readings = {}
    errors = {}
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {executor.submit(fetch_station_with_retries, url): url for url in urls}

        for future in as_completed(future_to_url):
            station_id, reading_result, error_result = future.result()
            with lock:
                if reading_result is not None:
                    readings[station_id] = reading_result["reading"]
                if error_result is not None:
                    errors[station_id] = error_result

    return {"readings": readings, "errors": errors}


def build_example_urls(count: int = 50) -> list[str]:
    urls = []
    for i in range(1, count + 1):
        station = f"station-{i:03d}"

        if i % 11 == 0:
            urls.append(f"https://api.example.com/stations/{station}?mode=permanent&delay=0.15")
        elif i % 9 == 0:
            urls.append(f"https://api.example.com/stations/{station}?mode=restricted&delay=0.05")
        elif i % 7 == 0:
            urls.append(f"https://api.example.com/stations/{station}?mode=temporary&delay=0.25")
        elif i % 5 == 0:
            failures = 1 if i % 10 else 2
            urls.append(f"https://api.example.com/stations/{station}?mode=flaky&failures={failures}&delay=0.12")
        else:
            value = round(20 + (i * 1.37) % 50, 2)
            delay = round(0.03 + (i % 6) * 0.04, 2)
            urls.append(f"https://api.example.com/stations/{station}?mode=ok&value={value}&delay={delay}")
    return urls


def main():
    urls = build_example_urls(60)
    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print("Readings:")
    for station in sorted(result["readings"]):
        print(f"  {station}: {result['readings'][station]}")

    print("\nErrors:")
    for station in sorted(result["errors"]):
        print(f"  {station}: {result['errors'][station]}")

    print(f"\nTotal stations: {len(urls)}")
    print(f"Successful readings: {len(result['readings'])}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Elapsed time: {elapsed:.3f}s")


if __name__ == "__main__":
    main()