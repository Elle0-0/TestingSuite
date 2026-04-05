import asyncio
import aiohttp
import time
import json
from typing import Any


async def fetch_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    max_retries: int = 3,
    base_delay: float = 1.0,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Fetch a single station URL with retry logic and exponential backoff."""
    last_exception = None

    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    data = await response.json()
                    return {"url": url, "success": True, "data": data}
                elif response.status == 429:
                    # Rate limited - respect Retry-After header if present
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        delay = float(retry_after)
                    else:
                        delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(f"Rate limited (429) at {url}")
                    continue
                elif response.status >= 500:
                    # Server error - retry with backoff
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    last_exception = Exception(
                        f"Server error {response.status} at {url}"
                    )
                    continue
                else:
                    # Client error (4xx except 429) - don't retry
                    text = await response.text()
                    return {
                        "url": url,
                        "success": False,
                        "error": f"HTTP {response.status}: {text[:200]}",
                    }
        except asyncio.TimeoutError:
            delay = base_delay * (2 ** attempt)
            last_exception = Exception(f"Timeout fetching {url}")
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
        except aiohttp.ClientError as e:
            delay = base_delay * (2 ** attempt)
            last_exception = e
            if attempt < max_retries - 1:
                await asyncio.sleep(delay)
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)

    return {
        "url": url,
        "success": False,
        "error": f"Failed after {max_retries} retries: {last_exception}",
    }


async def fetch_station(
    semaphore: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    url: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    """Fetch a station with concurrency limiting via semaphore."""
    async with semaphore:
        return await fetch_with_retry(session, url, max_retries=max_retries)


async def _fetch_all_stations_async(
    urls: list[str], max_concurrent: int = 10
) -> dict[str, Any]:
    """Internal async implementation of fetch_all_stations."""
    semaphore = asyncio.Semaphore(max_concurrent)
    readings = {}
    errors = {}

    connector = aiohttp.TCPConnector(limit=max_concurrent, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.create_task(fetch_station(semaphore, session, url))
            for url in urls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                # Task itself raised an unhandled exception
                errors["unknown"] = str(result)
            elif result["success"]:
                readings[result["url"]] = result["data"]
            else:
                errors[result["url"]] = result["error"]

    return {"readings": readings, "errors": errors}


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict[str, Any]:
    """
    Fetch data from multiple station URLs concurrently.

    Returns a dict with:
        - "readings": dict mapping URL to response data for successful fetches
        - "errors": dict mapping URL to error message for failed fetches
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're already in an async context; create a new thread to run
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run, _fetch_all_stations_async(urls, max_concurrent)
            )
            return future.result()
    else:
        return asyncio.run(_fetch_all_stations_async(urls, max_concurrent))


def main():
    """Demonstrate the solution with a large list of example URLs."""
    # Generate a large list of example station URLs
    base_urls = [
        "https://httpbin.org/json",
        "https://httpbin.org/delay/1",
        "https://httpbin.org/status/200",
        "https://httpbin.org/get",
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/404",
        "https://httpbin.org/status/429",
    ]

    # Create a larger set of URLs to demonstrate scale
    urls = []
    for i in range(50):
        url = base_urls[i % len(base_urls)]
        # Add query param to make URLs unique
        separator = "&" if "?" in url else "?"
        urls.append(f"{url}{separator}station={i}")

    print(f"Fetching data from {len(urls)} stations...")
    print(f"Max concurrent requests: 10")
    print("-" * 60)

    start_time = time.time()
    results = fetch_all_stations(urls, max_concurrent=10)
    elapsed = time.time() - start_time

    successful = len(results["readings"])
    failed = len(results["errors"])

    print(f"\nResults Summary:")
    print(f"  Total stations: {len(urls)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total elapsed time: {elapsed:.2f} seconds")
    print()

    if results["readings"]:
        print("Sample successful readings (first 3):")
        for i, (url, data) in enumerate(results["readings"].items()):
            if i >= 3:
                break
            data_str = json.dumps(data, indent=2)
            if len(data_str) > 200:
                data_str = data_str[:200] + "..."
            print(f"  {url}:")
            print(f"    {data_str}")
        print()

    if results["errors"]:
        print("Sample errors (first 5):")
        for i, (url, error) in enumerate(results["errors"].items()):
            if i >= 5:
                break
            print(f"  {url}: {error}")
        print()

    # Demonstrate the time improvement
    if len(urls) > 0:
        avg_time = elapsed / len(urls)
        print(f"Average time per station: {avg_time:.3f} seconds")
        print(
            f"(With concurrent fetching, this is much faster than "
            f"sequential which would take ~{len(urls) * 1.0:.0f}+ seconds)"
        )


if __name__ == "__main__":
    main()