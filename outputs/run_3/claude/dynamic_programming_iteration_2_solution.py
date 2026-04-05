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
    
    # Number of stations excluding depot
    stations = list(range(1, n))
    
    if not stations:
        return {
            "feasible": True,
            "route": [0, 0],
            "arrival_times": [0, 0],
            "total_energy": 0
        }
    
    # DP with bitmask over stations 1..n-1
    # State: (visited_set_bitmask, current_station)
    # Value: (min_energy, earliest_finish_time, parent_info for reconstruction)
    
    num_stations = len(stations)  # n-1 stations
    full_mask = (1 << num_stations) - 1
    
    # dp[mask][i] = (min_energy, earliest_arrival_time_at_i) 
    # where mask is the set of visited stations (among 1..n-1), i is index in stations list
    # We store the best (energy, arrival_time) and track for reconstruction
    
    INF = float('inf')
    
    # dp[mask][i] = list of (energy, arrival_time) - we keep Pareto-optimal front
    # Actually, let's keep it simpler: dp[mask][i] = (min_energy, arrival_time, departure_time)
    # But energy and time can conflict. We need to find minimum energy route that is time-feasible.
    
    # Since n is typically small for TSP, let's try: for each state, track (best_energy, corresponding_earliest_departure)
    # But we might need to track multiple Pareto-optimal states (energy vs time).
    
    # For correctness with time windows, we should track: dp[mask][i] = minimum energy to visit set mask ending at station i,
    # along with the earliest possible departure time from i given that energy-optimal path.
    # However, two paths with same energy but different times matter. And a higher-energy path might enable 
    # reaching future stations within their windows.
    
    # For small n, let's do: dp[mask][i] = dict of possible (energy -> earliest_departure_time)
    # Pruning dominated states where both energy and time are worse.
    
    # Given typical problem sizes for bitmask DP (n <= ~20), let's use Pareto front approach.
    
    # dp[mask][i] = list of (energy, departure_time) tuples, Pareto-optimal
    # A state (e1, t1) dominates (e2, t2) if e1 <= e2 and t1 <= t2
    
    dp = [[[] for _ in range(num_stations)] for _ in range(1 << num_stations)]
    parent = [[dict() for _ in range(num_stations)] for _ in range(1 << num_stations)]
    
    # Initialize: start from depot (0) to each station
    for idx, s in enumerate(stations):
        travel_time = cost_matrix[0][s] // speed if speed != 0 else cost_matrix[0][s]
        travel_energy = cost_matrix[0][s]
        arrival_time = 0 + travel_time  # depart depot at time 0
        
        tw_start, tw_end = time_windows[s]
        
        if arrival_time > tw_end:
            continue  # Can't make it in time
        
        actual_start = max(arrival_time, tw_start)
        departure_time = actual_start + inspection_time
        
        mask = 1 << idx
        dp[mask][idx] = [(travel_energy, departure_time)]
        parent[mask][idx][(travel_energy, departure_time)] = (0, -1, None)  # (prev_mask, prev_idx, prev_state)
    
    def add_to_pareto(front, new_entry):
        """Add entry to Pareto front, removing dominated entries. Returns True if added."""
        e_new, t_new = new_entry
        # Check if new entry is dominated
        for (e, t) in front:
            if e <= e_new and t <= t_new:
                return False  # dominated
        # Remove entries dominated by new
        front[:] = [(e, t) for (e, t) in front if not (e_new <= e and t_new <= t)]
        front.append(new_entry)
        return True
    
    # Fill DP
    for mask in range(1, 1 << num_stations):
        for idx in range(num_stations):
            if not (mask & (1 << idx)):
                continue
            if not dp[mask][idx]:
                continue
            
            s = stations[idx]
            
            for next_idx in range(num_stations):
                if mask & (1 << next_idx):
                    continue
                
                next_s = stations[next_idx]
                new_mask = mask | (1 << next_idx)
                travel_energy = cost_matrix[s][next_s]
                travel_time = cost_matrix[s][next_s] // speed if speed != 0 else cost_matrix[s][next_s]
                
                tw_start, tw_end = time_windows[next_s]
                
                for (energy, dep_time) in dp[mask][idx]:
                    arrival = dep_time + travel_time
                    
                    if arrival > tw_end:
                        continue
                    
                    actual_start = max(arrival, tw_start)
                    new_dep = actual_start + inspection_time
                    new_energy = energy + travel_energy
                    
                    new_state = (new_energy, new_dep)
                    if add_to_pareto(dp[new_mask][next_idx], new_state):
                        parent[new_mask][next_idx][new_state] = (mask, idx, (energy, dep_time))
    
    # Find best route: visit all stations and return to depot
    best_energy = INF
    best_last_idx = -1
    best_last_state = None
    
    for idx in range(num_stations):
        s = stations[idx]
        for (energy, dep_time) in dp[full_mask][idx]:
            return_energy = cost_matrix[s][0]
            return_time = cost_matrix[s][0] // speed if speed != 0 else cost_matrix[s][0]
            total_energy = energy + return_energy
            arrival_at_depot = dep_time + return_time
            
            if total_energy < best_energy:
                best_energy = total_energy
                best_last_idx = idx
                best_last_state = (energy, dep_time)
                best_arrival_depot = arrival_at_depot
    
    if best_energy == INF:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route_indices = []
    current_mask = full_mask
    current_idx = best_last_idx
    current_state = best_last_state
    
    while current_idx != -1:
        route_indices.append(current_idx)
        prev_mask, prev_idx, prev_state = parent[current_mask][current_idx][current_state]
        current_mask = prev_mask
        current_idx = prev_idx
        current_state = prev_state
    
    route_indices.reverse()
    
    # Build full route with station numbers and compute arrival times
    route = [0]
    arrival_times = [0]
    
    current_time = 0
    current_station = 0
    
    for idx in route_indices:
        s = stations[idx]
        travel_time = cost_matrix[current_station][s] // speed if speed != 0 else cost_matrix[current_station][s]
        arrival = current_time + travel_time
        tw_start, tw_end = time_windows[s]
        actual_start = max(arrival, tw_start)
        departure = actual_start + inspection_time
        
        route.append(s)
        arrival_times.append(arrival)
        
        current_time = departure
        current_station = s
    
    # Return to depot
    travel_time = cost_matrix[current_station][0] // speed if speed != 0 else cost_matrix[current_station][0]
    arrival_depot = current_time + travel_time
    route.append(0)
    arrival_times.append(arrival_depot)
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": best_energy
    }


