import random
import time


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find optimal route visiting all monitoring stations within time windows.
    
    Uses bitmask DP for efficient state space exploration.
    
    Parameters:
        cost_matrix: 2D list of travel costs/distances between stations
        time_windows: list of (earliest, latest) tuples for each station
        inspection_time: time spent at each station (scalar or list)
        speed: travel speed factor
    
    Returns:
        dict with keys: 'route', 'total_cost', 'arrival_times', 'feasible'
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
    
    if n == 0:
        return {'route': [], 'total_cost': 0, 'arrival_times': [], 'feasible': True}
    
    if n == 1:
        earliest, latest = time_windows[0]
        arrival = earliest
        if arrival <= latest:
            return {'route': [0], 'total_cost': 0, 'arrival_times': [arrival], 'feasible': True}
        else:
            return {'route': [0], 'total_cost': 0, 'arrival_times': [arrival], 'feasible': False}
    
    full_mask = (1 << n) - 1
    INF = float('inf')
    
    MAX_PARETO = 50  # limit per state to control memory/time
    
    # dp[(mask, i)] = list of (cost, dep_time, arr_time) Pareto-optimal entries
    # parent[(mask, i)] = list of parent info corresponding to each entry
    dp = {}
    parent = {}
    
    def add_to_pareto(key, cost, dep_time, arr_time, par_info):
        """Add a (cost, dep_time, arr_time) entry to dp[key], maintaining Pareto optimality."""
        if key not in dp:
            dp[key] = []
            parent[key] = []
        
        entries = dp[key]
        parents = parent[key]
        
        # Check if dominated by existing
        for c, d, a in entries:
            if c <= cost and d <= dep_time:
                return  # dominated
        
        # Remove entries dominated by new
        new_entries = []
        new_parents = []
        for idx, (c, d, a) in enumerate(entries):
            if cost <= c and dep_time <= d:
                continue  # dominated by new entry
            new_entries.append((c, d, a))
            new_parents.append(parents[idx])
        
        new_entries.append((cost, dep_time, arr_time))
        new_parents.append(par_info)
        
        # Limit Pareto front size
        if len(new_entries) > MAX_PARETO:
            combined = list(zip(new_entries, new_parents))
            combined.sort(key=lambda x: (x[0][0], x[0][1]))
            combined = combined[:MAX_PARETO]
            new_entries = [x[0] for x in combined]
            new_parents = [x[1] for x in combined]
        
        dp[key] = new_entries
        parent[key] = new_parents
    
    # Initialize: start from station 0 at its earliest time
    start_earliest, start_latest = time_windows[0]
    start_arrival = start_earliest
    if start_arrival > start_latest:
        return {'route': list(range(n)), 'total_cost': INF, 'arrival_times': [0]*n, 'feasible': False}
    
    start_departure = start_arrival + insp[0]
    init_key = (1 << 0, 0)
    dp[init_key] = [(0.0, start_departure, start_arrival)]
    parent[init_key] = [None]  # No parent for initial state
    
    # Process states in order of popcount (number of visited stations)
    for popcount in range(1, n + 1):
        keys_to_process = [(mask, i) for (mask, i) in list(dp.keys()) if bin(mask).count('1') == popcount]
        
        for mask, i in keys_to_process:
            entries = dp[(mask, i)]
            
            for pidx, (cost, dep_time, arr_time_i) in enumerate(entries):
                # Try extending to each unvisited station
                for j in range(n):
                    if mask & (1 << j):
                        continue
                    
                    tt = travel_time[i][j]
                    arrival_j = dep_time + tt
                    
                    earliest_j, latest_j = time_windows[j]
                    
                    # Wait if arriving early
                    if arrival_j < earliest_j:
                        arrival_j = earliest_j
                    
                    # Check if within time window
                    if arrival_j > latest_j:
                        continue
                    
                    new_cost = cost + cost_matrix[i][j]
                    new_dep = arrival_j + insp[j]
                    new_mask = mask | (1 << j)
                    
                    add_to_pareto(
                        (new_mask, j),
                        new_cost, new_dep, arrival_j,
                        (mask, i, pidx)
                    )
    
    # Find best solution visiting all stations
    best_cost = INF
    best_key = None
    best_pidx = None
    
    for i in range(n):
        key = (full_mask, i)
        if key in dp:
            for pidx, (cost, dep_time, arr_time) in enumerate(dp[key]):
                if cost < best_cost:
                    best_cost = cost
                    best_key = key
                    best_pidx = pidx
    
    if best_key is None:
        # No feasible solution visiting all stations
        # Find the mask with most bits set that has a solution
        best_partial_cost = INF
        best_partial_key = None
        best_partial_pidx = None
        best_partial_count = 0
        
        for (mask, i), entries in dp.items():
            count = bin(mask).count('1')
            for pidx, (cost, dep, arr) in enumerate(entries):
                if count > best_partial_count or (count == best_partial_count and cost < best_partial_cost):
                    best_partial_count = count
                    best_partial_cost = cost
                    best_partial_key = (mask, i)
                    best_partial_pidx = pidx
        
        if best_partial_key is None:
            return {'route': list(range(n)), 'total_cost': INF, 'arrival_times': [0]*n, 'feasible': False}
        
        route, arrival_list = _reconstruct(best_partial_key, best_partial_pidx, dp, parent)
        
        return {
            'route': route,
            'total_cost': best_partial_cost,
            'arrival_times': arrival_list,
            'feasible': False
        }
    
    # Reconstruct route
    route, arrival_list = _reconstruct(best_key, best_pidx, dp, parent)
    
    return {
        'route': route,
        'total_cost': best_cost,
        'arrival_times': arrival_list,
        'feasible': True
    }


