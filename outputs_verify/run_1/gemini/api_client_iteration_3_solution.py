import concurrent.futures
import requests
import time
import pprint

MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 0.1
FORBIDDEN_STATUS_CODE = 403


class Station:
    """Represents a single weather station API endpoint."""

    def __init__(self, url: str):
        """Initializes a Station with a specific URL."""
        self.url = url

    def fetch(self) -> tuple[bool, dict | str]:
        """
        Fetches data from the station's URL with a retry mechanism.

        Returns:
            A tuple containing:
            - A boolean indicating success.
            - The JSON data as a dict if successful, or an error message string.
        """
        last_error_message = "No attempts made."
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(self.url, timeout=5)

                if response.status_code == FORBIDDEN_STATUS_CODE:
                    return False, f"Access forbidden. Service restriction at {self.url}."

                response.raise_for_status()
                return True, response.json()

            except requests.exceptions.HTTPError as e:
                last_error_message = f"HTTP Error: {e.response.status_code} on attempt {attempt + 1}"
            except requests.exceptions.RequestException as e:
                last_error_message = f"Request failed: {type(e).__name__} on attempt {attempt + 1}"

            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_FACTOR * (2 ** attempt))

        return False, f"Failed to fetch from {self.url} after {MAX_RETRIES} attempts. Last error: {last_error_message}"


def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    """
    Fetches data from a list of station URLs concurrently.

    Args:
        urls: A list of station URL strings.
        max_concurrent: The maximum number of concurrent requests.

    Returns:
        A dictionary with "readings" and "errors" keys, summarizing
        the results from all stations.
    """
    results = {"readings": {}, "errors": {}}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {executor.submit(Station(url).fetch): url for url in urls}

        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                success, data = future.result()
                if success:
                    results["readings"][url] = data
                else:
                    results["errors"][url] = data
            except Exception as exc:
                results["errors"][url] = f"An unexpected error occurred during fetch: {exc}"

    return results


def main():
    """
    Demonstrates the concurrent station data fetching solution.
    """
    # A larger list of example URLs to demonstrate scale
    station_urls = [
        # Successful requests
        "https://httpbin.org/json",
        "https://httpbin.org/get?station=alpha",
        "https://httpbin.org/get?station=beta",
        "https://httpbin.org/get?station=gamma",
        "https://httpbin.org/get?station=delta",

        # Slow requests
        "https://httpbin.org/delay/2",
        "https://httpbin.org/delay/3",

        # Requests that will fail and be retried
        "https://httpbin.org/status/500",
        "https://httpbin.org/status/502",
        "https://httpbin.org/status/503",

        # Requests that will fail without retry (4xx)
        "https://httpbin.org/status/404",
        "https://httpbin.org/status/418",

        # Request that is forbidden and will not be retried
        "https://httpbin.org/status/403",

        # Request that will time out
        "https://httpbin.org/delay/6",

        # Requests that will fail due to connection errors
        "http://this-is-not-a-real-domain.org/data",
        "https://invalid.url.that.does.not.exist",

        # More successful requests to pad the list
        "https://httpbin.org/get?station=epsilon",
        "https://httpbin.org/get?station=zeta",
        "https://httpbin.org/get?station=eta",
        "https://httpbin.org/get?station=theta",
    ]

    print(f"Fetching data from {len(station_urls)} stations concurrently...")
    start_time = time.monotonic()

    # Using a higher concurrency level for the larger list
    all_data = fetch_all_stations(station_urls, max_concurrent=10)

    end_time = time.monotonic()
    elapsed_time = end_time - start_time

    print("\n--- Fetching Complete ---\n")
    print("Collected Readings:")
    pprint.pprint(all_data["readings"])
    print("\nReported Errors:")
    pprint.pprint(all_data["errors"])
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds.")


if __name__ == "__main__":
    main()