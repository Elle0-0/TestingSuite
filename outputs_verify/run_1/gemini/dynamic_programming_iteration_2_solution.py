import math

def find_optimal_route(
    cost_matrix: list[list[int]],
    time_windows: list[tuple[int, int]],
    inspection_time: int,
    speed: int = 1
) -> dict:
    """
    Finds the optimal route for a drone visiting multiple stations with time windows.
    """
    n = len(cost_matrix)
    if n == 0:
        return {
            "feasible": True,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }
    if n == 1:
        return {
            "feasible": True,
            "route": [0, 0],
            "arrival_times": [time_windows[0][0], time_windows[0][0]],
            "total_energy": 0,
        }

    # dp[mask][i] = (earliest_start_inspection_time, min_energy)
    dp = [[(math.inf, math.inf) for _ in range(n)] for _ in range(1 << n)]
    path = [[-1 for _ in range(n)] for _ in range(1 << n)]

    # Base case: start at station 0
    start_time = time_windows[0][0]
    dp[1][0] = (start_time, 0)

    for mask in range(1, 1 << n):
        for i in range(n):
            if (mask >> i) & 1:  # If station i is in the current set
                if dp[mask][i][0] == math.inf:
                    continue

                current_time, current_energy = dp[mask][i]
                
                # Time when inspection at i finishes and drone departs
                departure_time = current_time + inspection_time

                for j in range(n):
                    if not ((mask >> j) & 1):  # If station j is not yet visited
                        travel_time = cost_matrix[i][j] / speed
                        arrival_at_j = departure_time + travel_time

                        earliest_j, latest_j = time_windows[j]

                        if arrival_at_j > latest_j:
                            continue  # This path is not feasible

                        # Drone waits if it arrives early
                        new_start_time_at_j = max(arrival_at_j, earliest_j)
                        new_energy = current_energy + cost_matrix[i][j]
                        
                        next_mask = mask | (1 << j)
                        
                        existing_energy, _ = dp[next_mask][j]

                        # Optimize for energy, then for time
                        if new_energy < existing_energy:
                            dp[next_mask][j] = (new_start_time_at_j, new_energy)
                            path[next_mask][j] = i
                        elif new_energy == existing_energy:
                            if new_start_time_at_j < dp[next_mask][j][0]:
                                dp[next_mask][j] = (new_start_time_at_j, new_energy)
                                path[next_mask][j] = i

    # Find the best complete tour ending at station 0
    final_mask = (1 << n) - 1
    min_total_energy = math.inf
    best_last_station = -1

    for i in range(1, n):
        if dp[final_mask][i][0] != math.inf:
            last_station_time, last_station_energy = dp[final_mask][i]
            
            # Calculate final leg back to base
            return_travel_time = cost_matrix[i][0] / speed
            return_departure_time = last_station_time + inspection_time
            arrival_at_base = return_departure_time + return_travel_time
            
            earliest_0, latest_0 = time_windows[0]

            if arrival_at_base <= latest_0:
                total_energy = last_station_energy + cost_matrix[i][0]
                if total_energy < min_total_energy:
                    min_total_energy = total_energy
                    best_last_station = i

    if best_last_station == -1:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": -1,
        }

    # Reconstruct the optimal path
    route = []
    curr_station = best_last_station
    mask = final_mask
    while curr_station != 0:
        route.insert(0, curr_station)
        prev_station = path[mask][curr_station]
        mask ^= (1 << curr_station)
        curr_station = prev_station
    
    route.insert(0, 0)
    route.append(0)

    # Re-calculate arrival times for the final route
    arrival_times = []
    current_time = time_windows[0][0]
    arrival_times.append(current_time)

    for i in range(len(route) - 1):
        u, v = route[i], route[i+1]
        
        # Departure time from u after waiting (if needed) and inspecting
        departure_time_from_u = max(current_time, time_windows[u][0]) + inspection_time
        travel_time_uv = cost_matrix[u][v] / speed
        current_time = departure_time_from_u + travel_time_uv
        arrival_times.append(current_time)

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": min_total_energy,
    }

def main():
    """
    Demonstrates the solution with an example that includes time windows.
    """
    cost_matrix = [
        [0, 20, 42, 35],
        [20, 0, 30, 34],
        [42, 30, 0, 12],
        [35, 34, 12, 0]
    ]
    time_windows = [
        (0, 200),   # Station 0 (base)
        (0, 100),   # Station 1
        (20, 120),  # Station 2
        (40, 140)   # Station 3
    ]
    inspection_time = 10
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    if result['arrival_times']:
        # Format arrival times for readability
        formatted_times = [round(t, 2) for t in result['arrival_times']]
        print(f"Arrival Times: {formatted_times}")
    else:
        print("Arrival Times: []")
    print(f"Total Energy: {result['total_energy']}")

    print("\n--- Example with no feasible solution ---")
    
    tight_time_windows = [
        (0, 100),   # Station 0 (base)
        (0, 50),    # Station 1 (impossible to reach in time from some paths)
        (20, 80),   # Station 2
        (40, 90)    # Station 3
    ]
    
    result_infeasible = find_optimal_route(cost_matrix, tight_time_windows, inspection_time, speed)

    print(f"Feasible: {result_infeasible['feasible']}")
    print(f"Route: {result_infeasible['route']}")
    print(f"Arrival Times: {result_infeasible['arrival_times']}")
    print(f"Total Energy: {result_infeasible['total_energy']}")


if __name__ == "__main__":
    main()