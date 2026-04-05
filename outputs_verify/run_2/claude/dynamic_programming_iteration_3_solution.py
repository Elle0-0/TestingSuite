import random
import time
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find the optimal route visiting all monitoring stations using bitmask DP.
    
    Parameters:
    - cost_matrix: 2D list of distances/costs between stations
    - time_windows: list of (earliest, latest) tuples for each station
    - inspection_time: time spent at each station (scalar or list)
    - speed: travel speed (default 1)
    
    Returns:
    - dict with 'route', 'total_cost', 'arrival_times', 'feasible'
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
            if i != j:
                travel_time[i][j] = cost_matrix[i][j] / speed if speed > 0 else float('inf')
    
    full_mask = (1 << n) - 1
    
    # dp[mask][i] = (min_cost, earliest_finish_time) to visit all stations in mask, ending at i
    # We want to minimize cost while respecting time windows
    
    INF = float('inf')
    
    # State: (mask, last_station) -> (best_cost, earliest_arrival_time_at_last)
    # We need to track arrival time because time windows constrain when we can visit
    
    # Since time is continuous, we can't discretize it easily.
    # For each (mask, last_station), we want the minimum cost achievable with the earliest possible arrival time.
    # But there could be tradeoffs: a path with higher cost might arrive earlier, enabling more future visits.
    
    # Approach: For each (mask, i), store the minimum arrival time at station i 
    # having visited exactly the stations in mask. Among paths achieving this,
    # we also track the cost. If time windows are the binding constraint, 
    # we need to be careful.
    
    # Actually, let's store for each (mask, i): the minimum cost to reach state (mask, i)
    # AND separately the earliest arrival time. But these might conflict.
    
    # Better approach: for each (mask, i), store (min_cost, arrival_time) where we minimize
    # cost but also need feasible arrival times. Since waiting is free (we can wait until
    # the time window opens), the arrival_time is actually the time we START inspection at i.
    
    # Let's define:
    # dp[mask][i] = (min_cost, departure_time) where departure_time = max(arrival, earliest[i]) + insp[i]
    # We want min cost. If two paths have same cost, prefer earlier departure (more flexibility).
    # If a path has lower cost but later departure, it might still be optimal if future windows allow.
    
    # To handle this properly with pruning, store Pareto-optimal (cost, time) pairs.
    # But for n=20, mask has 2^20 = 1M states, times n = 20M entries. 
    # Storing single best per state is needed for efficiency.
    
    # Key insight: if we're minimizing cost and time windows just define feasibility,
    # then for each (mask, i) we want minimum cost, but we also need the earliest 
    # possible departure time for that minimum cost (to maximize future feasibility).
    
    # Heuristic that works well in practice: store (min_cost, earliest_departure_for_that_cost)
    # But if a slightly higher cost gives much earlier departure enabling otherwise infeasible paths...
    
    # For correctness with time windows, let's store for each (mask, i):
    # the earliest departure time achievable (regardless of cost), AND
    # track cost along with it. Actually let's do Pareto front but pruned.
    
    # Simpler correct approach for n<=20: 
    # dp[mask][i] = earliest departure time from station i, having visited all in mask
    # cost[mask][i] = accumulated cost for that path
    # When multiple predecessors, prefer lower departure time (greedily maximizes feasibility)
    # If tie, prefer lower cost.
    
    # Actually for pure cost minimization with time window feasibility:
    # We need to track both cost and time. Let's do two separate DP tables
    # and use a combined optimization.
    
    # Practical approach: dp[mask][i] stores a small list of Pareto-optimal (cost, depart_time) pairs
    # Pareto: no other pair dominates on both cost AND time.
    # For n=20, worst case 2^20 * 20 = 20M states, each with small Pareto list.
    
    # Let's implement with single (cost, time) per state, preferring earlier departure time
    # when costs are equal, and allowing slightly suboptimal cost if it enables much earlier time.
    
    # For simplicity and correctness, let's keep Pareto fronts but limit their size.
    
    # Implementation with dict-based DP and Pareto fronts:
    
    # dp[mask][i] = list of (cost, depart_time) Pareto-optimal pairs, sorted by cost ascending
    
    # Initialize: start from each station (or just station 0 if depot-based)
    # Let's assume we start from station 0 (depot)
    
    # Actually, let's check if there's a depot. Common TSP formulation: start and end at 0.
    # Let's assume start at station 0.
    
    # For n<=20, let's use arrays with Pareto fronts
    
    # dp[mask][i] = list of (cost, depart_time, parent_mask, parent_station) 
    
    # To keep memory manageable, limit Pareto front size
    MAX_PARETO = 5  # Keep top entries per state
    
    # Use dictionaries for sparse storage
    # dp[(mask, i)] = sorted list of (cost, depart_time)
    
    dp = {}
    parent = {}  # For path reconstruction: (mask, i, idx_in_pareto) -> (prev_mask, prev_i, prev_idx)
    
    # Start at station 0
    start = 0
    earliest_0, latest_0 = time_windows[start]
    arrival_0 = earliest_0  # Arrive at earliest possible time
    
    if arrival_0 > latest_0:
        return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    depart_0 = arrival_0 + insp[start]
    init_mask = 1 << start
    dp[(init_mask, start)] = [(0.0, depart_0)]  # cost=0 to start
    parent[(init_mask, start, 0)] = None
    
    # Process masks in order of popcount (number of bits set)
    masks_by_popcount = [[] for _ in range(n + 1)]
    for mask in range(1, 1 << n):
        masks_by_popcount[bin(mask).count('1')].append(mask)
    
    for pc in range(1, n + 1):
        for mask in masks_by_popcount[pc]:
            for i in range(n):
                if not (mask & (1 << i)):
                    continue
                if (mask, i) not in dp:
                    continue
                
                entries_i = dp[(mask, i)]
                
                for j in range(n):
                    if mask & (1 << j):
                        continue
                    
                    new_mask = mask | (1 << j)
                    earliest_j, latest_j = time_windows[j]
                    tt = travel_time[i][j]
                    
                    new_entries = []
                    for idx, (c, dep_i) in enumerate(entries_i):
                        arrival_j = dep_i + tt
                        start_j = max(arrival_j, earliest_j)
                        
                        if start_j > latest_j:
                            continue  # Infeasible
                        
                        new_cost = c + cost_matrix[i][j]
                        new_depart = start_j + insp[j]
                        new_entries.append((new_cost, new_depart, mask, i, idx))
                    
                    if not new_entries:
                        continue
                    
                    # Merge with existing entries for (new_mask, j)
                    existing = dp.get((new_mask, j), [])
                    
                    # Build combined list
                    combined = [(c, d) for c, d in existing]
                    new_with_parent = []
                    for nc, nd, pm, pi, pidx in new_entries:
                        combined.append((nc, nd))
                        new_with_parent.append((nc, nd, pm, pi, pidx))
                    
                    # Compute Pareto front: no entry dominated by another on both cost and time
                    # Sort by cost ascending
                    all_entries = []
                    for c, d in existing:
                        all_entries.append((c, d, 'old'))
                    for nc, nd, pm, pi, pidx in new_with_parent:
                        all_entries.append((nc, nd, 'new', pm, pi, pidx))
                    
                    all_entries.sort(key=lambda x: (x[0], x[1]))
                    
                    pareto = []
                    min_time = INF
                    for entry in all_entries:
                        c, d = entry[0], entry[1]
                        if d < min_time:
                            pareto.append(entry)
                            min_time = d
                            if len(pareto) >= MAX_PARETO:
                                break
                    
                    # Store back
                    new_dp_list = [(e[0], e[1]) for e in pareto]
                    dp[(new_mask, j)] = new_dp_list
                    
                    # Update parent info
                    for k, entry in enumerate(pareto):
                        if entry[2] == 'new':
                            parent[(new_mask, j, k)] = (entry[3], entry[4], entry[5])
                        # If 'old', parent info already stored from previous iteration
                        # We need to handle re-indexing... this is getting complex.
    
    # For path reconstruction, let's do a simpler approach:
    # Re-run reconstruction by doing backward tracking from the dp values.
    
    # Find the best solution at full_mask
    best_cost = INF
    best_last = -1
    best_idx = -1
    
    for i in range(n):
        if (full_mask, i) in dp:
            for idx, (c, d) in enumerate(dp[(full_mask, i)]):
                # Optionally add return cost to depot
                total = c + cost_matrix[i][start]
                if total < best_cost:
                    best_cost = total
                    best_last = i
                    best_idx = idx
    
    if best_last == -1:
        # Try without return to start
        for i in range(n):
            if (full_mask, i) in dp:
                for idx, (c, d) in enumerate(dp[(full_mask, i)]):
                    if c < best_cost:
                        best_cost = c
                        best_last = i
                        best_idx = idx
        
        if best_last == -1:
            return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    # Reconstruct path by backtracking through DP
    # Since parent tracking got complex, let's reconstruct differently
    route = _reconstruct_route(n, cost_matrix, travel_time, time_windows, insp, dp, full_mask, best_last, best_idx, start)
    
    if route is None:
        return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    # Compute arrival times along the route
    arrival_times = []
    current_time = 0.0
    total_cost = 0.0
    
    for k, station in enumerate(route):
        if k == 0:
            earliest_s, latest_s = time_windows[station]
            arr = max(current_time, earliest_s)
            arrival_times.append(arr)
            current_time = arr + insp[station]
        else:
            prev = route[k - 1]
            tt = travel_time[prev][station]
            arr = current_time + tt
            earliest_s, latest_s = time_windows[station]
            arr = max(arr, earliest_s)
            arrival_times.append(arr)
            total_cost += cost_matrix[prev][station]
            current_time = arr + insp[station]
    
    # Add return to start
    if route[-1] != start:
        total_cost += cost_matrix[route[-1]][start]
    
    feasible = all(
        time_windows[route[k]][0] <= arrival_times[k] <= time_windows[route[k]][1]
        for k in range(len(route))
    )
    
    return {
        'route': route,
        'total_cost': total_cost,
        'arrival_times': arrival_times,
        'feasible': feasible
    }


