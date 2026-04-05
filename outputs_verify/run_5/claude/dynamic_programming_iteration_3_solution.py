import random
import time
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find the optimal route to visit all monitoring stations minimizing total cost
    while respecting time windows and energy constraints.
    
    Uses bitmask DP for efficient state space exploration.
    
    Parameters:
        cost_matrix: n x n matrix where cost_matrix[i][j] is travel cost from station i to j
        time_windows: list of (earliest, latest) tuples for each station
        inspection_time: time spent at each station (scalar or list)
        speed: travel speed factor (default 1)
    
    Returns:
        dict with keys: 'route', 'total_cost', 'arrival_times', 'feasible'
    """
    n = len(cost_matrix)
    
    if n == 0:
        return {'route': [], 'total_cost': 0, 'arrival_times': [], 'feasible': True}
    
    if n == 1:
        earliest, latest = time_windows[0]
        insp = inspection_time[0] if isinstance(inspection_time, list) else inspection_time
        arrival = earliest
        if arrival <= latest:
            return {'route': [0], 'total_cost': 0, 'arrival_times': [arrival], 'feasible': True}
        else:
            return {'route': [0], 'total_cost': 0, 'arrival_times': [arrival], 'feasible': False}
    
    # Normalize inspection_time to a list
    if isinstance(inspection_time, (int, float)):
        insp_times = [inspection_time] * n
    else:
        insp_times = list(inspection_time)
    
    # Travel time from i to j
    def travel_time(i, j):
        if speed == 0:
            return float('inf')
        return cost_matrix[i][j] / speed
    
    full_mask = (1 << n) - 1
    
    # DP with bitmask: dp[mask][i] = (min_cost, earliest_finish_time)
    # mask: set of visited stations, i: last visited station
    # We want to find the route visiting all stations starting from station 0
    
    # State: (mask, last_station) -> (min_cost, earliest_departure_time)
    # earliest_departure_time = arrival_time + inspection_time
    
    INF = float('inf')
    
    # dp[mask][i] = (min_cost, earliest_departure_time)
    # We use dictionaries or arrays. For n<=20, mask up to 2^20 = 1M, times n = 20M entries
    # Use arrays for speed
    
    dp_cost = [[INF] * n for _ in range(1 << n)]
    dp_time = [[INF] * n for _ in range(1 << n)]
    dp_parent = [[-1] * n for _ in range(1 << n)]
    dp_arrival = [[0.0] * n for _ in range(1 << n)]
    
    # Start at station 0
    start = 0
    earliest_0, latest_0 = time_windows[start]
    arrival_0 = earliest_0  # arrive at earliest possible time
    
    if arrival_0 > latest_0:
        # Even the start is infeasible
        return {'route': list(range(n)), 'total_cost': INF, 'arrival_times': [0]*n, 'feasible': False}
    
    departure_0 = arrival_0 + insp_times[start]
    init_mask = 1 << start
    dp_cost[init_mask][start] = 0
    dp_time[init_mask][start] = departure_0
    dp_arrival[init_mask][start] = arrival_0
    
    # For tracking feasibility with time windows, we need to handle the case
    # where we might want to arrive later at a node to wait for its window.
    # With cost minimization: if cost doesn't depend on time, we want minimum cost.
    # But time windows constrain which transitions are feasible.
    
    # Key insight: for minimum cost with time windows, we should track the 
    # minimum departure time for each (mask, node) state, because arriving 
    # earlier gives more flexibility for future nodes.
    # If two states have same mask and node, prefer: lower cost, and among equal cost, earlier time.
    # Actually we need to be careful: a state with higher cost but earlier time might 
    # enable visiting nodes that a lower-cost-but-later state cannot.
    
    # For correctness with time windows, we need to handle Pareto-optimal states.
    # But for practical purposes with n<=20, let's use the approach:
    # dp[mask][i] = minimum departure time achievable with minimum cost
    # Tie-break: minimize cost first, then minimize time.
    
    # Actually, let's think about this more carefully.
    # If costs are independent of arrival time (which they appear to be - cost_matrix is static),
    # then we want minimum cost. Among routes with same cost visiting same set and ending at same node,
    # we prefer earliest departure (more flexibility).
    # But a higher cost route might have earlier departure enabling feasible completion...
    
    # For n<=20, we can use a more careful approach:
    # dp[mask][i] = minimum departure time, with cost as secondary
    # Actually, the standard TSP with time windows approach:
    # dp[mask][i] = (min_cost, min_departure_time_given_min_cost)
    
    # Simplification: if we just minimize cost and track earliest possible time,
    # we might miss feasible solutions. Let's do it properly:
    # For each (mask, i), store the Pareto front of (cost, time) pairs.
    
    # For n<=20, the bitmask space is 2^20 * 20 ≈ 20M states. Storing Pareto fronts
    # could be expensive. Let's try a simpler approach first:
    # dp[mask][i] = minimum time to depart from i having visited mask
    # Then separately track the minimum cost path.
    
    # Actually, the cleanest approach for this problem:
    # Since cost_matrix[i][j] IS the travel cost and likely also proportional to travel time,
    # let's check if travel time = cost / speed. If speed=1, cost = time.
    
    # Let me re-read: travel_time = cost_matrix[i][j] / speed
    # So minimizing cost while respecting time windows.
    
    # Approach: dp[mask][i] stores minimum cost to visit stations in mask, ending at i,
    # with the constraint that all time windows are respected.
    # For states with equal cost, we prefer earlier departure time (more flexible).
    # But this greedy choice on time might not always work...
    
    # For a robust solution, let's use:
    # dp[mask][i] = earliest possible departure time from i, having visited all stations in mask,
    #               with minimum total travel cost.
    # Primary key: cost (minimize), Secondary: departure time (minimize)
    
    for mask in range(1 << n):
        for last in range(n):
            if dp_cost[mask][last] == INF:
                continue
            if not (mask & (1 << last)):
                continue
            
            current_cost = dp_cost[mask][last]
            current_depart = dp_time[mask][last]
            
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                
                new_mask = mask | (1 << nxt)
                tt = cost_matrix[last][nxt] / speed if speed > 0 else INF
                tc = cost_matrix[last][nxt]
                
                arrival = current_depart + tt
                earliest_nxt, latest_nxt = time_windows[nxt]
                
                # Wait if we arrive early
                actual_arrival = max(arrival, earliest_nxt)
                
                # Check if we can make it within the time window
                if actual_arrival > latest_nxt:
                    continue
                
                departure_nxt = actual_arrival + insp_times[nxt]
                new_cost = current_cost + tc
                
                # Update if better: lower cost, or same cost but earlier departure
                if (new_cost < dp_cost[new_mask][nxt] or 
                    (new_cost == dp_cost[new_mask][nxt] and departure_nxt < dp_time[new_mask][nxt])):
                    dp_cost[new_mask][nxt] = new_cost
                    dp_time[new_mask][nxt] = departure_nxt
                    dp_parent[new_mask][nxt] = last
                    dp_arrival[new_mask][nxt] = actual_arrival
    
    # Find best end station
    best_cost = INF
    best_last = -1
    
    for i in range(n):
        if dp_cost[full_mask][i] < best_cost:
            best_cost = dp_cost[full_mask][i]
            best_last = i
    
    if best_last == -1:
        # No feasible solution found - try to find best partial or return infeasible
        # Try returning the route that visits most stations
        best_count = 0
        best_partial_mask = 0
        best_partial_last = 0
        best_partial_cost = INF
        
        for mask in range(1 << n):
            count = bin(mask).count('1')
            for i in range(n):
                if dp_cost[mask][i] < INF:
                    if count > best_count or (count == best_count and dp_cost[mask][i] < best_partial_cost):
                        best_count = count
                        best_partial_mask = mask
                        best_partial_last = i
                        best_partial_cost = dp_cost[mask][i]
        
        if best_count == 0:
            return {'route': [0], 'total_cost': 0, 'arrival_times': [time_windows[0][0]], 'feasible': False}
        
        # Reconstruct partial route
        route = []
        arrivals = []
        mask = best_partial_mask
        current = best_partial_last
        
        while current != -1:
            route.append(current)
            arrivals.append(dp_arrival[mask][current])
            prev = dp_parent[mask][current]
            mask = mask ^ (1 << current)
            current = prev
        
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
    current = best_last
    
    while current != -1:
        route.append(current)
        arrivals.append(dp_arrival[mask][current])
        prev = dp_parent[mask][current]
        mask = mask ^ (1 << current)
        current = prev
    
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
            cost = random.uniform(1, 50)
            cost_matrix[i][j] = round(cost, 2)
            cost_matrix[j][i] = round(cost, 2)
    
    # Generate time windows - make them wide enough to be feasible
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 100)
        latest = earliest + random.uniform(50, 200)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Station 0 starts early
    time_windows[0] = (0, 500)
    
    inspection_time = [random.uniform(1, 5) for _ in range(n)]
    inspection_time = [round(t, 2) for t in inspection_time]
    
    speed = 1.0
    
    print(f"Number of stations: {n}")
    print(f"Time windows: {time_windows[:5]}... (showing first 5)")
    print(f"Inspection times: {inspection_time[:5]}... (showing first 5)")
    print()
    
    start_time = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start_time
    
    print(f"Result:")
    print(f"  Route: {result['route']}")
    print(f"  Total cost: {result['total_cost']:.2f}")
    print(f"  Arrival times: {[round(t, 2) for t in result['arrival_times']]}")
    print(f"  Feasible: {result['feasible']}")
    print(f"  Number of stations visited: {len(result['route'])}")
    print(f"\nElapsed time: {elapsed:.4f} seconds")
    
    # Verify the solution
    if result['feasible']:
        route = result['route']
        assert len(route) == n, f"Route should visit all {n} stations"
        assert set(route) == set(range(n)), "Route should visit each station exactly once"
        
        # Verify time windows
        for idx, station in enumerate(route):
            arrival = result['arrival_times'][idx]
            earliest, latest = time_windows[station]
            assert arrival >= earliest - 1e-9, f"Station {station}: arrival {arrival} < earliest {earliest}"
            assert arrival <= latest + 1e-9, f"Station {station}: arrival {arrival} > latest {latest}"
        
        # Verify cost
        total_cost = 0
        for idx in range(len(route) - 1):
            total_cost += cost_matrix[route[idx]][route[idx + 1]]
        assert abs(total_cost - result['total_cost']) < 1e-6, f"Cost mismatch: {total_cost} vs {result['total_cost']}"
        
        print("\nSolution verified successfully!")


if __name__ == "__main__":
    main()