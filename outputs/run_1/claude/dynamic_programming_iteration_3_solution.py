import random
import time
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find the optimal route through monitoring stations using bitmask DP.
    
    Parameters:
    - cost_matrix: NxN matrix of travel costs/distances between stations
    - time_windows: list of (earliest, latest) tuples for each station
    - inspection_time: time spent at each station (scalar or list)
    - speed: travel speed (distance/time)
    
    Returns:
    - dict with 'route', 'cost', 'arrival_times', and 'feasible' keys
    """
    n = len(cost_matrix)
    
    if isinstance(inspection_time, (int, float)):
        insp = [inspection_time] * n
    else:
        insp = list(inspection_time)
    
    # Precompute travel times
    travel_time = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if speed > 0 and i != j:
                travel_time[i][j] = cost_matrix[i][j] / speed
            else:
                travel_time[i][j] = 0.0
    
    # Bitmask DP
    # State: (current_station, visited_mask) -> (min_cost, arrival_time)
    # We start from station 0
    
    full_mask = (1 << n) - 1
    
    # dp[mask][i] = (min_cost, current_time) to have visited exactly the stations in mask,
    # currently at station i, with the ability to continue
    INF = float('inf')
    
    # Use dictionaries for sparse states or arrays for dense
    # For n<=20, 2^20 * 20 = ~20M entries, manageable with arrays
    
    dp_cost = [[INF] * n for _ in range(1 << n)]
    dp_time = [[0.0] * n for _ in range(1 << n)]
    dp_parent = [[-1] * n for _ in range(1 << n)]
    
    # Start at station 0, time = earliest time window for station 0
    start_time = time_windows[0][0]
    if start_time <= time_windows[0][1]:
        dp_cost[1 << 0][0] = 0.0
        dp_time[1 << 0][0] = start_time + insp[0]
    
    best_cost = INF
    best_last = -1
    best_mask = -1
    
    for mask in range(1, 1 << n):
        for u in range(n):
            if dp_cost[mask][u] == INF:
                continue
            if not (mask & (1 << u)):
                continue
            
            current_cost = dp_cost[mask][u]
            current_time = dp_time[mask][u]
            
            # Try to go to station v
            for v in range(n):
                if mask & (1 << v):
                    continue
                
                new_mask = mask | (1 << v)
                arr_time = current_time + travel_time[u][v]
                
                # Wait until earliest time window if we arrive early
                earliest_v, latest_v = time_windows[v]
                effective_arrival = max(arr_time, earliest_v)
                
                # Check if we can arrive within the time window
                if effective_arrival > latest_v:
                    continue
                
                new_cost = current_cost + cost_matrix[u][v]
                depart_time = effective_arrival + insp[v]
                
                if new_cost < dp_cost[new_mask][v]:
                    dp_cost[new_mask][v] = new_cost
                    dp_time[new_mask][v] = depart_time
                    dp_parent[new_mask][v] = u
    
    # Find the best complete route (return to station 0) or best partial
    # First try full mask with return to 0
    best_cost = INF
    best_last = -1
    best_mask = full_mask
    
    for u in range(n):
        if dp_cost[full_mask][u] == INF:
            continue
        total_cost = dp_cost[full_mask][u] + cost_matrix[u][0]
        arr_back = dp_time[full_mask][u] + travel_time[u][0]
        if total_cost < best_cost:
            best_cost = total_cost
            best_last = u
            best_return_time = arr_back
    
    feasible = best_last != -1
    
    if not feasible:
        # Try without returning to 0, find best coverage
        best_visited_count = 0
        for mask in range(1, 1 << n):
            count = bin(mask).count('1')
            if count < best_visited_count:
                continue
            for u in range(n):
                if dp_cost[mask][u] == INF:
                    continue
                total = dp_cost[mask][u] + cost_matrix[u][0]
                if count > best_visited_count or (count == best_visited_count and total < best_cost):
                    best_visited_count = count
                    best_cost = total
                    best_last = u
                    best_mask = mask
                    best_return_time = dp_time[mask][u] + travel_time[u][0]
    
    # Reconstruct route
    if best_last == -1:
        return {
            'route': [0],
            'cost': 0,
            'arrival_times': [time_windows[0][0]],
            'feasible': False
        }
    
    route = []
    mask = best_mask
    u = best_last
    while u != -1:
        route.append(u)
        prev = dp_parent[mask][u]
        mask = mask ^ (1 << u)
        u = prev
    
    route.reverse()
    
    # Add return to start
    route.append(0)
    
    # Compute arrival times
    arrival_times = []
    current_time = time_windows[0][0]
    for i, station in enumerate(route):
        if i == 0:
            arrival_times.append(current_time)
            current_time += insp[station]
        else:
            prev_station = route[i - 1]
            arr = current_time + travel_time[prev_station][station]
            if station != 0 or i < len(route) - 1:
                effective = max(arr, time_windows[station][0])
            else:
                effective = arr
            arrival_times.append(effective)
            if i < len(route) - 1:
                current_time = effective + insp[station]
            else:
                current_time = effective
    
    return {
        'route': route,
        'cost': best_cost,
        'arrival_times': arrival_times,
        'feasible': feasible
    }


def main():
    random.seed(42)
    n = 15
    
    # Generate random cost matrix (symmetric)
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            cost = random.uniform(5, 50)
            cost_matrix[i][j] = round(cost, 2)
            cost_matrix[j][i] = round(cost, 2)
    
    # Generate time windows
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 50)
        latest = earliest + random.uniform(50, 200)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Sort station 0's time window to start at 0
    time_windows[0] = (0, time_windows[0][1] + 100)
    
    inspection_time = 2.0
    speed = 1.0
    
    print(f"Number of stations: {n}")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print()
    
    start = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start
    
    print(f"Route: {result['route']}")
    print(f"Cost: {result['cost']:.2f}")
    print(f"Feasible: {result['feasible']}")
    print(f"Arrival times: {[round(t, 2) for t in result['arrival_times']]}")
    print(f"Stations visited: {len(result['route']) - 1}")
    print(f"Elapsed time: {elapsed:.4f} seconds")


if __name__ == "__main__":
    main()