def main():
    # Example: 4 stations (0 is depot, 1-3 are monitoring stations)
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # Time windows: (earliest, latest) arrival time for each station
    # Station 0 (depot) doesn't have a meaningful window
    time_windows = [
        (0, 1000),   # depot - not used
        (5, 50),     # station 1: arrive between time 5 and 50
        (10, 60),    # station 2: arrive between time 10 and 60
        (15, 80),    # station 3: arrive between time 15 and 80
    ]
    
    inspection_time = 5  # 5 time units at each station
    speed = 1  # travel time = distance / speed
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Number of stations: {len(cost_matrix)}")
    print(f"Inspection time per station: {inspection_time}")
    print(f"Speed: {speed}")
    print(f"Time windows: {time_windows[1:]}")
    print()
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print(f"Feasible: {result['feasible']}")
    if result['feasible']:
        print(f"Optimal route: {result['route']}")
        print(f"Arrival times: {result['arrival_times']}")
        print(f"Total energy: {result['total_energy']}")
        
        print("\nDetailed schedule:")
        route = result['route']
        arrival_times = result['arrival_times']
        for i, (station, arr) in enumerate(zip(route, arrival_times)):
            if i == 0:
                print(f"  Depart depot (station {station}) at time {arr}")
            elif i == len(route) - 1:
                print(f"  Return to depot (station {station}) at time {arr}")
            else:
                tw = time_windows[station]
                wait = max(0, tw[0] - arr)
                print(f"  Station {station}: arrive at {arr}, window={tw}, wait={wait}, "
                      f"inspect {max(arr, tw[0])}-{max(arr, tw[0]) + inspection_time}")
    else:
        print("No feasible route found!")
    
    # Example with infeasible time windows
    print("\n=== Infeasible Example ===")
    tight_windows = [
        (0, 1000),
        (1, 3),      # Very tight window for station 1
        (1, 3),      # Very tight window for station 2
        (1, 3),      # Very tight window for station 3
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    if not result2['feasible']:
        print("No feasible route exists with these tight time windows.")
    else:
        print(f"Route: {result2['route']}")
        print(f"Arrival times: {result2['arrival_times']}")
        print(f"Total energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()