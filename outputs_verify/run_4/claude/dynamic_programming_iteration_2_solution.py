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
    
    # Number of stations to visit (excluding depot 0)
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
    
    num_stations = len(stations)
    full_mask = (1 << num_stations) - 0  # not used directly
    
    # dp[mask][i] = (min_energy, earliest_departure_time) for having visited the stations in mask,
    # currently at station stations[i] (where bit i corresponds to stations[i])
    # We also track arrival times for reconstruction
    
    INF = float('inf')
    
    # dp[mask][i] = (min_energy, departure_time)
    # departure_time = arrival_time + inspection_time (if feasible)
    dp = {}
    parent = {}
    arrival_at = {}
    
    # Initialize: go from depot 0 to each station
    for i in range(num_stations):
        s = stations[i]
        mask = 1 << i
        travel_time = cost_matrix[0][s] / speed if speed != 1 else cost_matrix[0][s]
        travel_energy = cost_matrix[0][s]
        arrival_time = travel_time  # depart at time 0
        
        tw_start, tw_end = time_windows[s]
        
        # Wait if early
        effective_start = max(arrival_time, tw_start)
        
        if effective_start > tw_end:
            continue  # infeasible
        
        departure_time = effective_start + inspection_time
        dp[(mask, i)] = (travel_energy, departure_time)
        arrival_at[(mask, i)] = effective_start
        parent[(mask, i)] = None
    
    # Expand
    for mask in range(1, 1 << num_stations):
        for i in range(num_stations):
            if not (mask & (1 << i)):
                continue
            if (mask, i) not in dp:
                continue
            
            cur_energy, cur_depart = dp[(mask, i)]
            s_i = stations[i]
            
            for j in range(num_stations):
                if mask & (1 << j):
                    continue
                
                s_j = stations[j]
                new_mask = mask | (1 << j)
                
                travel_time = cost_matrix[s_i][s_j] / speed if speed != 1 else cost_matrix[s_i][s_j]
                travel_energy = cost_matrix[s_i][s_j]
                
                arrival_time = cur_depart + travel_time
                tw_start, tw_end = time_windows[s_j]
                
                effective_start = max(arrival_time, tw_start)
                
                if effective_start > tw_end:
                    continue
                
                new_energy = cur_energy + travel_energy
                new_depart = effective_start + inspection_time
                
                if (new_mask, j) not in dp or new_energy < dp[(new_mask, j)][0] or \
                   (new_energy == dp[(new_mask, j)][0] and new_depart < dp[(new_mask, j)][1]):
                    dp[(new_mask, j)] = (new_energy, new_depart)
                    arrival_at[(new_mask, j)] = effective_start
                    parent[(new_mask, j)] = (mask, i)
    
    # Find best complete route (all stations visited, return to depot)
    full_mask = (1 << num_stations) - 1
    best_energy = INF
    best_last = -1
    best_arrival_home = 0
    
    for i in range(num_stations):
        if (full_mask, i) not in dp:
            continue
        
        cur_energy, cur_depart = dp[(full_mask, i)]
        s_i = stations[i]
        return_energy = cost_matrix[s_i][0]
        total_energy = cur_energy + return_energy
        
        if total_energy < best_energy:
            best_energy = total_energy
            best_last = i
            return_time = cur_depart + (cost_matrix[s_i][0] / speed if speed != 1 else cost_matrix[s_i][0])
            best_arrival_home = return_time
    
    if best_last == -1:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route_indices = []
    arrivals = []
    
    state = (full_mask, best_last)
    while state is not None:
        mask, i = state
        route_indices.append(stations[i])
        arrivals.append(arrival_at[state])
        state = parent[state]
    
    route_indices.reverse()
    arrivals.reverse()
    
    route = [0] + route_indices + [0]
    arrival_times = [0] + arrivals + [best_arrival_home]
    
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
    # Station 0 (depot) has no constraint
    time_windows = [
        (0, 1000),   # depot - not used
        (5, 50),     # station 1
        (10, 60),    # station 2
        (30, 100),   # station 3
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
    tight_time_windows = [
        (0, 1000),
        (1, 3),      # station 1: window too early/tight
        (1, 3),      # station 2: window too early/tight
        (1, 3),       # station 3: window too early/tight
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_time_windows, inspection_time, speed)
    
    print("=== Infeasible Example ===")
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Arrival Times: {result2['arrival_times']}")
    print(f"Total Energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()