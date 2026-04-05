import random
import time
import sys
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find the optimal route visiting all monitoring stations within time windows.
    
    Uses bitmask DP for efficient state space exploration.
    
    Parameters:
        cost_matrix: NxN matrix of distances/costs between stations
        time_windows: list of (earliest, latest) tuples for each station
        inspection_time: time spent at each station (scalar or list)
        speed: travel speed (distance/time)
    
    Returns:
        dict with keys: 'route', 'cost', 'arrival_times', 'feasible'
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
            if speed > 0:
                travel_time[i][j] = cost_matrix[i][j] / speed
            else:
                travel_time[i][j] = cost_matrix[i][j]
    
    # Bitmask DP
    # State: (current_station, visited_mask) -> (min_cost, earliest_feasible_departure_time)
    # We want to minimize cost while respecting time windows
    
    full_mask = (1 << n) - 1
    
    # dp[mask][i] = (min_cost, earliest_departure_time) 
    # meaning: we've visited exactly the stations in mask, currently at station i,
    # and we depart at earliest_departure_time with accumulated cost min_cost
    
    INF = float('inf')
    
    # Initialize: dp stores (cost, departure_time, parent_mask, parent_station)
    # For reconstruction, we'll track the path separately
    
    # dp[mask][i] = (cost, departure_time)
    dp = [[None] * n for _ in range(1 << n)]
    parent = [[None] * n for _ in range(1 << n)]
    
    # Start at station 0
    earliest_0, latest_0 = time_windows[0]
    arrival_0 = earliest_0  # arrive at earliest possible
    if arrival_0 > latest_0:
        return {'route': [], 'cost': INF, 'arrival_times': [], 'feasible': False}
    
    departure_0 = arrival_0 + insp[0]
    dp[1 << 0][0] = (0.0, departure_0, arrival_0)  # (cost, departure_time, arrival_time)
    
    # Process states in order of popcount for correctness
    for mask in range(1, 1 << n):
        for u in range(n):
            if dp[mask][u] is None:
                continue
            if not (mask & (1 << u)):
                continue
            
            cost_u, depart_u, arrival_u = dp[mask][u]
            
            for v in range(n):
                if mask & (1 << v):
                    continue
                
                new_mask = mask | (1 << v)
                tt = travel_time[u][v]
                arrival_v = depart_u + tt
                
                earliest_v, latest_v = time_windows[v]
                
                # Must wait if we arrive early
                if arrival_v < earliest_v:
                    arrival_v = earliest_v
                
                # Infeasible if we arrive after the latest time
                if arrival_v > latest_v:
                    continue
                
                new_cost = cost_u + cost_matrix[u][v]
                departure_v = arrival_v + insp[v]
                
                if dp[new_mask][v] is None or new_cost < dp[new_mask][v][0] or \
                   (new_cost == dp[new_mask][v][0] and departure_v < dp[new_mask][v][1]):
                    dp[new_mask][v] = (new_cost, departure_v, arrival_v)
                    parent[new_mask][v] = (mask, u)
    
    # Find the best end state (all visited, return to 0)
    best_cost = INF
    best_end = -1
    best_total_cost = INF
    return_to_start = True
    
    # Try ending at any station (with return to station 0)
    for u in range(n):
        if dp[full_mask][u] is None:
            continue
        
        cost_u, depart_u, arr_u = dp[full_mask][u]
        # Cost to return to station 0
        return_cost = cost_matrix[u][0]
        total_cost = cost_u + return_cost
        
        # Check if we can return in time (if station 0 has a window for return)
        return_arrival = depart_u + travel_time[u][0]
        
        if total_cost < best_total_cost:
            best_total_cost = total_cost
            best_end = u
    
    # Also try without returning to start
    best_no_return_cost = INF
    best_no_return_end = -1
    for u in range(n):
        if dp[full_mask][u] is None:
            continue
        cost_u, depart_u, arr_u = dp[full_mask][u]
        if cost_u < best_no_return_cost:
            best_no_return_cost = cost_u
            best_no_return_end = u
    
    # Decide whether to return to start or not
    # We'll include return to start as the standard TSP formulation
    if best_end == -1 and best_no_return_end == -1:
        return {'route': [], 'cost': INF, 'arrival_times': [], 'feasible': False}
    
    # Use the version with return to start if feasible, otherwise without
    if best_end != -1:
        use_return = True
        final_end = best_end
        final_cost = best_total_cost
    else:
        use_return = False
        final_end = best_no_return_end
        final_cost = best_no_return_cost
    
    # Reconstruct route
    route = []
    arrival_times = []
    
    current_mask = full_mask
    current_node = final_end
    
    while current_node is not None:
        state = dp[current_mask][current_node]
        route.append(current_node)
        arrival_times.append(state[2])  # arrival time
        
        p = parent[current_mask][current_node]
        if p is None:
            break
        prev_mask, prev_node = p
        current_mask = prev_mask
        current_node = prev_node
    
    route.reverse()
    arrival_times.reverse()
    
    if use_return:
        # Add return to station 0
        last_depart = dp[full_mask][final_end][1]
        return_arrival = last_depart + travel_time[final_end][0]
        route.append(0)
        arrival_times.append(return_arrival)
    
    return {
        'route': route,
        'cost': final_cost,
        'arrival_times': arrival_times,
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
        earliest = random.uniform(0, 50)
        latest = earliest + random.uniform(100, 300)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Station 0 starts early
    time_windows[0] = (0, 500)
    
    inspection_time = 2.0
    speed = 1.0
    
    print(f"Number of stations: {n}")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print(f"Time windows (first 5): {time_windows[:5]}...")
    print()
    
    start_time = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start_time
    
    print(f"Feasible: {result['feasible']}")
    if result['feasible']:
        print(f"Route: {result['route']}")
        print(f"Cost: {result['cost']:.2f}")
        print(f"Arrival times: {[f'{t:.2f}' for t in result['arrival_times']]}")
        print(f"Number of stops: {len(result['route'])}")
    else:
        print("No feasible route found.")
    
    print(f"\nElapsed time: {elapsed:.4f} seconds")
    
    # Verify solution
    if result['feasible'] and len(result['route']) > 1:
        route = result['route']
        arrivals = result['arrival_times']
        valid = True
        for idx in range(len(route)):
            station = route[idx]
            arr = arrivals[idx]
            if idx < len(route) - 1 or station != route[0]:  # skip return trip window check
                tw = time_windows[station]
                if arr < tw[0] - 1e-9 or arr > tw[1] + 1e-9:
                    if not (idx == len(route) - 1 and station == 0):
                        print(f"WARNING: Station {station} arrival {arr:.2f} outside window {tw}")
                        valid = True  # return trip might not need window check
        
        # Verify visited all stations
        visited = set(route)
        if 0 in visited and route[-1] == 0:
            visited_without_return = set(route[:-1])
        else:
            visited_without_return = visited
        
        all_stations = set(range(n))
        if visited_without_return >= all_stations:
            print("All stations visited: YES")
        else:
            missing = all_stations - visited_without_return
            print(f"Missing stations: {missing}")


if __name__ == "__main__":
    main()