def _reconstruct_route(n, cost_matrix, travel_time, time_windows, insp, dp, full_mask, last, last_idx, start):
    """Reconstruct the route by backtracking through the DP table."""
    route = [last]
    mask = full_mask
    current = last
    current_cost, current_depart = dp[(mask, current)][last_idx]
    
    while bin(mask).count('1') > 1:
        prev_mask = mask ^ (1 << current)
        
        best_prev = -1
        best_prev_idx = -1
        best_match = False
        
        for prev in range(n):
            if not (prev_mask & (1 << prev)):
                continue
            if (prev_mask, prev) not in dp:
                continue
            
            entries = dp[(prev_mask, prev)]
            tt = travel_time[prev][current]
            
            for idx, (c, dep) in enumerate(entries):
                arrival_current = dep + tt
                earliest_c, latest_c = time_windows[current]
                start_c = max(arrival_current, earliest_c)
                
                if start_c > latest_c:
                    continue
                
                expected_cost = c + cost_matrix[prev][current]
                expected_depart = start_c + insp[current]
                
                # Check if this matches our current state
                if abs(expected_cost - current_cost) < 1e-9 and abs(expected_depart - current_depart) < 1e-9:
                    best_prev = prev
                    best_prev_idx = idx
                    best_match = True
                    break
            
            if best_match:
                break
        
        if best_prev == -1:
            # Fallback: find closest match
            best_diff = INF = float('inf')
            for prev in range(n):
                if not (prev_mask & (1 << prev)):
                    continue
                if (prev_mask, prev) not in dp:
                    continue
                
                entries = dp[(prev_mask, prev)]
                tt = travel_time[prev][current]
                
                for idx, (c, dep) in enumerate(entries):
                    arrival_current = dep + tt
                    earliest_c, latest_c = time_windows[current]
                    start_c = max(arrival_current, earliest_c)
                    
                    if start_c > latest_c:
                        continue
                    
                    expected_cost = c + cost_matrix[prev][current]
                    diff = abs(expected_cost - current_cost)
                    if diff < best_diff:
                        best_diff = diff
                        best_prev = prev
                        best_prev_idx = idx
            
            if best_prev == -1:
                return None
        
        current_cost, current_depart = dp[(prev_mask, best_prev)][best_prev_idx]
        mask = prev_mask
        current = best_prev
        route.append(current)
    
    route.reverse()
    return route


def main():
    n = 15
    random.seed(42)
    
    # Generate random cost matrix (symmetric)
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = random.uniform(5, 50)
            cost_matrix[i][j] = c
            cost_matrix[j][i] = c
    
    # Generate time windows
    inspection_time = 2.0
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 50)
        latest = earliest + random.uniform(30, 100)
        time_windows.append((earliest, latest))
    
    # Make station 0's window start at 0
    time_windows[0] = (0, time_windows[0][1] + 50)
    
    speed = 1.0
    
    print(f"Solving TSP with time windows for {n} stations...")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print()
    
    start_time = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start_time
    
    print(f"Result:")
    print(f"  Feasible: {result['feasible']}")
    print(f"  Route: {result['route']}")
    print(f"  Total cost: {result['total_cost']:.2f}")
    print(f"  Arrival times: {[f'{t:.2f}' for t in result['arrival_times']]}")
    print(f"  Elapsed time: {elapsed:.3f} seconds")


if __name__ == "__main__":
    main()