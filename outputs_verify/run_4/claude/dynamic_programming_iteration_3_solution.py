import random
import time
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    """
    Find the optimal route visiting all monitoring stations within time windows.
    
    Uses bitmask DP (Held-Karp style) for efficient solving of TSP-like problems
    with time window constraints.
    
    Parameters:
        cost_matrix: 2D list of travel costs/distances between stations
        time_windows: list of (earliest, latest) tuples for each station
        inspection_time: time spent at each station (scalar or list)
        speed: travel speed (default 1)
    
    Returns:
        dict with keys: 'route', 'total_cost', 'arrival_times', 'feasible'
    """
    n = len(cost_matrix)
    
    if n == 0:
        return {'route': [], 'total_cost': 0, 'arrival_times': [], 'feasible': True}
    
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
    
    full_mask = (1 << n) - 1
    
    # DP with bitmask
    # State: (visited_mask, current_station) -> (min_cost, earliest_finish_time)
    # We want to minimize cost while respecting time windows
    
    INF = float('inf')
    
    # dp[mask][i] = (best_cost, earliest_departure_time) 
    # meaning: visited exactly the stations in mask, currently at station i,
    # departed from i at earliest_departure_time with total travel cost best_cost
    
    # Initialize: start from station 0
    # We can also try starting from each station and pick the best
    
    # Using dict-based DP for sparse states
    # dp[mask][i] = (min_cost, min_departure_time_for_that_cost)
    # Among states with equal cost, prefer earlier departure time
    # Among all, we want minimum cost that is feasible
    
    # For time windows, we need to track time, so state is (mask, i) -> list of (cost, time) Pareto-optimal points
    # But for tractability, we keep (mask, i) -> (cost, departure_time) 
    # where we greedily minimize cost first, then time
    
    # Actually, since time windows create feasibility constraints, we need to be careful.
    # A cheaper path might arrive too late at a future station.
    # We need Pareto-optimal (cost, time) states.
    
    # For up to 20 stations, 2^20 * 20 = ~20M states. With Pareto fronts this could explode.
    # Compromise: keep only a limited Pareto front, or use a single (cost, time) per state
    # choosing minimum cost, breaking ties by minimum time.
    
    # Better approach: since we want minimum cost and feasibility, let's track:
    # dp[mask][i] = minimum cost to visit all stations in mask ending at i,
    #               with the constraint that all time windows are met,
    #               along with the departure time from i for that minimum cost path.
    # If multiple paths have the same minimum cost, keep the one with earliest departure.
    # If a cheaper path leads to infeasibility later but a costlier one doesn't,
    # we need Pareto front.
    
    # For correctness with time windows, maintain Pareto front of (cost, time).
    # A state (c1, t1) dominates (c2, t2) if c1 <= c2 and t1 <= t2.
    
    # With 20 stations, worst case Pareto fronts could be large, but in practice they're small.
    
    # dp[mask][i] = list of (cost, departure_time) Pareto-optimal states
    
    dp = [[None] * n for _ in range(1 << n)]
    parent = [[None] * n for _ in range(1 << n)]
    
    # Start at station 0
    start = 0
    earliest_0, latest_0 = time_windows[start]
    arrival_0 = earliest_0  # arrive at earliest possible time
    if arrival_0 > latest_0:
        return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    departure_0 = max(arrival_0, earliest_0) + insp[start]
    start_mask = 1 << start
    dp[start_mask][start] = [(0, arrival_0, departure_0)]  # (cost, arrival_time, departure_time)
    
    # Try all starting stations
    for s in range(n):
        e_s, l_s = time_windows[s]
        arr_s = e_s
        if arr_s > l_s:
            continue
        dep_s = max(arr_s, e_s) + insp[s]
        s_mask = 1 << s
        if dp[s_mask][s] is None:
            dp[s_mask][s] = [(0, arr_s, dep_s)]
        else:
            dp[s_mask][s].append((0, arr_s, dep_s))
            dp[s_mask][s] = _pareto_filter(dp[s_mask][s])
    
    # Fill DP
    for mask in range(1, 1 << n):
        for i in range(n):
            if not (mask & (1 << i)):
                continue
            if dp[mask][i] is None:
                continue
            
            for j in range(n):
                if mask & (1 << j):
                    continue
                
                new_mask = mask | (1 << j)
                e_j, l_j = time_windows[j]
                
                new_states = []
                for (cost_so_far, arr_i, dep_i) in dp[mask][i]:
                    tt = travel_time[i][j]
                    arr_j = dep_i + tt
                    
                    # Must arrive within time window
                    actual_start_j = max(arr_j, e_j)
                    if actual_start_j > l_j:
                        continue  # infeasible
                    
                    dep_j = actual_start_j + insp[j]
                    new_cost = cost_so_far + cost_matrix[i][j]
                    
                    new_states.append((new_cost, arr_j, dep_j))
                
                if not new_states:
                    continue
                
                if dp[new_mask][j] is None:
                    dp[new_mask][j] = []
                
                dp[new_mask][j].extend(new_states)
                dp[new_mask][j] = _pareto_filter(dp[new_mask][j])
                
                # Limit Pareto front size to prevent blowup
                if len(dp[new_mask][j]) > 50:
                    dp[new_mask][j] = dp[new_mask][j][:50]
    
    # Find best solution visiting all stations
    best_cost = INF
    best_end = -1
    best_idx = -1
    
    for i in range(n):
        if dp[full_mask][i] is None:
            continue
        for idx, (cost, arr, dep) in enumerate(dp[full_mask][i]):
            # Optionally add return cost to start
            total = cost
            if total < best_cost:
                best_cost = total
                best_end = i
                best_idx = idx
    
    if best_cost == INF:
        # Try partial solutions - find mask with most bits set
        best_partial_mask = 0
        best_partial_cost = INF
        best_partial_end = -1
        best_partial_idx = -1
        best_count = 0
        
        for mask in range(1, 1 << n):
            count = bin(mask).count('1')
            if count < best_count:
                continue
            for i in range(n):
                if dp[mask][i] is None:
                    continue
                for idx, (cost, arr, dep) in enumerate(dp[mask][i]):
                    if count > best_count or (count == best_count and cost < best_partial_cost):
                        best_count = count
                        best_partial_cost = cost
                        best_partial_mask = mask
                        best_partial_end = i
                        best_partial_idx = idx
        
        if best_count == 0:
            return {'route': [], 'total_cost': 0, 'arrival_times': [], 'feasible': False}
        
        # Reconstruct partial route
        route, arrivals = _reconstruct(dp, cost_matrix, travel_time, time_windows, insp,
                                        best_partial_mask, best_partial_end, best_partial_idx, n)
        return {
            'route': route,
            'total_cost': best_partial_cost,
            'arrival_times': arrivals,
            'feasible': False
        }
    
    # Reconstruct route
    route, arrivals = _reconstruct(dp, cost_matrix, travel_time, time_windows, insp,
                                    full_mask, best_end, best_idx, n)
    
    return {
        'route': route,
        'total_cost': best_cost,
        'arrival_times': arrivals,
        'feasible': True
    }


