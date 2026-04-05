import time
import random
import threading
from queue import Queue, Empty


MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.2
REQUEST_TIMEOUT_SECONDS = 1.5


def fetch_station_with_retries(url: str, max_retries: int = MAX_RETRIES, timeout: float = REQUEST_TIMEOUT_SECONDS) -> tuple[bool, dict]:
    attempt = 0
    last_error = None
    while attempt < max_retries:
        attempt += 1
        try:
            reading = simulate_station_request(url, timeout=timeout)
            return True, reading
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_retries:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    return False, {"url": url, "error": last_error or "unknown error", "attempts": attempt}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    if max_concurrent < 1:
        max_concurrent = 1

    readings = []
    errors = []
    results_lock = threading.Lock()
    work_queue = Queue()

    for url in urls:
        work_queue.put(url)

    def worker() -> None:
        while True:
            try:
                url = work_queue.get_nowait()
            except Empty:
                return
            try:
                ok, payload = fetch_station_with_retries(url)
                with results_lock:
                    if ok:
                        readings.append(payload)
                    else:
                        errors.append(payload)
            finally:
                work_queue.task_done()

    thread_count = min(max_concurrent, len(urls)) if urls else 0
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(thread_count)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    readings.sort(key=lambda x: x.get("station", ""))
    errors.sort(key=lambda x: x.get("url", ""))

    return {
        "readings": readings,
        "errors": errors,
    }


def simulate_station_request(url: str, timeout: float = REQUEST_TIMEOUT_SECONDS) -> dict:
    seed = hash(url) & 0xFFFFFFFF
    rng = random.Random(seed + int(time.time() // 60))

    if "forbidden" in url:
        raise PermissionError("service restriction: access denied")
    if "invalid" in url:
        raise ValueError("invalid station url")

    delay = rng.uniform(0.05, 2.5)
    if delay > timeout:
        time.sleep(timeout)
        raise TimeoutError(f"request timed out after {timeout:.1f}s")

    time.sleep(delay)

    failure_roll = rng.random()
    if "flaky" in url and failure_roll < 0.5:
        raise ConnectionError("temporary network failure")
    if "down" in url and failure_roll < 0.9:
        raise ConnectionError("station unavailable")
    if failure_roll < 0.05:
        raise ConnectionError("transient upstream error")

    station_name = url.rstrip("/").split("/")[-1] or "unknown"
    return {
        "station": station_name,
        "url": url,
        "temperature_c": round(rng.uniform(-10.0, 38.0), 1),
        "humidity_pct": round(rng.uniform(15.0, 95.0), 1),
        "status": "ok",
    }


def build_example_urls(count: int = 60) -> list[str]:
    urls = []
    for i in range(count):
        suffix = f"station-{i:03d}"
        if i % 17 == 0:
            suffix = f"forbidden-{suffix}"
        elif i % 13 == 0:
            suffix = f"invalid-{suffix}"
        elif i % 11 == 0:
            suffix = f"down-{suffix}"
        elif i % 7 == 0:
            suffix = f"flaky-{suffix}"
        urls.append(f"https://api.example.com/{suffix}")
    return urls


def main() -> None:
    urls = build_example_urls(80)
    start = time.perf_counter()
    result = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.perf_counter() - start

    print("Readings:")
    for item in result["readings"]:
        print(item)

    print("\nErrors:")
    for item in result["errors"]:
        print(item)

    print(f"\nTotal stations: {len(urls)}")
    print(f"Successful readings: {len(result['readings'])}")
    print(f"Errors: {len(result['errors'])}")
    print(f"Elapsed time: {elapsed:.3f}s")


if __name__ == "__main__":
    main()