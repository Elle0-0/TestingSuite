import random
import time
import sys
from functools import lru_cache


def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    """
    Find the optimal route visiting all monitoring stations within time windows.
    
    Uses bitmask DP (Held-Karp style) for efficient solving up to ~20 stations.
    
    Parameters:
        cost_matrix: 2D list of travel costs/distances between stations
        time_windows: list of (earliest, latest) tuples for each station
        inspection_time: time spent at each station (scalar or list)
        speed: travel speed (distance/time)
    
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
            if i != j:
                travel_time[i][j] = cost_matrix[i][j] / speed if speed != 0 else float('inf')
    
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
    
    # dp[mask][i] = (min_cost, earliest_finish_time) to visit all stations in mask, ending at i
    # We want to minimize cost, and among equal costs, minimize time (to keep feasibility)
    # Actually, we need to track both cost and time carefully.
    # 
    # State: (mask, last_station) -> (min_cost, earliest_departure_time)
    # departure_time = arrival_time + inspection_time
    # arrival at j from i: departure_time_i + travel_time[i][j]
    # must have arrival_time_j >= earliest_j and arrival_time_j <= latest_j
    # We wait if we arrive early: effective_arrival = max(arrival, earliest_j)
    # feasible if effective_arrival <= latest_j
    
    # For optimality with time windows, we need to be careful:
    # Lower cost path might arrive later, making future windows infeasible.
    # We track (cost, departure_time) and for same mask/station, we prune dominated states.
    # A state dominates another if it has both <= cost and <= departure_time.
    
    # dp[mask][i] = list of Pareto-optimal (cost, departure_time) pairs
    # To keep it tractable, we can simplify: for each (mask, i), keep the minimum
    # departure time achievable, parameterized by cost. In practice, for many problems
    # the time-window constraints mean we should track earliest possible departure time
    # at minimum cost. But if a cheaper path arrives too late, we need the more expensive one.
    
    # Practical approach: dp[mask][i] = list of non-dominated (cost, dep_time) tuples
    # With pruning, this stays manageable for n<=20.
    
    # For efficiency, let's use arrays. But Pareto fronts can grow.
    # Alternative simpler approach that often works: dp[mask][i] = (min_cost, min_dep_time_at_min_cost)
    # If we break ties by earliest departure time, this is often sufficient.
    # But it's not always correct for time windows.
    
    # Full correct approach: maintain Pareto front per (mask, i).
    # For n=20, there are 20 * 2^20 ≈ 20M states. Each with a small Pareto front.
    # This could be too much memory. Let's try a compromise:
    # Track dp_cost[mask][i] and dp_time[mask][i] separately isn't correct either.
    
    # Better approach: Since we want min cost subject to feasibility,
    # and time windows constrain arrival times, let's do:
    # dp[mask][i] = minimum cost to visit stations in mask, ending at i,
    #               with dp_dep[mask][i] = earliest departure time achievable at that min cost
    # When transitioning, if the earliest departure leads to infeasibility at next station,
    # we skip. This might miss cases where a slightly costlier path has earlier departure
    # and enables visiting all stations. 
    
    # For full correctness with Pareto fronts:
    # Let's limit Pareto front size and see if it works.
    
    # Actually, let me reconsider. For many practical TSP-with-time-windows problems,
    # using (mask, i) -> min departure_time for each cost level is ideal, but we can
    # also just track: for (mask, i), the set of (cost, dep_time) where no other entry
    # has both cost' <= cost and dep_time' <= dep_time.
    
    # Implementation with Pareto fronts:
    
    # Initialize: start from station 0 (depot)
    # If no natural depot, try all starting stations.
    
    # Let's assume station 0 is the depot/start.
    # Actually, let's try all starting stations and pick best.
    
    # For large n, trying all starts is O(n) overhead which is fine.
    
    # Let's implement with Pareto fronts stored as sorted lists.
    
    # dp[mask][i] = sorted list of (cost, dep_time) non-dominated tuples
    # sorted by cost ascending, dep_time descending (since lower cost with higher time
    # is only kept if no lower-cost entry has lower time too)
    # Actually: Pareto front sorted by cost ascending means dep_time must be descending
    # for non-dominated points.
    
    # For n=20: 2^20 * 20 = ~20M entries. Each entry is a small list. 
    # Memory might be tight. Let's limit Pareto front size to some max (e.g., 10).
    
    MAX_PARETO = 50  # limit Pareto front size per state
    
    # Use dict for sparse storage - many (mask, i) states won't be reachable
    # dp[(mask, i)] = list of (cost, dep_time) tuples, Pareto-optimal
    
    dp = {}
    parent = {}  # for path reconstruction: (mask, i, pareto_idx) -> (prev_mask, prev_i, prev_pareto_idx)
    
    # Try each station as starting point
    for start in range(n):
        mask = 1 << start
        earliest, latest = time_windows[start]
        arrival = earliest  # arrive as early as possible
        if arrival > latest:
            continue  # can't start here
        dep_time = arrival + insp[start]
        cost = 0.0
        key = (mask, start)
        if key not in dp:
            dp[key] = []
        dp[key].append((cost, dep_time))
        parent[(mask, start, 0)] = None  # start state, store (start_station, arrival_time)
    
    # We need to reconstruct the path, so let's store parent info differently.
    # parent[(mask, i, cost, dep_time)] = (prev_mask, prev_i, prev_cost, prev_dep_time, arrival_time_at_i)
    # This is expensive. Let's store reconstruction info in a separate structure.
    
    # Actually, let's simplify path reconstruction:
    # After DP, we know the optimal (mask=full, i) endpoint. We can backtrack
    # by checking which predecessor state could have led to it.
    
    # For reconstruction, store:
    # back[(mask, i)] = list of (cost, dep_time, arrival_time_i, prev_mask, prev_j, prev_cost, prev_dep) 
    # parallel to dp[(mask, i)]
    
    back = {}
    
    for start in range(n):
        mask = 1 << start
        earliest, latest = time_windows[start]
        arrival = earliest
        if arrival > latest:
            continue
        dep_time = arrival + insp[start]
        cost = 0.0
        key = (mask, start)
        if key not in back:
            back[key] = []
        back[key].append((cost, dep_time, arrival, -1, -1, -1, -1))
    
    # Process masks in order of popcount (number of bits set)
    masks_by_popcount = [[] for _ in range(n + 1)]
    for mask in range(1, 1 << n):
        masks_by_popcount[bin(mask).count('1')].append(mask)
    
    for pc in range(1, n + 1):
        for mask in masks_by_popcount[pc]:
            # For each station i that is the last visited in mask
            for i in range(n):
                if not (mask & (1 << i)):
                    continue
                key_i = (mask, i)
                if key_i not in dp:
                    continue
                
                pareto_i = dp[key_i]
                back_i = back[key_i]
                
                # Try extending to station j not in mask
                for j in range(n):
                    if mask & (1 << j):
                        continue
                    
                    new_mask = mask | (1 << j)
                    tt = travel_time[i][j]
                    tc = cost_matrix[i][j]
                    earliest_j, latest_j = time_windows[j]
                    
                    key_j = (new_mask, j)
                    
                    for idx, (c, dt) in enumerate(pareto_i):
                        arrival_j = dt + tt
                        effective_arrival_j = max(arrival_j, earliest_j)
                        
                        if effective_arrival_j > latest_j:
                            continue  # infeasible
                        
                        new_cost = c + tc
                        new_dep = effective_arrival_j + insp[j]
                        
                        # Add to Pareto front of (new_mask, j)
                        # Check if dominated
                        if key_j in dp:
                            dominated = False
                            new_front = []
                            new_back = []
                            existing = dp[key_j]
                            existing_back = back[key_j]
                            
                            inserted = False
                            for k, (ec, edt) in enumerate(existing):
                                if ec <= new_cost and edt <= new_dep:
                                    dominated = True
                                    break
                            
                            if dominated:
                                continue
                            
                            # Remove entries dominated by new point
                            for k, (ec, edt) in enumerate(existing):
                                if new_cost <= ec and new_dep <= edt:
                                    continue  # dominated by new point, remove
                                new_front.append((ec, edt))
                                new_back.append(existing_back[k])
                            
                            new_front.append((new_cost, new_dep))
                            new_back.append((new_cost, new_dep, effective_arrival_j, mask, i, c, dt))
                            
                            # Sort by cost
                            combined = list(zip(new_front, new_back))
                            combined.sort(key=lambda x: (x[0][0], x[0][1]))
                            
                            # Limit Pareto front size
                            if len(combined) > MAX_PARETO:
                                combined = combined[:MAX_PARETO]
                            
                            dp[key_j] = [x[0] for x in combined]
                            back[key_j] = [x[1] for x in combined]
                        else:
                            dp[key_j] = [(new_cost, new_dep)]
                            back[key_j] = [(new_cost, new_dep, effective_arrival_j, mask, i, c, dt)]
    
    # Find the best solution: minimum cost among all dp[(full_mask, i)]
    best_cost = INF
    best_end = -1
    best_idx = -1
    
    for i in range(n):
        key = (full_mask, i)
        if key in dp:
            for idx, (c, dt) in enumerate(dp[key]):
                if c < best_cost:
                    best_cost = c
                    best_end = i
                    best_idx = idx
    
    if best_end == -1:
        # No feasible solution found
        # Return best effort: try to find any partial solution or report infeasible
        # Try to find the largest mask with a solution
        best_partial_mask = 0
        best_partial_cost = INF
        best_partial_end = -1
        best_partial_idx = -1
        
        for (mask, i), pareto in dp.items():
            if bin(mask).count('1') > bin(best_partial_mask).count('1') or \
               (bin(mask).count('1') == bin(best_partial_mask).count('1') and pareto[0][0] < best_partial_cost):
                best_partial_mask = mask
                best_partial_cost = pareto[0][0]
                best_partial_end = i
                best_partial_idx = 0
        
        if best_partial_end == -1:
            return {'route': [], 'total_cost': 0, 'arrival_times': [], 'feasible': False}
        
        # Reconstruct partial route
        route, arrival_times, total_cost = _reconstruct(back, best_partial_mask, best_partial_end, best_partial_idx)
        return {'route': route, 'total_cost': total_cost, 'arrival_times': arrival_times, 'feasible': False}
    
    # Reconstruct the optimal route
    route, arrival_times, total_cost = _reconstruct(back, full_mask, best_end, best_idx)
    
    return {'route': route, 'total_cost': total_cost, 'arrival_times': arrival_times, 'feasible': True}


def _reconstruct(back, mask, end, idx):
    """Reconstruct path from back-tracking data."""
    route = []
    arrival_times = []
    
    current_mask = mask
    current_i = end
    
    # Find the entry in back that matches
    # back[(mask, i)] = list of (cost, dep_time, arrival_time_i, prev_mask, prev_j, prev_cost, prev_dep)
    
    path = []
    
    while current_mask > 0 and current_i >= 0:
        key = (current_mask, current_i)
        if key not in back:
            break
        
        entries = back[key]
        
        # Find the matching entry by idx or by matching cost/dep
        if idx < len(entries):
            entry = entries[idx]
        else:
            break
        
        cost, dep_time, arrival_time, prev_mask, prev_j, prev_cost, prev_dep = entry
        
        path.append((current_i, arrival_time))
        
        if prev_j < 0:
            # This is a start state
            break
        
        # Find idx in prev state
        prev_key = (prev_mask, prev_j)
        if prev_key in back:
            prev_entries = back[prev_key]
            found_idx = -1
            for k, pe in enumerate(prev_entries):
                if abs(pe[0] - prev_cost) < 1e-12 and abs(pe[1] - prev_dep) < 1e-12:
                    found_idx = k
                    break
            if found_idx == -1:
                found_idx = 0
            idx = found_idx
        
        current_mask = prev_mask
        current_i = prev_j
    
    path.reverse()
    route = [p[0] for p in path]
    arrival_times = [p[1] for p in path]
    
    total_cost = 0
    for k in range(1, len(route)):
        # We don't have cost_matrix here, but we stored cost in back
        pass
    
    # Get total cost from the final back entry
    key = (mask, end)
    if key in back and idx < len(back[key]):
        total_cost = back[key][idx][0]
    else:
        total_cost = 0
    
    # Recalculate total cost from the stored value
    return route, arrival_times, total_cost


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
    
    # Generate time windows
    # Station 0 has early window, others spread out
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 100)
        latest = earliest + random.uniform(50, 200)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Sort time windows to make problem more feasible
    # (stations with earlier windows should be visited first ideally)
    
    inspection_time = 5.0
    speed = 1.0
    
    print(f"Number of stations: {n}")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print()
    
    print("Cost matrix (first 5x5):")
    for i in range(min(5, n)):
        print([cost_matrix[i][j] for j in range(min(5, n))])
    print("...")
    print()
    
    print("Time windows (first 10):")
    for i in range(min(10, n)):
        print(f"  Station {i}: [{time_windows[i][0]}, {time_windows[i][1]}]")
    print("...")
    print()
    
    start_time = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.time() - start_time
    
    print("=" * 60)
    print("Result:")
    print(f"  Feasible: {result['feasible']}")
    print(f"  Route: {result['route']}")
    print(f"  Total cost: {result['total_cost']}")
    print(f"  Arrival times: {[round(t, 2) for t in result['arrival_times']]}")
    print(f"  Number of stations visited: {len(result['route'])}")
    print(f"  Elapsed time: {elapsed:.4f} seconds")
    print("=" * 60)
    
    # Verify solution
    if result['feasible'] and len(result['route']) > 0:
        print("\nVerification:")
        route = result['route']
        arrivals = result['arrival_times']
        total_cost_check = 0
        
        for idx in range(len(route)):
            station = route[idx]
            arr = arrivals[idx]
            tw = time_windows[station]
            status = "OK" if tw[0] <= arr <= tw[1] else "VIOLATED"
            print(f"  Station {station}: arrive={arr:.2f}, window=[{tw[0]}, {tw[1]}] {status}")
            
            if idx > 0:
                prev = route[idx - 1]
                total_cost_check += cost_matrix[prev][station]
        
        print(f"\n  Verified total cost: {total_cost_check:.2f}")
        print(f"  Reported total cost: {result['total_cost']:.2f}")
        match = abs(total_cost_check - result['total_cost']) < 0.01
        print(f"  Cost match: {match}")


if __name__ == "__main__":
    main()