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
    # We need to track timing carefully. For each state, among all paths that reach it,
    # we want to find ones that are feasible and minimize energy.
    # However, there's a subtlety: a path with higher energy but earlier arrival might
    # enable visiting future stations within their windows. So we need to be careful.
    
    # We'll use DP: dp[mask][i] = list of (energy, arrival_time, route, arrival_times_list)
    # To keep it tractable, for each (mask, i) we keep Pareto-optimal states 
    # (non-dominated in both energy and arrival_time).
    
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    # dp[mask][station] -> list of (energy, time, route, arrival_times)
    # We'll keep Pareto-optimal: no entry dominated in both energy and time
    INF = float('inf')
    
    dp = {}
    
    # Initialize: start at station 0 at time 0, go to each station
    for i in stations:
        idx = i - 1
        mask = 1 << idx
        travel_time = cost_matrix[0][i] // speed if speed != 0 else cost_matrix[0][i]
        travel_energy = cost_matrix[0][i]
        
        arrival = travel_time
        tw_start, tw_end = time_windows[i]
        
        # Wait if early
        effective_arrival = max(arrival, tw_start)
        
        if effective_arrival > tw_end:
            continue  # infeasible
        
        departure_time = effective_arrival + inspection_time
        
        key = (mask, i)
        dp[key] = [(travel_energy, departure_time, [0, i], [0, effective_arrival])]
    
    # Expand
    for count in range(2, num_stations + 1):
        for key in list(dp.keys()):
            mask, last = key
            if bin(mask).count('1') != count - 1:
                continue
            for state in dp[key]:
                energy, current_time, route, arrival_times = state
                for j in stations:
                    jdx = j - 1
                    if mask & (1 << jdx):
                        continue
                    
                    new_mask = mask | (1 << jdx)
                    travel_time = cost_matrix[last][j] // speed if speed != 0 else cost_matrix[last][j]
                    travel_energy = cost_matrix[last][j]
                    
                    arrival = current_time + travel_time
                    tw_start, tw_end = time_windows[j]
                    effective_arrival = max(arrival, tw_start)
                    
                    if effective_arrival > tw_end:
                        continue
                    
                    departure_time = effective_arrival + inspection_time
                    new_energy = energy + travel_energy
                    
                    new_key = (new_mask, j)
                    new_state = (new_energy, departure_time, route + [j], arrival_times + [effective_arrival])
                    
                    if new_key not in dp:
                        dp[new_key] = [new_state]
                    else:
                        # Add if not dominated
                        dominated = False
                        to_remove = []
                        for idx2, existing in enumerate(dp[new_key]):
                            e_en, e_time = existing[0], existing[1]
                            if e_en <= new_energy and e_time <= departure_time:
                                dominated = True
                                break
                            if new_energy <= e_en and departure_time <= e_time:
                                to_remove.append(idx2)
                        
                        if not dominated:
                            dp[new_key] = [s for idx2, s in enumerate(dp[new_key]) if idx2 not in to_remove]
                            dp[new_key].append(new_state)
    
    # Find best complete route returning to 0
    best_energy = INF
    best_route = None
    best_arrival_times = None
    
    for last in stations:
        key = (full_mask, last)
        if key not in dp:
            continue
        for state in dp[key]:
            energy, current_time, route, arrival_times = state
            return_energy = cost_matrix[last][0]
            return_time = current_time + cost_matrix[last][0] // speed if speed != 0 else current_time + cost_matrix[last][0]
            
            total_energy = energy + return_energy
            if total_energy < best_energy:
                best_energy = total_energy
                best_route = route + [0]
                best_arrival_times = arrival_times + [return_time]
    
    if best_route is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    return {
        "feasible": True,
        "route": best_route,
        "arrival_times": best_arrival_times,
        "total_energy": best_energy
    }


def main():
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # time_windows[i] = (earliest, latest) for station i
    # Station 0 is the base, its window is irrelevant
    time_windows = [
        (0, 1000),   # base station (ignored)
        (5, 50),     # station 1
        (10, 60),    # station 2
        (30, 80),    # station 3
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
    for i, tw in enumerate(time_windows):
        if i == 0:
            print(f"  Station {i} (base): N/A")
        else:
            print(f"  Station {i}: [{tw[0]}, {tw[1]}]")
    print()
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival times: {result['arrival_times']}")
    print(f"Total energy: {result['total_energy']}")
    
    print()
    print("=== Infeasible Example ===")
    
    tight_windows = [
        (0, 1000),
        (1, 5),      # very tight window for station 1
        (1, 5),      # very tight window for station 2
        (1, 5),      # very tight window for station 3
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Arrival times: {result2['arrival_times']}")
    print(f"Total energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()