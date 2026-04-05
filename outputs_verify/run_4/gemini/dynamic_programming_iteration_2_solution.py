import itertools

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": True, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        start_time = float(time_windows[0][0])
        return {"feasible": True, "route": [0, 0], "arrival_times": [start_time, start_time], "total_energy": 0}

    # dp[mask][i] stores a tuple: (minimum energy cost, earliest departure time)
    dp = [[(float('inf'), float('inf')) for _ in range(n)] for _ in range(1 << n)]
    parent = [[-1 for _ in range(n)] for _ in range(1 << n)]

    # Base cases: paths from depot (0) to other stations (i)
    start_time = float(time_windows[0][0])
    for i in range(1, n):
        mask = (1 << i) | 1
        travel_time_0_i = cost_matrix[0][i] / speed
        arrival_time_at_i = start_time + travel_time_0_i
        
        earliest_i, latest_i = time_windows[i]

        if arrival_time_at_i <= latest_i:
            cost = cost_matrix[0][i]
            departure_time = max(arrival_time_at_i, earliest_i) + inspection_time
            dp[mask][i] = (cost, departure_time)
            parent[mask][i] = 0

    # Iterate through subsets of increasing size (from 3 to n)
    for size in range(3, n + 1):
        for subset in itertools.combinations(range(1, n), size - 1):
            mask = 1 | sum(1 << i for i in subset)
            for i in subset:
                prev_mask = mask ^ (1 << i)
                
                # Find the best predecessor 'j' for station 'i'
                for j in subset:
                    if i == j:
                        continue
                        
                    prev_cost, prev_departure_time = dp[prev_mask][j]

                    if prev_cost == float('inf'):
                        continue

                    travel_time_j_i = cost_matrix[j][i] / speed
                    arrival_time_at_i = prev_departure_time + travel_time_j_i
                    
                    earliest_i, latest_i = time_windows[i]

                    if arrival_time_at_i <= latest_i:
                        new_cost = prev_cost + cost_matrix[j][i]
                        new_departure_time = max(arrival_time_at_i, earliest_i) + inspection_time
                        
                        current_best_cost, current_best_time = dp[mask][i]
                        
                        if new_cost < current_best_cost or \
                           (new_cost == current_best_cost and new_departure_time < current_best_time):
                            dp[mask][i] = (new_cost, new_departure_time)
                            parent[mask][i] = j
    
    # Find the optimal final path back to the depot
    final_mask = (1 << n) - 1
    min_total_energy = float('inf')
    last_station = -1

    for i in range(1, n):
        cost_to_i, departure_time_from_i = dp[final_mask][i]
        
        if cost_to_i == float('inf'):
            continue
            
        travel_time_i_0 = cost_matrix[i][0] / speed
        final_arrival_time = departure_time_from_i + travel_time_i_0
        _, latest_0 = time_windows[0]

        if final_arrival_time <= latest_0:
            total_energy = cost_to_i + cost_matrix[i][0]
            if total_energy < min_total_energy:
                min_total_energy = total_energy
                last_station = i

    if last_station == -1:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": -1}

    # Reconstruct route
    route = []
    curr_mask = final_mask
    curr_station = last_station
    while curr_station != 0:
        route.insert(0, curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station
    
    route.insert(0, 0)
    route.append(0)

    # Reconstruct arrival times for the final route
    arrival_times = []
    current_time = start_time
    arrival_times.append(current_time)

    for k in range(len(route) - 1):
        u, v = route[k], route[k+1]
        earliest_u, _ = time_windows[u]
        
        departure_time_from_u = max(current_time, earliest_u)
        if u != 0:
            departure_time_from_u += inspection_time
        
        travel_time_u_v = cost_matrix[u][v] / speed
        arrival_at_v = departure_time_from_u + travel_time_u_v
        arrival_times.append(arrival_at_v)
        current_time = arrival_at_v
        
    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": int(min_total_energy)
    }

def main():
    cost_matrix_1 = [
        [0, 10, 80, 20],
        [10, 0, 25, 25],
        [80, 25, 0, 30],
        [20, 25, 30, 0]
    ]
    time_windows_1 = [
        (0, 200),
        (10, 100),
        (20, 100),
        (30, 100)
    ]
    inspection_time_1 = 5
    speed_1 = 1

    result_1 = find_optimal_route(cost_matrix_1, time_windows_1, inspection_time_1, speed_1)
    
    print("Example 1:")
    print(f"Feasible: {result_1['feasible']}")
    print(f"Route: {result_1['route']}")
    print(f"Arrival Times: {[round(t, 2) for t in result_1['arrival_times']]}")
    print(f"Total Energy: {result_1['total_energy']}")
    print("-" * 20)

    cost_matrix_2 = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    time_windows_2 = [
        (0, 1000),
        (10, 25),
        (20, 45),
        (40, 65)
    ]
    inspection_time_2 = 5
    speed_2 = 1

    result_2 = find_optimal_route(cost_matrix_2, time_windows_2, inspection_time_2, speed_2)

    print("Example 2:")
    print(f"Feasible: {result_2['feasible']}")
    print(f"Route: {result_2['route']}")
    print(f"Arrival Times: {[round(t, 2) for t in result_2['arrival_times']]}")
    print(f"Total Energy: {result_2['total_energy']}")
    print("-" * 20)
    
    cost_matrix_3 = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    time_windows_3 = [
        (0, 1000),
        (20, 100),
        (30, 100),
        (40, 100),
    ]
    inspection_time_3 = 5
    speed_3 = 1
    
    result_3 = find_optimal_route(cost_matrix_3, time_windows_3, inspection_time_3, speed_3)
    
    print("Example 3:")
    print(f"Feasible: {result_3['feasible']}")
    print(f"Route: {result_3['route']}")
    print(f"Arrival Times: {[round(t, 2) for t in result_3['arrival_times']]}")
    print(f"Total Energy: {result_3['total_energy']}")


if __name__ == "__main__":
    main()