def _reconstruct(key, pidx, dp, parent):
    """Reconstruct route from DP tables."""
    path = []
    
    current_key = key
    current_pidx = pidx
    
    while current_key is not None:
        mask_c, i_c = current_key
        entries = dp[current_key]
        
        # Handle case where pidx might be out of range due to Pareto pruning
        if current_pidx >= len(entries):
            current_pidx = 0
        
        cost_c, dep_c, arr_c = entries[current_pidx]
        path.append((i_c, arr_c))
        
        par_entries = parent.get(current_key)
        if par_entries is None:
            break
        
        if current_pidx >= len(par_entries):
            current_pidx = 0
            
        par = par_entries[current_pidx]
        if par is None:
            break
        
        prev_mask, prev_i, prev_pidx = par
        current_key = (prev_mask, prev_i)
        current_pidx = prev_pidx
    
    path.reverse()
    route = [station for station, arr in path]
    arrival_list = [arr for station, arr in path]
    
    return route, arrival_list


def main():
    random.seed(42)
    n = 15
    
    # Generate random cost matrix (symmetric, positive)
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = random.uniform(5, 50)
            cost_matrix[i][j] = round(c, 2)
            cost_matrix[j][i] = round(c, 2)
    
    # Generate time windows: each station has a window [earliest, latest]
    # Make windows reasonably wide to allow feasible solutions
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 100)
        latest = earliest + random.uniform(50, 200)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Station 0 starts early
    time_windows[0] = (0, 300)
    
    inspection_time = 2.0
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
    print(f"Number of stations visited: {len(result['route'])}")
    print(f"Elapsed time: {elapsed:.4f} seconds")
    
    # Verify time windows
    if result['feasible']:
        print("\nVerification:")
        for idx, station in enumerate(result['route']):
            arr = result['arrival_times'][idx]
            tw = time_windows[station]
            ok = tw[0] <= arr <= tw[1]
            print(f"  Station {station}: arrival={arr:.2f}, window=[{tw[0]:.2f}, {tw[1]:.2f}], {'OK' if ok else 'VIOLATED'}")


if __name__ == "__main__":
    main()