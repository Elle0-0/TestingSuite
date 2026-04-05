import asyncio
import json
from pprint import pprint

import aiohttp
from aiohttp import web

MAX_RETRIES = 4
BASE_RETRY_DELAY = 1
CLIENT_TIMEOUT_SECONDS = 5

async def _fetch_with_retries(session: aiohttp.ClientSession, url: str) -> dict:
    """Fetches a URL with retries for temporary failures."""
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            timeout = aiohttp.ClientTimeout(total=CLIENT_TIMEOUT_SECONDS)
            async with session.get(url, timeout=timeout) as response:
                # Handle rate limiting
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", BASE_RETRY_DELAY))
                    error_message = f"Rate limited. Retrying after {retry_after} seconds."
                    last_exception = aiohttp.ClientResponseError(response.request_info, response.history, status=response.status, message=error_message)
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise last_exception

                # Raise HTTPError for bad responses (4xx or 5xx)
                response.raise_for_status()

                # Handle malformed JSON
                data = await response.json()
                return data

        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                # Exponential backoff
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
            else:
                raise last_exception
    
    # This line should not be reachable if logic is correct, but as a fallback:
    raise last_exception or RuntimeError(f"All retries failed for {url}")

def fetch_all_stations(urls: list[str]) -> dict:
    """
    Fetches data from a list of URLs concurrently, handling failures and retries.
    """
    async def _run_fetch() -> dict:
        readings = []
        errors = []
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                asyncio.create_task(_fetch_with_retries(session, url))
                for url in urls
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for url, result in zip(urls, results):
                if isinstance(result, Exception):
                    errors.append({
                        "url": url,
                        "error_type": type(result).__name__,
                        "message": str(result)
                    })
                else:
                    readings.append(result)
        
        return {"readings": readings, "errors": errors}

    return asyncio.run(_run_fetch())

async def handle_ok(request: web.Request) -> web.Response:
    return web.json_response({"station_id": "station_ok", "status": "operational"})

async def handle_temp_fail(request: web.Request) -> web.Response:
    app_state = request.app['state']
    app_state['temp_fail_count'] = app_state.get('temp_fail_count', 0) + 1
    if app_state['temp_fail_count'] < 3:
        return web.Response(status=503, reason="Service Unavailable")
    return web.json_response({"station_id": "station_temp_fail", "status": "recovered"})

async def handle_timeout(request: web.Request) -> web.Response:
    await asyncio.sleep(CLIENT_TIMEOUT_SECONDS + 1)
    return web.json_response({"station_id": "station_timeout", "status": "delayed"}) # This will not be sent

async def handle_bad_json(request: web.Request) -> web.Response:
    return web.Response(text='{"station_id": "bad_json", "status": "malformed"', content_type="application/json")

async def handle_rate_limit(request: web.Request) -> web.Response:
    app_state = request.app['state']
    app_state['rate_limit_count'] = app_state.get('rate_limit_count', 0) + 1
    if app_state['rate_limit_count'] < 2:
        return web.Response(status=429, headers={"Retry-After": "1"})
    return web.json_response({"station_id": "station_rate_limit", "status": "accessible"})

async def main():
    """Sets up a mock server and demonstrates the API client."""
    app = web.Application()
    app['state'] = {}
    app.add_routes([
        web.get('/ok', handle_ok),
        web.get('/temp_fail', handle_temp_fail),
        web.get('/timeout', handle_timeout),
        web.get('/bad_json', handle_bad_json),
        web.get('/rate_limit', handle_rate_limit),
        web.get('/permanent_fail', lambda r: web.Response(status=404)),
    ])
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    base_url = "http://localhost:8080"
    urls_to_fetch = [
        f"{base_url}/ok",
        f"{base_url}/temp_fail",        # Should succeed after retries
        f"{base_url}/rate_limit",       # Should succeed after respecting Retry-After
        f"{base_url}/timeout",          # Should fail after retries
        f"{base_url}/bad_json",         # Should fail on first attempt
        f"{base_url}/permanent_fail",   # Should fail after retries
        f"{base_url}/nonexistent",      # Should fail with connection error
    ]

    print("Fetching station data...")
    results = fetch_all_stations(urls_to_fetch)
    
    print("\n--- Successful Readings ---")
    pprint(results["readings"])
    
    print("\n--- Error Reports ---")
    pprint(results["errors"])

    await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (aiohttp.ClientError, RuntimeError) as e:
        # This might catch server startup/shutdown issues
        print(f"An error occurred during execution: {e}")