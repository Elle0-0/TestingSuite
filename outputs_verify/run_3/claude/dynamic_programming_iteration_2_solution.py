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
    # State: (visited_mask, current_station) -> (min_energy, arrival_time_at_current, parent_info)
    # We need to track timing, so we can't just minimize energy independently.
    # Since timing depends on the path order, we need to track both energy and time.
    # With time windows, a state with higher energy but earlier arrival might enable more future visits.
    # For correctness with time windows, we store (best_energy, earliest_arrival) per state.
    # Actually we need to be more careful: we want minimum energy among feasible completions.
    # We'll use DP: dp[mask][i] = (min_energy_to_reach_this_state, arrival_time) 
    # But arrival time affects feasibility of future states. We need to track arrival time.
    # For small n, we can store the best (energy, time) and if there's a conflict, keep Pareto-optimal.
    # For simplicity and correctness, let's keep only the state with minimum arrival time among
    # minimum energy states, or use Pareto front.
    
    # dp[mask][i] = list of (total_energy, arrival_time) Pareto-optimal (both less is better)
    
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    # dp[mask][i] stores Pareto-optimal set of (energy, time)
    dp = [[None for _ in range(n)] for _ in range(1 << num_stations)]
    parent = [[None for _ in range(n)] for _ in range(1 << num_stations)]
    
    # Initialize: start at station 0 at time 0
    for i in stations:
        bit = 1 << (i - 1)
        travel_time = cost_matrix[0][i] // speed if speed != 0 else cost_matrix[0][i]
        travel_energy = cost_matrix[0][i]
        arrival = travel_time
        tw_start, tw_end = time_windows[i]
        
        if arrival > tw_end:
            continue
        
        actual_start = max(arrival, tw_start)
        departure = actual_start + inspection_time
        
        dp[bit][i] = [(travel_energy, departure, arrival)]
        parent[bit][i] = [(0, 0, None)]  # came from station 0, mask 0
    
    for mask in range(1, 1 << num_stations):
        for i in stations:
            if not (mask & (1 << (i - 1))):
                continue
            if dp[mask][i] is None:
                continue
            
            for j in stations:
                if mask & (1 << (j - 1)):
                    continue
                
                new_mask = mask | (1 << (j - 1))
                travel_energy = cost_matrix[i][j]
                travel_time = travel_energy // speed if speed != 0 else travel_energy
                
                tw_start, tw_end = time_windows[j]
                
                for idx, (energy, depart_time, _arr) in enumerate(dp[mask][i]):
                    arrival_j = depart_time + travel_time
                    
                    if arrival_j > tw_end:
                        continue
                    
                    actual_start_j = max(arrival_j, tw_start)
                    departure_j = actual_start_j + inspection_time
                    new_energy = energy + travel_energy
                    
                    # Add to dp[new_mask][j] with Pareto check
                    if dp[new_mask][j] is None:
                        dp[new_mask][j] = [(new_energy, departure_j, arrival_j)]
                        parent[new_mask][j] = [(i, mask, idx)]
                    else:
                        # Check if dominated
                        dominated = False
                        to_remove = []
                        for k, (e, t, _a) in enumerate(dp[new_mask][j]):
                            if e <= new_energy and t <= departure_j:
                                dominated = True
                                break
                            if new_energy <= e and departure_j <= t:
                                to_remove.append(k)
                        
                        if not dominated:
                            for k in sorted(to_remove, reverse=True):
                                dp[new_mask][j].pop(k)
                                parent[new_mask][j].pop(k)
                            dp[new_mask][j].append((new_energy, departure_j, arrival_j))
                            parent[new_mask][j].append((i, mask, idx))
    
    # Find best complete route returning to 0
    best_energy = float('inf')
    best_end = None
    
    for i in stations:
        if dp[full_mask][i] is None:
            continue
        for idx, (energy, depart_time, _arr) in enumerate(dp[full_mask][i]):
            return_energy = cost_matrix[i][0]
            total = energy + return_energy
            if total < best_energy:
                best_energy = total
                best_end = (i, idx)
    
    if best_end is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route = [0]  # will prepend, then reverse
    arrival_times_map = {}
    
    current_station, current_idx = best_end
    current_mask = full_mask
    
    path_reversed = []
    while current_station != 0:
        energy, depart, arr = dp[current_mask][current_station][current_idx]
        path_reversed.append((current_station, arr))
        prev_station, prev_mask, prev_idx = parent[current_mask][current_station][current_idx]
        current_station = prev_station
        current_mask = prev_mask
        current_idx = prev_idx if prev_idx is not None else 0
    
    path_reversed.reverse()
    
    route = [0]
    arrival_times = [0]
    for station, arr in path_reversed:
        route.append(station)
        arrival_times.append(arr)
    
    # Return to base
    last = route[-1]
    return_travel = cost_matrix[last][0] // speed if speed != 0 else cost_matrix[last][0]
    # departure time of last station
    last_mask_idx = None
    # Find departure of last station
    last_station = route[-1]
    # We already have this from reconstruction
    last_energy, last_depart, last_arr = dp[full_mask][best_end[0]][best_end[1]]
    return_arrival = last_depart + return_travel
    
    route.append(0)
    arrival_times.append(return_arrival)
    
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
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
        (0, 1000),   # Station 0 (base) - not used
        (5, 50),     # Station 1: can arrive between time 5 and 50
        (10, 60),    # Station 2: can arrive between time 10 and 60
        (15, 80),    # Station 3: can arrive between time 15 and 80
    ]
    
    inspection_time = 5
    speed = 1
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Number of stations: {len(cost_matrix)}")
    print(f"Inspection time per station: {inspection_time}")
    print(f"Speed: {speed}")
    print(f"Time windows: {time_windows[1:]}")
    print()
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival times: {result['arrival_times']}")
    print(f"Total energy: {result['total_energy']}")
    
    if result['feasible']:
        print("\nDetailed schedule:")
        for i, station in enumerate(result['route']):
            arr = result['arrival_times'][i]
            if station == 0:
                if i == 0:
                    print(f"  Depart base (station 0) at time {arr}")
                else:
                    print(f"  Return to base (station 0) at time {arr}")
            else:
                tw = time_windows[station]
                wait = max(0, tw[0] - arr)
                print(f"  Station {station}: arrive at {arr}, window={tw}, wait={wait}, inspect until {max(arr, tw[0]) + inspection_time}")
    
    # Example with infeasible time windows
    print("\n=== Infeasible Example ===")
    tight_windows = [
        (0, 1000),
        (5, 8),      # Very tight window for station 1
        (10, 12),    # Very tight window for station 2
        (15, 18),    # Very tight window for station 3
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Time windows: {tight_windows[1:]}")
    print(f"Feasible: {result2['feasible']}")
    print(f"Route: {result2['route']}")
    print(f"Arrival times: {result2['arrival_times']}")
    print(f"Total energy: {result2['total_energy']}")


if __name__ == "__main__":
    main()