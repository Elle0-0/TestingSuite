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
    # We need to track timing carefully. For each state, we want to minimize energy,
    # but we also need to ensure time windows are met.
    # 
    # Actually, since travel time = cost / speed, and we want to minimize energy (sum of costs),
    # but timing constraints may force us to choose different routes, we need to be careful.
    # 
    # We'll use DP: dp[mask][i] = (min_energy_to_reach_state, earliest_time_at_i_after_inspection)
    # mask = set of visited stations (among 1..n-1), i = current station
    # We track the earliest completion time because arriving earlier is always at least as good as later.
    
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    INF = float('inf')
    
    # dp[mask][i] = (min_energy, earliest_departure_time, parent_mask, parent_station)
    # i is index in stations (0-based among non-depot), actual station = i+1
    dp = [[None for _ in range(num_stations)] for _ in range(1 << num_stations)]
    
    # Initialize: start from depot (0) to each station
    for i in range(num_stations):
        station = i + 1
        travel_cost = cost_matrix[0][station]
        travel_time = travel_cost / speed
        arrival_time = 0 + travel_time  # depart depot at time 0
        
        tw_start, tw_end = time_windows[station]
        
        # Wait if early
        service_start = max(arrival_time, tw_start)
        
        if service_start > tw_end:
            continue  # Can't visit this station first
        
        departure_time = service_start + inspection_time
        mask = 1 << i
        dp[mask][i] = (travel_cost, departure_time, arrival_time, -1, -1)  # (energy, depart_time, arrival_time, prev_mask, prev_station_idx)
    
    # Fill DP
    for mask in range(1, 1 << num_stations):
        for i in range(num_stations):
            if dp[mask][i] is None:
                continue
            if not (mask & (1 << i)):
                continue
            
            energy_so_far, depart_time, _, _, _ = dp[mask][i]
            station_i = i + 1
            
            for j in range(num_stations):
                if mask & (1 << j):
                    continue  # already visited
                
                station_j = j + 1
                travel_cost = cost_matrix[station_i][station_j]
                travel_time = travel_cost / speed
                arrival_time = depart_time + travel_time
                
                tw_start, tw_end = time_windows[station_j]
                service_start = max(arrival_time, tw_start)
                
                if service_start > tw_end:
                    continue
                
                new_departure = service_start + inspection_time
                new_energy = energy_so_far + travel_cost
                new_mask = mask | (1 << j)
                
                if dp[new_mask][j] is None or new_energy < dp[new_mask][j][0] or (new_energy == dp[new_mask][j][0] and new_departure < dp[new_mask][j][1]):
                    dp[new_mask][j] = (new_energy, new_departure, arrival_time, mask, i)
    
    # Find best complete route returning to depot
    best_energy = INF
    best_last = -1
    best_return_time = INF
    
    for i in range(num_stations):
        if dp[full_mask][i] is None:
            continue
        energy_so_far, depart_time, _, _, _ = dp[full_mask][i]
        station_i = i + 1
        return_cost = cost_matrix[station_i][0]
        total_energy = energy_so_far + return_cost
        return_time = depart_time + return_cost / speed
        
        if total_energy < best_energy:
            best_energy = total_energy
            best_last = i
            best_return_time = return_time
    
    if best_last == -1:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route_stations = []
    arrival_times_list = []
    mask = full_mask
    current = best_last
    
    while current != -1:
        entry = dp[mask][current]
        route_stations.append(current + 1)
        arrival_times_list.append(entry[2])  # arrival_time at this station
        prev_mask = entry[3]
        prev_station = entry[4]
        mask = prev_mask
        current = prev_station
    
    route_stations.reverse()
    arrival_times_list.reverse()
    
    # Build full route and arrival times
    route = [0] + route_stations + [0]
    arrival_times = [0] + arrival_times_list + [best_return_time]
    
    # Convert to int if possible
    arrival_times_clean = []
    for t in arrival_times:
        if t == int(t):
            arrival_times_clean.append(int(t))
        else:
            arrival_times_clean.append(t)
    
    total_energy = int(best_energy) if best_energy == int(best_energy) else best_energy
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times_clean,
        "total_energy": total_energy
    }


def main():
    # Example: 4 stations (0=depot, 1, 2, 3)
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # Time windows: (earliest, latest) arrival time for each station
    # Station 0 (depot) has no constraint
    time_windows = [
        (0, 1000),   # depot - not used
        (5, 20),     # station 1: arrive between 5 and 20
        (15, 50),    # station 2: arrive between 15 and 50
        (30, 70),    # station 3: arrive between 30 and 70
    ]
    
    inspection_time = 5
    speed = 1
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Number of stations: {len(cost_matrix)}")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print()
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival times: {result['arrival_times']}")
    print(f"Total energy: {result['total_energy']}")
    
    if result['feasible']:
        print("\nDetailed schedule:")
        route = result['route']
        arrivals = result['arrival_times']
        for idx in range(len(route)):
            station = route[idx]
            arr = arrivals[idx]
            if station == 0:
                if idx == 0:
                    print(f"  Depart depot at time {arr}")
                else:
                    print(f"  Return to depot at time {arr}")
            else:
                tw = time_windows[station]
                print(f"  Station {station}: arrive at {arr}, window [{tw[0]}, {tw[1]}]")
    
    # Example with infeasible time windows
    print("\n=== Infeasible Example ===")
    tight_windows = [
        (0, 1000),
        (0, 5),      # must arrive at station 1 by time 5
        (0, 5),      # must arrive at station 2 by time 5
        (0, 5),      # must arrive at station 3 by time 5
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Total energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()