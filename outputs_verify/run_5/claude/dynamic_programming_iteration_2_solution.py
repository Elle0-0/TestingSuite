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
    num_stations = len(stations)
    
    # DP with bitmask
    # State: (current_node, visited_set_bitmask)
    # Value: (min_energy, earliest_possible_arrival_time_at_current_node)
    # We need to track time carefully because of time windows
    
    # Since time windows constrain feasibility, we need to track both energy and time.
    # For the same (node, visited_set), different arrival times might lead to different
    # future feasibilities. However, if we want minimum energy, we should track
    # (node, visited) -> list of (energy, time) Pareto-optimal states.
    
    # For small n, we can use bitmask DP.
    # State: (current_node, visited_mask) -> (min_energy, arrival_time)
    # But arrival time matters for future feasibility. We want to minimize energy
    # but also keep arrival time as early as possible to maximize future feasibility.
    
    # Strategy: For each state (node, mask), store the best (energy, time) where
    # "best" means Pareto-optimal: no other state dominates in both energy AND time.
    
    INF = float('inf')
    
    # dp[(node, mask)] = list of (energy, time) tuples, Pareto-optimal
    dp = {}
    
    # Initialize: start from node 0 at time 0
    for i in stations:
        bit = 1 << (i - 1)
        travel_time = cost_matrix[0][i] // speed if speed != 0 else cost_matrix[0][i]
        travel_energy = cost_matrix[0][i]
        arrival = travel_time
        
        tw_start, tw_end = time_windows[i]
        
        if arrival > tw_end:
            continue
        
        actual_start = max(arrival, tw_start)
        departure_time = actual_start + inspection_time
        
        dp[(i, bit)] = [(travel_energy, departure_time, arrival)]
    
    full_mask = (1 << num_stations) - 1
    
    for mask in range(1, full_mask + 1):
        for curr in stations:
            curr_bit = 1 << (curr - 1)
            if not (mask & curr_bit):
                continue
            if (curr, mask) not in dp:
                continue
            
            for next_station in stations:
                next_bit = 1 << (next_station - 1)
                if mask & next_bit:
                    continue
                
                new_mask = mask | next_bit
                
                for (energy, depart_time, _arr) in dp[(curr, mask)]:
                    travel_time = cost_matrix[curr][next_station] // speed if speed != 0 else cost_matrix[curr][next_station]
                    travel_energy = cost_matrix[curr][next_station]
                    
                    arrival = depart_time + travel_time
                    tw_start, tw_end = time_windows[next_station]
                    
                    if arrival > tw_end:
                        continue
                    
                    actual_start = max(arrival, tw_start)
                    departure = actual_start + inspection_time
                    new_energy = energy + travel_energy
                    
                    key = (next_station, new_mask)
                    new_state = (new_energy, departure, arrival)
                    
                    if key not in dp:
                        dp[key] = [new_state]
                    else:
                        # Add if Pareto-optimal (not dominated by any existing)
                        dominated = False
                        to_remove = []
                        for idx2, (e2, t2, a2) in enumerate(dp[key]):
                            if e2 <= new_energy and t2 <= departure:
                                dominated = True
                                break
                            if new_energy <= e2 and departure <= t2:
                                to_remove.append(idx2)
                        
                        if not dominated:
                            for idx2 in reversed(to_remove):
                                dp[key].pop(idx2)
                            dp[key].append(new_state)
    
    # Find best route back to 0
    best_energy = INF
    best_last = None
    best_arrival_at_0 = None
    
    for curr in stations:
        key = (curr, full_mask)
        if key not in dp:
            continue
        for (energy, depart_time, _arr) in dp[key]:
            travel_time = cost_matrix[curr][0] // speed if speed != 0 else cost_matrix[curr][0]
            travel_energy = cost_matrix[curr][0]
            total_energy = energy + travel_energy
            arrival_at_0 = depart_time + travel_time
            
            if total_energy < best_energy:
                best_energy = total_energy
                best_last = (curr, energy, depart_time)
                best_arrival_at_0 = arrival_at_0
    
    if best_energy == INF:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct path
    route = [0]
    arrival_times = [0]
    
    # Backtrack to find the actual route
    # We need to reconstruct. Let's do it by tracing back.
    curr_node = best_last[0]
    curr_energy = best_last[1]
    curr_depart = best_last[2]
    curr_mask = full_mask
    
    path_reversed = [(curr_node, curr_depart)]
    
    while curr_mask != (1 << (curr_node - 1)):
        prev_mask = curr_mask ^ (1 << (curr_node - 1))
        found = False
        for prev_node in stations:
            prev_bit = 1 << (prev_node - 1)
            if not (prev_mask & prev_bit):
                continue
            key = (prev_node, prev_mask)
            if key not in dp:
                continue
            
            travel_energy = cost_matrix[prev_node][curr_node]
            travel_time = travel_energy // speed if speed != 0 else travel_energy
            
            for (e, t, _a) in dp[key]:
                arrival_at_curr = t + travel_time
                tw_start, tw_end = time_windows[curr_node]
                actual_start = max(arrival_at_curr, tw_start)
                departure_at_curr = actual_start + inspection_time
                
                if abs(e + travel_energy - curr_energy) < 1e-9 and abs(departure_at_curr - curr_depart) < 1e-9:
                    path_reversed.append((prev_node, t))
                    curr_node = prev_node
                    curr_energy = e
                    curr_depart = t
                    curr_mask = prev_mask
                    found = True
                    break
            if found:
                break
        
        if not found:
            return {
                "feasible": False,
                "route": [],
                "arrival_times": [],
                "total_energy": 0
            }
    
    path_reversed.reverse()
    
    # Now rebuild arrival times properly
    route = [0]
    arrival_times_list = [0]
    current_time = 0
    
    for i, (node, _depart) in enumerate(path_reversed):
        prev = route[-1]
        travel_time = cost_matrix[prev][node] // speed if speed != 0 else cost_matrix[prev][node]
        arrival = current_time + travel_time
        tw_start, tw_end = time_windows[node]
        actual_start = max(arrival, tw_start)
        departure = actual_start + inspection_time
        
        route.append(node)
        arrival_times_list.append(arrival)
        current_time = departure
    
    # Return to 0
    prev = route[-1]
    travel_time = cost_matrix[prev][0] // speed if speed != 0 else cost_matrix[prev][0]
    arrival_home = current_time + travel_time
    route.append(0)
    arrival_times_list.append(arrival_home)
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times_list,
        "total_energy": best_energy
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
    # Station 0 (base) has no constraint
    time_windows = [
        (0, 1000),   # base - no real constraint
        (5, 50),     # station 1: can arrive between time 5 and 50
        (10, 60),    # station 2: can arrive between time 10 and 60
        (15, 80),    # station 3: can arrive between time 15 and 80
    ]
    
    inspection_time = 5
    speed = 1
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival Times: {result['arrival_times']}")
    print(f"Total Energy: {result['total_energy']}")
    
    if result['feasible']:
        print("\nDetailed Schedule:")
        for i, station in enumerate(result['route']):
            arrival = result['arrival_times'][i]
            if station == 0:
                if i == 0:
                    print(f"  Depart base (station 0) at time {arrival}")
                else:
                    print(f"  Return to base (station 0) at time {arrival}")
            else:
                tw = time_windows[station]
                wait = max(0, tw[0] - arrival)
                print(f"  Station {station}: arrive at {arrival}, "
                      f"time window [{tw[0]}, {tw[1]}], "
                      f"wait {wait}, "
                      f"inspect {inspection_time}")
    
    print("\n=== Infeasible Example ===")
    # Tight time windows that make it impossible
    tight_windows = [
        (0, 1000),
        (5, 8),      # very tight
        (5, 8),      # very tight
        (5, 8),      # very tight
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Arrival Times: {result2['arrival_times']}")
    print(f"Total Energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()