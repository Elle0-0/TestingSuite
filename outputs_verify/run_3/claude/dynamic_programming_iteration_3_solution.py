import random
import time
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find optimal route visiting all monitoring stations within time windows.
    
    Uses bitmask DP for TSP-like optimization.
    
    Parameters:
        cost_matrix: 2D list of travel costs/distances between stations
        time_windows: list of (earliest, latest) tuples for each station
        inspection_time: time spent at each station (scalar or list)
        speed: travel speed factor
    
    Returns:
        dict with 'route', 'total_cost', 'arrival_times', 'feasible'
    """
    n = len(cost_matrix)
    
    if isinstance(inspection_time, (int, float)):
        insp_times = [inspection_time] * n
    else:
        insp_times = list(inspection_time)
    
    # Compute travel times from cost matrix and speed
    travel_time = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if speed > 0:
                travel_time[i][j] = cost_matrix[i][j] / speed
            else:
                travel_time[i][j] = cost_matrix[i][j]
    
    # Bitmask DP
    # State: (current_station, visited_mask) -> (min_cost, earliest_finish_time)
    # We want to visit all stations starting from station 0
    
    full_mask = (1 << n) - 1
    
    # dp[mask][i] = (min_cost, earliest_completion_time_at_i, parent_mask, parent_station)
    # We'll use a dict-based approach for states
    
    INF = float('inf')
    
    # dp[mask][i] = (best_cost, arrival_time_at_i, completion_time_at_i)
    # Using arrays for speed
    dp_cost = [[INF] * n for _ in range(1 << n)]
    dp_arrival = [[0.0] * n for _ in range(1 << n)]
    dp_completion = [[0.0] * n for _ in range(1 << n)]
    dp_parent = [[(-1, -1)] * n for _ in range(1 << n)]  # (prev_mask, prev_station)
    
    # Start at station 0
    start_mask = 1 << 0
    earliest_0, latest_0 = time_windows[0]
    arrival_0 = earliest_0  # arrive at earliest possible time
    if arrival_0 > latest_0:
        return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    completion_0 = arrival_0 + insp_times[0]
    dp_cost[start_mask][0] = 0  # cost so far (travel cost)
    dp_arrival[start_mask][0] = arrival_0
    dp_completion[start_mask][0] = completion_0
    
    # Process masks in order of number of bits
    for mask in range(1, 1 << n):
        for last in range(n):
            if not (mask & (1 << last)):
                continue
            if dp_cost[mask][last] == INF:
                continue
            
            curr_cost = dp_cost[mask][last]
            curr_completion = dp_completion[mask][last]
            
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                
                new_mask = mask | (1 << nxt)
                tt = travel_time[last][nxt]
                tc = cost_matrix[last][nxt]
                
                arrival = curr_completion + tt
                earliest_nxt, latest_nxt = time_windows[nxt]
                
                # Wait if arriving early
                actual_start = max(arrival, earliest_nxt)
                
                # Check if we can start before the window closes
                if actual_start > latest_nxt:
                    continue
                
                completion = actual_start + insp_times[nxt]
                new_cost = curr_cost + tc
                
                # We prefer lower cost; if tied, prefer earlier completion
                if new_cost < dp_cost[new_mask][nxt] or \
                   (new_cost == dp_cost[new_mask][nxt] and completion < dp_completion[new_mask][nxt]):
                    dp_cost[new_mask][nxt] = new_cost
                    dp_arrival[new_mask][nxt] = arrival
                    dp_completion[new_mask][nxt] = completion
                    dp_parent[new_mask][nxt] = (mask, last)
    
    # Find the best final state (all stations visited)
    best_cost = INF
    best_last = -1
    
    for last in range(n):
        if dp_cost[full_mask][last] < best_cost:
            best_cost = dp_cost[full_mask][last]
            best_last = last
    
    if best_last == -1:
        # Try to find best partial route
        best_partial_mask = 0
        best_partial_cost = INF
        best_partial_last = -1
        best_partial_count = 0
        
        for mask in range(1, 1 << n):
            cnt = bin(mask).count('1')
            for last in range(n):
                if not (mask & (1 << last)):
                    continue
                if dp_cost[mask][last] == INF:
                    continue
                if cnt > best_partial_count or (cnt == best_partial_count and dp_cost[mask][last] < best_partial_cost):
                    best_partial_count = cnt
                    best_partial_cost = dp_cost[mask][last]
                    best_partial_mask = mask
                    best_partial_last = last
        
        if best_partial_last == -1:
            return {'route': [0], 'total_cost': 0, 'arrival_times': [time_windows[0][0]], 'feasible': False}
        
        # Reconstruct partial route
        route = []
        arrivals = []
        mask = best_partial_mask
        last = best_partial_last
        
        while last != -1:
            route.append(last)
            arrivals.append(dp_arrival[mask][last])
            prev_mask, prev_last = dp_parent[mask][last]
            mask = prev_mask
            last = prev_last
        
        route.reverse()
        arrivals.reverse()
        
        return {
            'route': route,
            'total_cost': best_partial_cost,
            'arrival_times': arrivals,
            'feasible': False
        }
    
    # Reconstruct route
    route = []
    arrivals = []
    mask = full_mask
    last = best_last
    
    while last != -1:
        route.append(last)
        arrivals.append(dp_arrival[mask][last])
        prev_mask, prev_last = dp_parent[mask][last]
        mask = prev_mask
        last = prev_last
    
    route.reverse()
    arrivals.reverse()
    
    return {
        'route': route,
        'total_cost': best_cost,
        'arrival_times': arrivals,
        'feasible': True
    }


def main():
    random.seed(42)
    n = 15
    
    # Generate random cost matrix (symmetric, no self-loops)
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = random.uniform(5, 50)
            cost_matrix[i][j] = round(c, 2)
            cost_matrix[j][i] = round(c, 2)
    
    # Generate time windows - make them wide enough to be feasible
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 100)
        latest = earliest + random.uniform(100, 300)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Sort station 0's window to start at 0
    time_windows[0] = (0, time_windows[0][1] + 200)
    
    inspection_time = 5.0
    speed = 1.0
    
    print(f"Solving TSP with time windows for {n} stations...")
    print(f"Time windows: {time_windows[:5]}... (showing first 5)")
    
    start_time = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start_time
    
    print(f"\nResult:")
    print(f"  Feasible: {result['feasible']}")
    print(f"  Route: {result['route']}")
    print(f"  Total cost: {result['total_cost']:.2f}")
    print(f"  Arrival times: {[f'{t:.2f}' for t in result['arrival_times']]}")
    print(f"  Stations visited: {len(result['route'])}")
    print(f"\nElapsed time: {elapsed:.3f} seconds")


if __name__ == "__main__":
    main()