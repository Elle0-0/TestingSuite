import json
import time
import requests
import concurrent.futures

class ServiceException(Exception):
    pass

def fetch_station_data(url: str, max_retries: int = 3, delay: int = 2) -> dict:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=3.05)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "MAINTENANCE" or data.get("status") == "DOWN":
                raise ServiceException(
                    f"Service for {url} is unavailable: {data.get('status')}"
                )

            return data
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise e
        except ServiceException:
            raise

def fetch_all_stations(urls: list[str], max_concurrent: int = 10) -> dict:
    results = {"readings": [], "errors": []}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        future_to_url = {executor.submit(fetch_station_data, url): url for url in urls}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results["readings"].append(data)
            except Exception as exc:
                results["errors"].append({"url": url, "error": str(exc)})
    
    return results

def main():
    base_url = "https://raw.githubusercontent.com/prijatelj/py-testing-primer-api/main/station"
    station_ids = list(range(1, 21))
    
    urls = [f"{base_url}_{i:02d}.json" for i in station_ids]
    
    # Add some known problematic URLs
    urls.extend([
        f"{base_url}_maintenance.json",
        f"{base_url}_down.json",
        "https://httpbin.org/delay/4",  # A slow URL
        "https://httpbin.org/status/500", # An error status
        "http://this.does.not.exist.domain/data.json" # A DNS error
    ] * 2) # Duplicate to increase load
    
    print(f"Fetching data from {len(urls)} stations...\n")
    
    start_time = time.perf_counter()
    
    station_data = fetch_all_stations(urls, max_concurrent=15)
    
    end_time = time.perf_counter()
    
    print(json.dumps(station_data, indent=2))
    
    elapsed_time = end_time - start_time
    print(f"\nTotal execution time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()