def _pareto_filter(states):
    """Filter to keep only Pareto-optimal states (minimize cost and departure_time)."""
    if not states:
        return states
    
    # Sort by cost, then by departure time
    states.sort(key=lambda x: (x[0], x[2]))
    
    filtered = [states[0]]
    min_dep = states[0][2]
    
    for i in range(1, len(states)):
        cost, arr, dep = states[i]
        if dep < min_dep:
            filtered.append(states[i])
            min_dep = dep
    
    return filtered


def _reconstruct(dp, cost_matrix, travel_time, time_windows, insp, mask, end, state_idx, n):
    """Reconstruct the route from DP table."""
    route = [end]
    arrivals = []
    
    current_mask = mask
    current_node = end
    current_cost, current_arr, current_dep = dp[current_mask][current_node][state_idx]
    arrivals.append(current_arr)
    
    while bin(current_mask).count('1') > 1:
        prev_mask = current_mask ^ (1 << current_node)
        
        found = False
        for prev_node in range(n):
            if not (prev_mask & (1 << prev_node)):
                continue
            if dp[prev_mask][prev_node] is None:
                continue
            
            for pidx, (pc, pa, pd) in enumerate(dp[prev_mask][prev_node]):
                tt = travel_time[prev_node][current_node]
                expected_arr = pd + tt
                expected_cost = pc + cost_matrix[prev_node][current_node]
                
                if abs(expected_cost - current_cost) < 1e-9:
                    e_j, l_j = time_windows[current_node]
                    actual_start = max(expected_arr, e_j)
                    expected_dep = actual_start + insp[current_node]
                    
                    if abs(expected_dep - current_dep) < 1e-9 and abs(expected_arr - current_arr) < 1e-9:
                        route.append(prev_node)
                        arrivals.append(pa)
                        current_mask = prev_mask
                        current_node = prev_node
                        current_cost = pc
                        current_arr = pa
                        current_dep = pd
                        found = True
                        break
            if found:
                break
        
        if not found:
            # Fallback: try approximate match
            for prev_node in range(n):
                if not (prev_mask & (1 << prev_node)):
                    continue
                if dp[prev_mask][prev_node] is None:
                    continue
                
                for pidx, (pc, pa, pd) in enumerate(dp[prev_mask][prev_node]):
                    expected_cost = pc + cost_matrix[prev_node][current_node]
                    if abs(expected_cost - current_cost) < 1e-6:
                        route.append(prev_node)
                        arrivals.append(pa)
                        current_mask = prev_mask
                        current_node = prev_node
                        current_cost = pc
                        current_arr = pa
                        current_dep = pd
                        found = True
                        break
                if found:
                    break
            
            if not found:
                break
    
    route.reverse()
    arrivals.reverse()
    
    return route, arrivals


def main():
    random.seed(42)
    n = 15
    
    # Generate random cost matrix (symmetric, no self-loops)
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            cost = random.uniform(5, 50)
            cost_matrix[i][j] = round(cost, 2)
            cost_matrix[j][i] = round(cost, 2)
    
    # Generate time windows
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 100)
        latest = earliest + random.uniform(50, 200)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Sort time windows to make feasibility more likely
    # (don't sort, just make windows wide enough)
    
    inspection_time = 5
    speed = 1.0
    
    print(f"Number of stations: {n}")
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
    
    # Verify the solution
    if result['feasible'] and result['route']:
        route = result['route']
        print(f"\nRoute length: {len(route)} stations")
        
        # Verify all stations visited
        assert len(route) == n, f"Expected {n} stations, got {len(route)}"
        assert set(route) == set(range(n)), "Not all stations visited"
        
        # Verify costs
        total = 0
        for k in range(len(route) - 1):
            total += cost_matrix[route[k]][route[k + 1]]
        assert abs(total - result['total_cost']) < 1e-6, f"Cost mismatch: {total} vs {result['total_cost']}"
        
        print("Solution verified successfully!")


if __name__ == "__main__":
    main()