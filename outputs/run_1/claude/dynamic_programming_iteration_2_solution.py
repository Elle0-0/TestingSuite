import itertools


def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    
    if n == 1:
        return {
            "feasible": True,
            "route": [0, 0],
            "arrival_times": [0, 0],
            "total_energy": 0
        }
    
    stations = list(range(1, n))
    
    # DP with bitmask over stations 1..n-1
    # State: (visited_mask, current_station) -> (min_energy, earliest_feasible_arrival_time, route)
    # We need to track time carefully: we want minimum energy, but among those, feasible timing.
    # Actually, since travel time = cost / speed, and we want to minimize energy while respecting time windows,
    # we need to carefully handle this.
    
    # For a given permutation of visits, the arrival times are determined.
    # Travel time from i to j = cost_matrix[i][j] / speed (we'll use integer division or exact)
    
    # DP state: (mask, current_node) -> list of (total_energy, current_time) Pareto-optimal states
    # Since we need to find minimum energy route that is feasible, and waiting is allowed,
    # we should track (mask, node) -> best (energy, time) pairs
    
    # Simplification: use (mask, node) -> (min_energy, earliest_arrival_time for that energy)
    # But energy and time might trade off. Let's use a more careful approach.
    
    # Actually, in standard TSP with time windows, the order matters for feasibility.
    # Let's use DP: dp[mask][i] = (min_energy, earliest_possible_current_time) 
    # where mask is set of visited stations (among 1..n-1), i is current station.
    # We track the minimum current_time for each energy level, but that's complex.
    
    # Since n is likely small (demonstration), let's use:
    # dp[mask][i] = minimum (energy, time) where we pick the one with min energy among feasible, 
    # or if multiple have same energy, pick earliest time.
    
    # More precisely: dp[mask][i] = list of Pareto-optimal (energy, arrival_time) pairs
    # A pair (e1, t1) dominates (e2, t2) if e1 <= e2 and t1 <= t2.
    
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    # dp[mask][i] = list of (energy, time, parent_mask, parent_node) -> Pareto front of (energy, time)
    INF = float('inf')
    
    # dp[mask][node] -> list of (energy, current_time)
    dp = {}
    parent = {}
    
    # Initialize: start at node 0, time 0
    for i in stations:
        bit = 1 << (i - 1)
        travel_time = cost_matrix[0][i] / speed
        travel_energy = cost_matrix[0][i]
        arrival = travel_time
        tw_start, tw_end = time_windows[i]
        
        if arrival > tw_end:
            continue
        
        actual_start = max(arrival, tw_start)
        departure = actual_start + inspection_time
        
        dp[(bit, i)] = [(travel_energy, departure, arrival)]
        parent[(bit, i, travel_energy, departure, arrival)] = (0, 0, 0, 0, 0)
    
    # Expand
    for mask in range(1, full_mask + 1):
        for i in stations:
            if not (mask & (1 << (i - 1))):
                continue
            if (mask, i) not in dp:
                continue
            
            for energy, depart_time, arr_time_i in dp[(mask, i)]:
                for j in stations:
                    if mask & (1 << (j - 1)):
                        continue
                    
                    new_mask = mask | (1 << (j - 1))
                    travel_time = cost_matrix[i][j] / speed
                    travel_energy_ij = cost_matrix[i][j]
                    
                    arrival_j = depart_time + travel_time
                    tw_start_j, tw_end_j = time_windows[j]
                    
                    if arrival_j > tw_end_j:
                        continue
                    
                    actual_start_j = max(arrival_j, tw_start_j)
                    departure_j = actual_start_j + inspection_time
                    new_energy = energy + travel_energy_ij
                    
                    key = (new_mask, j)
                    new_entry = (new_energy, departure_j, arrival_j)
                    
                    if key not in dp:
                        dp[key] = []
                    
                    # Check if dominated
                    dominated = False
                    to_remove = []
                    for idx, (e, t, a) in enumerate(dp[key]):
                        if e <= new_energy and t <= departure_j:
                            dominated = True
                            break
                        if new_energy <= e and departure_j <= t:
                            to_remove.append(idx)
                    
                    if not dominated:
                        for idx in sorted(to_remove, reverse=True):
                            old = dp[key][idx]
                            pkey = (key[0], key[1], old[0], old[1], old[2])
                            if pkey in parent:
                                del parent[pkey]
                            dp[key].pop(idx)
                        
                        dp[key].append(new_entry)
                        parent[(new_mask, j, new_energy, departure_j, arrival_j)] = (mask, i, energy, depart_time, arr_time_i)
    
    # Find best complete route returning to 0
    best_energy = INF
    best_state = None
    
    for i in stations:
        key = (full_mask, i)
        if key not in dp:
            continue
        for energy, depart_time, arr_time_i in dp[key]:
            travel_energy_back = cost_matrix[i][0]
            total = energy + travel_energy_back
            if total < best_energy:
                best_energy = total
                best_state = (full_mask, i, energy, depart_time, arr_time_i)
                return_travel_time = cost_matrix[i][0] / speed
                final_arrival = depart_time + return_travel_time
    
    if best_state is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route = [0]
    arrival_times_dict = {0: final_arrival}  # arrival back at 0
    
    path = []
    state = best_state
    while state != (0, 0, 0, 0, 0):
        mask, node, energy, depart, arr = state
        path.append((node, arr))
        pkey = (mask, node, energy, depart, arr)
        state = parent[pkey]
    
    path.reverse()
    
    route = [0]
    arrival_times = [0]
    
    for node, arr in path:
        route.append(node)
        arrival_times.append(arr)
    
    # Return to 0
    last_node = route[-1]
    last_state = best_state
    last_depart = last_state[3]
    return_time = last_depart + cost_matrix[last_node][0] / speed
    
    route.append(0)
    arrival_times.append(return_time)
    
    # Convert to int where possible
    arrival_times_clean = []
    for t in arrival_times:
        if t == int(t):
            arrival_times_clean.append(int(t))
        else:
            arrival_times_clean.append(t)
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times_clean,
        "total_energy": int(best_energy) if best_energy == int(best_energy) else best_energy
    }


def main():
    # Example: 4 stations (0 is base, 1-3 are monitoring stations)
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # Time windows: (earliest, latest) for each station
    # Station 0 has no constraint (base)
    time_windows = [
        (0, 1000),   # base - not used
        (5, 50),     # station 1
        (10, 60),    # station 2
        (30, 90),    # station 3
    ]
    
    inspection_time = 5
    speed = 1
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Number of stations: {len(cost_matrix)}")
    print(f"Inspection time per station: {inspection_time}")
    print(f"Speed: {speed}")
    print()
    print(f"Time windows:")
    for i in range(1, len(cost_matrix)):
        print(f"  Station {i}: [{time_windows[i][0]}, {time_windows[i][1]}]")
    print()
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival times: {result['arrival_times']}")
    print(f"Total energy: {result['total_energy']}")
    
    # Also demonstrate an infeasible case
    print("\n=== Infeasible Example ===")
    tight_windows = [
        (0, 1000),
        (1, 5),      # very tight - must arrive between 1 and 5
        (1, 5),      # very tight - conflicts
        (1, 5),      # very tight - conflicts
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Arrival times: {result2['arrival_times']}")
    print(f"Total energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()