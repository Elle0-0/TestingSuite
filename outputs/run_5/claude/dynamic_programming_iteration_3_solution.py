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
    
    # Travel time between stations
    travel_time = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if speed > 0:
                travel_time[i][j] = cost_matrix[i][j] / speed
            else:
                travel_time[i][j] = cost_matrix[i][j]
    
    full_mask = (1 << n) - 1
    
    # DP with bitmask: dp[mask][i] = (min_cost, earliest_finish_time)
    # State: visited set (mask), current station (i)
    # Value: minimum cost to reach this state, and the earliest time we can finish at station i
    
    INF = float('inf')
    
    # dp[mask][i] = (best_cost, earliest_completion_time)
    # We want to minimize cost; among equal costs, minimize time
    # Actually, we need to track time because of time windows
    # Multiple (cost, time) pairs might be needed, but for efficiency with bitmask DP,
    # we track the minimum arrival time for each (mask, i) state
    # If time windows are loose, minimum time is a good heuristic
    # For correctness with time windows, we need: arrive <= latest, wait until earliest if early
    
    # dp[mask][i] = minimum cost to visit all stations in mask, ending at station i,
    #               with associated arrival/completion time
    # But cost and time are coupled (waiting doesn't cost extra, but affects feasibility)
    # We'll track (min_cost, min_time_at_min_cost) 
    # Actually, we should track the earliest possible completion time at minimum cost,
    # because arriving earlier gives more flexibility for future stations.
    
    # For each (mask, i), store the best (cost, completion_time) - Pareto optimal set
    # To keep it tractable, we store the minimum completion time achievable,
    # since lower completion time is always better or equal for future decisions.
    # Among paths with feasible time, we pick minimum cost.
    # But a higher-cost path with earlier time might lead to better overall solution...
    
    # Approach: dp[mask][i] = list of Pareto-optimal (cost, time) pairs
    # Pareto: no other dominates in both cost and time
    # For n=20, 2^20 * 20 = ~20M states. Pareto sets should be small in practice.
    
    # Simpler approach that works well: dp[mask][i] = minimum time to complete,
    # then separately track cost. But cost and time are different objectives.
    
    # Let's use: dp[mask][i] = dict mapping to (min_cost, completion_time)
    # where for each (mask, i) we keep the Pareto front of (cost, time)
    
    # For performance, let's try a simpler model first:
    # If cost == travel distance and there's no separate cost structure,
    # then cost = sum of travel distances, time = sum of travel times + waits + inspections
    # With speed=1, cost and time are related but waits decouple them.
    
    # Let's maintain for each (mask, i) a list of (cost, time) Pareto-optimal states.
    
    # Initialize: start from each station (or station 0)
    # Let's assume we start from station 0
    
    # Actually, let's try starting from each station and returning to start (TSP-like)
    # Or: the problem might be open path. Let me handle both.
    # Based on typical formulation: start at station 0, visit all, return to 0.
    
    # Let's do: start at 0, visit all stations, return to 0.
    
    start = 0
    
    # Pareto front: list of (cost, time) where no entry dominates another
    # dp_table[mask][i] = sorted list of (cost, time) Pareto-optimal pairs
    
    dp_table = [[None] * n for _ in range(1 << n)]
    
    # Initialize: start at station 0
    earliest_0, latest_0 = time_windows[start]
    start_time = earliest_0  # arrive at earliest possible
    if start_time > latest_0:
        return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    completion_0 = start_time + insp[start]
    init_mask = 1 << start
    dp_table[init_mask][start] = [(0.0, completion_0)]  # cost=0 at start, time=completion
    
    # Also try starting from any station
    # For generality, let's allow starting from station 0 only (depot)
    
    def add_to_pareto(front, cost, time_val):
        """Add (cost, time_val) to Pareto front, removing dominated entries."""
        if front is None:
            return [(cost, time_val)]
        
        # Check if new point is dominated
        for c, t in front:
            if c <= cost and t <= time_val:
                return front  # dominated, don't add
        
        # Remove entries dominated by new point
        new_front = [(c, t) for c, t in front if not (cost <= c and time_val <= t)]
        new_front.append((cost, time_val))
        return new_front
    
    # Process masks in order of popcount
    for mask in range(1, 1 << n):
        for i in range(n):
            if not (mask & (1 << i)):
                continue
            if dp_table[mask][i] is None:
                continue
            
            pareto = dp_table[mask][i]
            
            # Try extending to station j
            for j in range(n):
                if mask & (1 << j):
                    continue  # already visited
                
                earliest_j, latest_j = time_windows[j]
                new_mask = mask | (1 << j)
                
                for cost_so_far, completion_i in pareto:
                    # Travel from i to j
                    tt = travel_time[i][j]
                    arrival_j = completion_i + tt
                    
                    # Check time window
                    if arrival_j > latest_j:
                        continue  # infeasible, too late
                    
                    # Wait if too early
                    start_j = max(arrival_j, earliest_j)
                    completion_j = start_j + insp[j]
                    
                    new_cost = cost_so_far + cost_matrix[i][j]
                    
                    dp_table[new_mask][j] = add_to_pareto(
                        dp_table[new_mask][j], new_cost, completion_j
                    )
    
    # Find best solution: all stations visited, return to start (or just end)
    # Let's check if return to start is needed. Typical TSP returns to start.
    # I'll compute both and prefer the one that makes sense.
    # Let's return to start (station 0).
    
    best_cost = INF
    best_last = -1
    best_time = INF
    return_to_start = True
    
    for i in range(n):
        if dp_table[full_mask][i] is None:
            continue
        for cost_val, comp_time in dp_table[full_mask][i]:
            if return_to_start:
                total = cost_val + cost_matrix[i][start]
            else:
                total = cost_val
            if total < best_cost or (total == best_cost and comp_time < best_time):
                best_cost = total
                best_last = i
                best_time = comp_time
    
    if best_last == -1:
        # Try without returning to start
        return_to_start = False
        for i in range(n):
            if dp_table[full_mask][i] is None:
                continue
            for cost_val, comp_time in dp_table[full_mask][i]:
                if cost_val < best_cost:
                    best_cost = cost_val
                    best_last = i
                    best_time = comp_time
    
    if best_last == -1:
        return {'route': [], 'total_cost': INF, 'arrival_times': [], 'feasible': False}
    
    # Reconstruct path
    route = []
    arrival_times = []
    
    # Backtrack
    current = best_last
    mask = full_mask
    path = [current]
    
    # We need to find the actual target cost/time at each step
    # Find the specific (cost, time) we used for the last station
    target_cost = best_cost - (cost_matrix[best_last][start] if return_to_start else 0)
    target_time = best_time  # completion time at last station
    
    # Find matching entry
    best_entry = None
    if dp_table[full_mask][best_last]:
        for c, t in dp_table[full_mask][best_last]:
            if abs(c - target_cost) < 1e-9:
                if best_entry is None or t < best_entry[1]:
                    best_entry = (c, t)
    
    if best_entry is None:
        # fallback
        best_entry = min(dp_table[full_mask][best_last], key=lambda x: x[0])
    
    current_cost, current_time = best_entry
    
    while mask != (1 << start):
        prev_mask = mask ^ (1 << current)
        
        if prev_mask == 0:
            break
            
        found = False
        for prev in range(n):
            if not (prev_mask & (1 << prev)):
                continue
            if dp_table[prev_mask][prev] is None:
                continue
            
            for c, t in dp_table[prev_mask][prev]:
                expected_cost = c + cost_matrix[prev][current]
                if abs(expected_cost - current_cost) > 1e-9:
                    continue
                
                # Check time consistency
                arrival = t + travel_time[prev][current]
                earliest_cur, latest_cur = time_windows[current]
                start_cur = max(arrival, earliest_cur)
                completion_cur = start_cur + insp[current]
                
                if abs(completion_cur - current_time) < 1e-9:
                    path.append(prev)
                    current = prev
                    mask = prev_mask
                    current_cost = c
                    current_time = t
                    found = True
                    break
            if found:
                break
        
        if not found:
            # Relaxed matching - just find any valid predecessor
            for prev in range(n):
                if not (prev_mask & (1 << prev)):
                    continue
                if dp_table[prev_mask][prev] is None:
                    continue
                for c, t in dp_table[prev_mask][prev]:
                    expected_cost = c + cost_matrix[prev][current]
                    if abs(expected_cost - current_cost) < 1e-9:
                        path.append(prev)
                        current = prev
                        mask = prev_mask
                        current_cost = c
                        current_time = t
                        found = True
                        break
                if found:
                    break
            if not found:
                break
    
    path.reverse()
    
    # Compute arrival times
    arrival_times = []
    current_time_sim = time_windows[path[0]][0]
    arrival_times.append(current_time_sim)
    finish_time = current_time_sim + insp[path[0]]
    
    for idx in range(1, len(path)):
        prev_station = path[idx - 1]
        cur_station = path[idx]
        tt = travel_time[prev_station][cur_station]
        arrival = finish_time + tt
        earliest, latest = time_windows[cur_station]
        actual_start = max(arrival, earliest)
        arrival_times.append(arrival)
        finish_time = actual_start + insp[cur_station]
    
    if return_to_start and (len(path) == 0 or path[-1] != start):
        pass  # route returns to start implicitly
    
    return {
        'route': path,
        'total_cost': best_cost,
        'arrival_times': arrival_times,
        'feasible': True
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
    
    # Generate time windows (generous to ensure feasibility)
    time_windows = []
    for i in range(n):
        earliest = random.uniform(0, 100)
        latest = earliest + random.uniform(200, 500)
        time_windows.append((round(earliest, 2), round(latest, 2)))
    
    # Make station 0 available from time 0
    time_windows[0] = (0.0, 600.0)
    
    inspection_time = 5.0
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
    print(f"Total cost: {result['total_cost']:.2f}")
    print(f"Arrival times: {[f'{t:.2f}' for t in result['arrival_times']]}")
    print(f"Elapsed time: {elapsed:.4f} seconds")


if __name__ == "__main__":
    main()