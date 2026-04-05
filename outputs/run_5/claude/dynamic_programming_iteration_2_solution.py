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
    # We need to track time carefully: we want minimum energy, but among routes with same energy,
    # we need feasibility. Actually, a route is either feasible or not based on time windows.
    # We need to find the minimum energy feasible route.
    
    # Since time windows create complex interactions, we use DP:
    # dp[mask][i] = (min_energy, earliest_arrival_time_at_i) for feasible partial routes
    # But minimum energy and earliest arrival can conflict. We need to track both.
    # 
    # Actually, for a given mask and endpoint, travel energy is determined by the path taken.
    # Time depends on travel times + wait times + inspection times.
    # Travel time from i to j = cost_matrix[i][j] / speed (using cost as distance proxy)
    # Energy = sum of cost_matrix edges
    
    # dp[mask][i] = list of (energy, arrival_time) Pareto-optimal states
    # To keep it tractable, for small n we can track best states.
    
    # For simplicity with reasonable n, use: dp[mask][i] = (best_energy, earliest_time) 
    # where we prioritize feasibility, then energy.
    # We'll store (energy, time) and keep only Pareto-optimal ones.
    
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    # dp[mask][i] = list of (energy, arrival_time, parent_mask, parent_node)
    # For tractability, keep only best per (mask, i): minimize energy among feasible, track time
    
    INF = float('inf')
    
    # dp[mask][i] = (energy, arrival_time)  -- best feasible state (min energy, then min time)
    dp = {}
    parent = {}
    
    # Start at station 0, time = 0
    for j in range(num_stations):
        station = j + 1
        mask = 1 << j
        travel_time = cost_matrix[0][station] / speed
        arrival = travel_time
        tw_start, tw_end = time_windows[station]
        
        if arrival > tw_end:
            continue
        
        effective_arrival = max(arrival, tw_start)
        energy = cost_matrix[0][station]
        dp[(mask, station)] = (energy, effective_arrival)
        parent[(mask, station)] = (0, 0, 0)  # (prev_mask, prev_station, dummy)
    
    for mask in range(1, full_mask + 1):
        for j in range(num_stations):
            station_j = j + 1
            if not (mask & (1 << j)):
                continue
            if (mask, station_j) not in dp:
                continue
            
            energy_j, time_j = dp[(mask, station_j)]
            depart_time = time_j + inspection_time
            
            for k in range(num_stations):
                if mask & (1 << k):
                    continue
                station_k = k + 1
                new_mask = mask | (1 << k)
                travel_time = cost_matrix[station_j][station_k] / speed
                arrival = depart_time + travel_time
                tw_start, tw_end = time_windows[station_k]
                
                if arrival > tw_end:
                    continue
                
                effective_arrival = max(arrival, tw_start)
                new_energy = energy_j + cost_matrix[station_j][station_k]
                
                if (new_mask, station_k) not in dp or new_energy < dp[(new_mask, station_k)][0] or \
                   (new_energy == dp[(new_mask, station_k)][0] and effective_arrival < dp[(new_mask, station_k)][1]):
                    dp[(new_mask, station_k)] = (new_energy, effective_arrival)
                    parent[(new_mask, station_k)] = (mask, station_j)
    
    # Find best complete route returning to 0
    best_energy = INF
    best_end = -1
    best_arrival_home = INF
    
    for j in range(num_stations):
        station_j = j + 1
        if (full_mask, station_j) not in dp:
            continue
        energy_j, time_j = dp[(full_mask, station_j)]
        depart_time = time_j + inspection_time
        travel_time = cost_matrix[station_j][0] / speed
        arrival_home = depart_time + travel_time
        total_energy = energy_j + cost_matrix[station_j][0]
        
        if total_energy < best_energy or (total_energy == best_energy and arrival_home < best_arrival_home):
            best_energy = total_energy
            best_end = station_j
            best_arrival_home = arrival_home
    
    if best_end == -1:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route = [0]
    arrival_times = [best_arrival_home]
    
    current_mask = full_mask
    current_station = best_end
    path = []
    
    while current_station != 0:
        energy_c, time_c = dp[(current_mask, current_station)]
        path.append((current_station, time_c))
        prev_mask, prev_station = parent[(current_mask, current_station)]
        current_mask = prev_mask
        current_station = prev_station
    
    path.reverse()
    
    route = [0]
    arrival_times_list = [0]
    for station, arr_time in path:
        route.append(station)
        arrival_times_list.append(arr_time)
    route.append(0)
    arrival_times_list.append(best_arrival_home)
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times_list,
        "total_energy": int(best_energy)
    }


def main():
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # time_windows[i] = (earliest, latest) for station i
    # Station 0 is the base, its window is not used
    time_windows = [
        (0, 1000),   # base station (ignored)
        (5, 50),     # station 1
        (10, 60),    # station 2
        (15, 80),    # station 3
    ]
    
    inspection_time = 5
    speed = 1
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival Times: {result['arrival_times']}")
    print(f"Total Energy: {result['total_energy']}")
    
    print()
    
    # Example with infeasible time windows
    tight_windows = [
        (0, 1000),
        (5, 8),      # very tight window for station 1
        (10, 12),    # very tight window for station 2
        (15, 18),    # very tight window for station 3
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    
    print("=== Infeasible Example ===")
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Arrival Times: {result2['arrival_times']}")
    print(f"Total Energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()