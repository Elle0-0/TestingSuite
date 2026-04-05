import random
import time
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find the optimal route visiting all monitoring stations using bitmask DP.
    
    Parameters:
    - cost_matrix: 2D list of travel costs/distances between stations
    - time_windows: list of (earliest, latest) tuples for each station
    - inspection_time: time spent at each station (scalar or list)
    - speed: travel speed (distance/time)
    
    Returns:
    - dict with 'route', 'total_cost', 'arrival_times', 'feasible'
    """
    n = len(cost_matrix)
    
    if isinstance(inspection_time, (int, float)):
        insp = [inspection_time] * n
    else:
        insp = list(inspection_time)
    
    # Travel time between stations
    travel_time = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if speed > 0:
                travel_time[i][j] = cost_matrix[i][j] / speed
            else:
                travel_time[i][j] = float('inf')
    
    full_mask = (1 << n) - 1
    
    # dp[mask][i] = (min_cost, earliest_finish_time) to have visited exactly the stations
    # in mask, ending at station i, with the minimum cost (and among min cost, earliest finish)
    INF = float('inf')
    
    # Use dictionaries for sparse states, but with n<=20, we use arrays
    # dp[mask][i] = (cost, finish_time) or None
    # finish_time = time when inspection at station i is complete
    
    # For n up to 20, 2^20 * 20 = ~20M entries - feasible with careful implementation
    # Use arrays of floats
    
    dp_cost = [[INF] * n for _ in range(1 << n)]
    dp_time = [[INF] * n for _ in range(1 << n)]
    dp_parent = [[-1] * n for _ in range(1 << n)]
    
    # Initialize: start from each station (try station 0 as depot, or try all)
    # We'll assume station 0 is the starting depot
    start = 0
    earliest_0, latest_0 = time_windows[start]
    arrival_0 = earliest_0  # arrive at earliest possible time
    finish_0 = arrival_0 + insp[start]
    
    if arrival_0 <= latest_0:
        dp_cost[1 << start][start] = 0  # cost so far (travel cost, not including inspection)
        dp_time[1 << start][start] = finish_0
    
    # Try starting from any station if needed - let's try depot = 0
    # Process in order of popcount for correct DP ordering
    for mask in range(1, 1 << n):
        for u in range(n):
            if not (mask & (1 << u)):
                continue
            if dp_cost[mask][u] == INF:
                continue
            
            current_cost = dp_cost[mask][u]
            current_finish = dp_time[mask][u]
            
            for v in range(n):
                if mask & (1 << v):
                    continue
                
                new_mask = mask | (1 << v)
                tt = travel_time[u][v]
                tc = cost_matrix[u][v]
                
                arrival_v = current_finish + tt
                earliest_v, latest_v = time_windows[v]
                
                # Wait if arriving early
                actual_start_v = max(arrival_v, earliest_v)
                
                # Check if we can start within the time window
                if actual_start_v > latest_v:
                    continue
                
                finish_v = actual_start_v + insp[v]
                new_cost = current_cost + tc
                
                # Update if better cost, or same cost but earlier finish
                if (new_cost < dp_cost[new_mask][v] or 
                    (new_cost == dp_cost[new_mask][v] and finish_v < dp_time[new_mask][v])):
                    dp_cost[new_mask][v] = new_cost
                    dp_time[new_mask][v] = finish_v
                    dp_parent[new_mask][v] = u
    
    # Find best ending station with full_mask
    best_cost = INF
    best_end = -1
    best_time = INF
    
    for u in range(n):
        if dp_cost[full_mask][u] < best_cost or (dp_cost[full_mask][u] == best_cost and dp_time[full_mask][u] < best_time):
            best_cost = dp_cost[full_mask][u]
            best_time = dp_time[full_mask][u]
            best_end = u
    
    if best_end == -1 or best_cost == INF:
        # Try to find best partial solution
        best_count = 0
        best_mask = 0
        for mask in range(1, 1 << n):
            for u in range(n):
                if dp_cost[mask][u] < INF:
                    cnt = bin(mask).count('1')
                    if cnt > best_count or (cnt == best_count and dp_cost[mask][u] < best_cost):
                        best_count = cnt
                        best_cost = dp_cost[mask][u]
                        best_end = u
                        best_mask = mask
        
        if best_end == -1:
            return {
                'route': [],
                'total_cost': float('inf'),
                'arrival_times': [],
                'feasible': False
            }
        
        # Reconstruct partial route
        route = []
        mask = best_mask
        u = best_end
        while u != -1:
            route.append(u)
            prev = dp_parent[mask][u]
            mask = mask ^ (1 << u)
            u = prev
        route.reverse()
        
        # Compute arrival times
        arrival_times = _compute_arrival_times(route, cost_matrix, time_windows, insp, speed)
        
        return {
            'route': route,
            'total_cost': best_cost,
            'arrival_times': arrival_times,
            'feasible': False
        }
    
    # Reconstruct route
    route = []
    mask = full_mask
    u = best_end
    while u != -1:
        route.append(u)
        prev = dp_parent[mask][u]
        mask = mask ^ (1 << u)
        u = prev
    route.reverse()
    
    # Compute arrival times
    arrival_times = _compute_arrival_times(route, cost_matrix, time_windows, insp, speed)
    
    return {
        'route': route,
        'total_cost': best_cost,
        'arrival_times': arrival_times,
        'feasible': True
    }


def _compute_arrival_times(route, cost_matrix, time_windows, insp, speed):
    """Compute actual arrival times along the route."""
    if not route:
        return []
    
    arrival_times = []
    first = route[0]
    earliest, _ = time_windows[first]
    arrival = earliest
    arrival_times.append(arrival)
    current_finish = arrival + insp[first]
    
    for i in range(1, len(route)):
        prev = route[i - 1]
        curr = route[i]
        tt = cost_matrix[prev][curr] / speed if speed > 0 else 0
        arrival = current_finish + tt
        earliest, _ = time_windows[curr]
        actual_start = max(arrival, earliest)
        arrival_times.append(actual_start)
        current_finish = actual_start + insp[curr]
    
    return arrival_times


def main():
    n = 15
    random.seed(42)
    
    # Generate random cost matrix (symmetric, no self-loops)
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = random.uniform(5, 50)
            cost_matrix[i][j] = round(c, 2)
            cost_matrix[j][i] = round(c, 2)
    
    # Generate time windows - make them fairly wide to ensure feasibility
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 50)
        latest = earliest + random.uniform(100, 300)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    inspection_time = 5.0
    speed = 1.0
    
    print(f"Test case: {n} stations")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print()
    
    start_time = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start_time
    
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Total cost: {result['total_cost']}")
    print(f"Arrival times: {result['arrival_times']}")
    print(f"Elapsed time: {elapsed:.4f} seconds")
    
    # Verify route
    if result['feasible']:
        route = result['route']
        assert len(route) == n, f"Route length {len(route)} != {n}"
        assert set(route) == set(range(n)), "Route doesn't visit all stations"
        
        # Verify cost
        total = 0
        for i in range(1, len(route)):
            total += cost_matrix[route[i-1]][route[i]]
        print(f"Verified cost: {round(total, 2)}")
        
        # Verify time windows
        all_ok = True
        for i, (station, arr) in enumerate(zip(route, result['arrival_times'])):
            earliest, latest = time_windows[station]
            if arr > latest + 1e-9:
                print(f"  WARNING: Station {station} arrival {arr:.2f} > latest {latest:.2f}")
                all_ok = False
        if all_ok:
            print("All time windows satisfied.")


if __name__ == "__main__":
    main()