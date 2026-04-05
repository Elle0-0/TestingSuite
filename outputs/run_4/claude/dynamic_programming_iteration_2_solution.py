import itertools


def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    
    if n <= 1:
        return {
            "feasible": True,
            "route": [0],
            "arrival_times": [0],
            "total_energy": 0
        }
    
    # Number of stations to visit (excluding depot 0)
    stations = list(range(1, n))
    
    # DP with bitmask over stations 1..n-1
    # State: (visited_set_bitmask, current_station) -> (min_energy, earliest_feasible_arrival_time)
    # We need to track both energy and time. Since time windows constrain feasibility,
    # we need to find routes that are both feasible and minimize energy.
    
    # For n up to ~15-20 this bitmask DP is feasible
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    # dp[mask][i] = (min_energy, arrival_time, parent_mask, parent_station)
    # mask: bitmask of visited stations (among 1..n-1)
    # i: current station index (0-based in stations list, so station = i+1)
    
    INF = float('inf')
    
    # dp[mask][i] = list of (energy, time) Pareto-optimal states
    # To keep it simpler, since we want minimum energy among feasible routes,
    # and time is determined by the path (with possible waiting), let's track:
    # dp[mask][i] = (min_energy_to_reach_here, earliest_arrival_time_at_i) 
    # But energy and time can conflict. A path with more energy might arrive earlier.
    # We need Pareto front or we simplify: travel time = cost / speed (assuming cost ~ distance)
    
    # Travel time from station i to station j = cost_matrix[i][j] / speed
    
    # dp[mask][i] = best (energy, arrival_time) pairs
    # Since we want minimum energy overall, and times are determined by path + waiting,
    # let's keep a dict: dp[mask][station] = list of (energy, time) non-dominated tuples
    
    dp = {}
    parent = {}
    
    # Initialize: go from depot (0) to each station
    for idx, s in enumerate(stations):
        mask = 1 << idx
        travel_time = cost_matrix[0][s] / speed
        energy = cost_matrix[0][s]
        arrival = travel_time
        
        # Check time window
        tw_start, tw_end = time_windows[s]
        if arrival > tw_end:
            continue  # infeasible
        effective_arrival = max(arrival, tw_start)
        
        dp[(mask, s)] = [(energy, effective_arrival)]
        parent[(mask, s, energy, effective_arrival)] = (0, 0, 0, 0)  # (prev_mask, prev_station, prev_energy, prev_time)
    
    # Iterate over all masks
    for mask in range(1, full_mask + 1):
        for idx, s in enumerate(stations):
            if not (mask & (1 << idx)):
                continue
            if (mask, s) not in dp:
                continue
            
            for energy_so_far, time_so_far in dp[(mask, s)]:
                depart_time = time_so_far + inspection_time
                
                for idx2, s2 in enumerate(stations):
                    if mask & (1 << idx2):
                        continue
                    
                    new_mask = mask | (1 << idx2)
                    travel_time = cost_matrix[s][s2] / speed
                    arrival = depart_time + travel_time
                    new_energy = energy_so_far + cost_matrix[s][s2]
                    
                    tw_start, tw_end = time_windows[s2]
                    if arrival > tw_end:
                        continue
                    effective_arrival = max(arrival, tw_start)
                    
                    # Add to dp[new_mask][s2]
                    key = (new_mask, s2)
                    if key not in dp:
                        dp[key] = []
                    
                    # Check if dominated
                    dominated = False
                    new_list = []
                    for (e, t) in dp[key]:
                        if e <= new_energy and t <= effective_arrival:
                            dominated = True
                            new_list.append((e, t))
                        elif new_energy <= e and effective_arrival <= t:
                            # new dominates old, skip old
                            continue
                        else:
                            new_list.append((e, t))
                    
                    if not dominated:
                        new_list.append((new_energy, effective_arrival))
                        parent[(new_mask, s2, new_energy, effective_arrival)] = (mask, s, energy_so_far, time_so_far)
                    
                    dp[key] = new_list
    
    # Find best complete route returning to depot
    best_energy = INF
    best_end = None
    best_arrival_at_end = None
    
    for idx, s in enumerate(stations):
        key = (full_mask, s)
        if key not in dp:
            continue
        for (energy, arrival_time) in dp[key]:
            depart_time = arrival_time + inspection_time
            travel_time = cost_matrix[s][0] / speed
            return_energy = energy + cost_matrix[s][0]
            return_time = depart_time + travel_time
            
            if return_energy < best_energy:
                best_energy = return_energy
                best_end = s
                best_arrival_at_end = arrival_time
                best_return_time = return_time
    
    if best_end is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct path
    route = [0]
    arrival_times = [0]
    
    path_stations = []
    path_arrivals = []
    
    cur_mask = full_mask
    cur_station = best_end
    cur_energy = best_energy - cost_matrix[best_end][0]  # energy before return
    cur_time = best_arrival_at_end
    
    # We need to match with the energy stored in dp
    # Actually let me re-derive: the energy at the end station before returning
    # Walk back through parents
    chain = []
    
    # Find the matching entry
    e = cur_energy
    t = cur_time
    s = cur_station
    m = cur_mask
    
    chain.append((s, t))
    
    while m != 0:
        pkey = (m, s, e, t)
        if pkey not in parent:
            # Try to find approximate match (floating point issues)
            found = False
            for pk, pv in parent.items():
                if pk[0] == m and pk[1] == s and abs(pk[2] - e) < 1e-9 and abs(pk[3] - t) < 1e-9:
                    pm, ps, pe, pt = pv
                    found = True
                    break
            if not found:
                break
        else:
            pm, ps, pe, pt = parent[pkey]
        
        if pm == 0 and ps == 0:
            break
        
        chain.append((ps, pt))
        m = pm
        s = ps
        e = pe
        t = pt
    
    chain.reverse()
    
    route = [0] + [c[0] for c in chain] + [0]
    arrival_times = [0] + [c[1] for c in chain] + [best_return_time]
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": int(best_energy)
    }


def main():
    # Example with 4 stations (0 is depot, 1-3 are monitoring stations)
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # Time windows: (earliest, latest) for each station
    # Station 0 (depot) doesn't have a meaningful window
    time_windows = [
        (0, 1000),   # depot - no constraint
        (5, 25),     # station 1: can arrive between time 5 and 25
        (10, 40),    # station 2: can arrive between time 10 and 40
        (15, 60),    # station 3: can arrive between time 15 and 60
    ]
    
    inspection_time = 5  # 5 time units at each station
    speed = 1  # 1 unit distance per time unit
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival Times: {result['arrival_times']}")
    print(f"Total Energy: {result['total_energy']}")
    
    print("\n--- Detailed Schedule ---")
    if result['feasible']:
        route = result['route']
        arrivals = result['arrival_times']
        for i, (station, arrival) in enumerate(zip(route, arrivals)):
            if station == 0 and i == 0:
                print(f"  Depart depot (station 0) at time 0")
            elif station == 0 and i == len(route) - 1:
                print(f"  Return to depot (station 0) at time {arrival:.1f}")
            else:
                tw = time_windows[station]
                print(f"  Station {station}: arrive at {arrival:.1f}, "
                      f"window [{tw[0]}, {tw[1]}], "
                      f"depart at {arrival + inspection_time:.1f}")
    
    # Test infeasible case
    print("\n=== Infeasible Example ===")
    tight_windows = [
        (0, 1000),
        (1, 5),      # Very tight window for station 1
        (1, 5),      # Very tight window for station 2
        (1, 5),      # Very tight window for station 3
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Total Energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()