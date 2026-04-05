import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    infinity = float('inf')

    if n == 0:
        return {"feasible": True, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        # Assuming arrival time at the start and end is 0
        return {"feasible": True, "route": [0, 0], "arrival_times": [0, 0], "total_energy": 0}

    # dp[mask][i] = (min_energy, departure_time) to reach station i, having visited stations in mask
    dp = [[(infinity, infinity)] * n for _ in range(1 << n)]
    
    # parent[mask][i] stores the predecessor of i in the optimal path for state (mask, i)
    parent = [[-1] * n for _ in range(1 << n)]

    # Base case: from station 0 to station j
    for j in range(1, n):
        travel_energy = cost_matrix[0][j]
        travel_time = travel_energy / speed
        arrival_time_at_j = travel_time

        earliest_j, latest_j = time_windows[j]

        if arrival_time_at_j <= latest_j:
            service_start_time = max(arrival_time_at_j, earliest_j)
            departure_time = service_start_time + inspection_time
            
            mask = 1 | (1 << j)
            dp[mask][j] = (travel_energy, departure_time)
            parent[mask][j] = 0

    # Fill DP table
    for mask in range(1, 1 << n):
        for i in range(1, n):
            if (mask >> i) & 1:
                current_energy, current_departure_time = dp[mask][i]
                if current_energy == infinity:
                    continue

                for j in range(1, n):
                    if not ((mask >> j) & 1):
                        travel_energy = cost_matrix[i][j]
                        travel_time = travel_energy / speed
                        
                        arrival_time_at_j = current_departure_time + travel_time
                        earliest_j, latest_j = time_windows[j]

                        if arrival_time_at_j <= latest_j:
                            new_energy = current_energy + travel_energy
                            next_mask = mask | (1 << j)
                            
                            if new_energy < dp[next_mask][j][0]:
                                service_start_time = max(arrival_time_at_j, earliest_j)
                                departure_time = service_start_time + inspection_time
                                dp[next_mask][j] = (new_energy, departure_time)
                                parent[next_mask][j] = i

    # Final step: return to base (station 0)
    final_mask = (1 << n) - 1
    min_total_energy = infinity
    last_station = -1

    for i in range(1, n):
        path_energy, departure_time = dp[final_mask][i]
        if path_energy != infinity:
            travel_energy_to_base = cost_matrix[i][0]
            travel_time_to_base = travel_energy_to_base / speed
            
            arrival_time_at_base = departure_time + travel_time_to_base
            _earliest_base, latest_base = time_windows[0]
            
            if arrival_time_at_base <= latest_base:
                total_energy = path_energy + travel_energy_to_base
                if total_energy < min_total_energy:
                    min_total_energy = total_energy
                    last_station = i
    
    if last_station == -1:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": -1,
        }

    # Reconstruct path
    route = []
    current_mask = final_mask
    current_station = last_station
    while current_station != 0:
        route.insert(0, current_station)
        prev_station = parent[current_mask][current_station]
        current_mask ^= (1 << current_station)
        current_station = prev_station
    
    route.insert(0, 0)
    route.append(0)

    # Calculate arrival times for the final route
    arrival_times = [0.0] * len(route)
    current_time = 0.0

    for i in range(len(route) - 1):
        u = route[i]
        v = route[i+1]
        
        arrival_times[i] = current_time
        
        earliest_u, _ = time_windows[u]
        
        service_start_time = max(current_time, earliest_u)
        
        current_inspection_time = inspection_time if u != 0 else 0
        
        departure_time = service_start_time + current_inspection_time
        
        travel_time_uv = cost_matrix[u][v] / speed
        current_time = departure_time + travel_time_uv
    
    arrival_times[-1] = current_time

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": min_total_energy,
    }

def main():
    cost_matrix = [
        [0, 10, 20, 30, 25],
        [10, 0, 15, 35, 20],
        [20, 15, 0, 5, 10],
        [30, 35, 5, 0, 15],
        [25, 20, 10, 15, 0]
    ]

    inf_time = float('inf')
    time_windows = [
        (0, inf_time),
        (0, 50),
        (20, 70),
        (40, 90),
        (0, 60)
    ]

    inspection_time = 5
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    print("Feasible:", result["feasible"])
    if result["feasible"]:
        print("Route:", result["route"])
        formatted_times = [round(t, 2) for t in result["arrival_times"]]
        print("Arrival Times:", formatted_times)
        print("Total Energy:", result["total_energy"])

    print("\n--- Infeasible Example ---")
    infeasible_time_windows = [
        (0, inf_time),
        (0, 10),
        (20, 70),
        (40, 90),
        (0, 60)
    ]
    infeasible_result = find_optimal_route(cost_matrix, infeasible_time_windows, inspection_time, speed)
    print("Feasible:", infeasible_result["feasible"])
    if not infeasible_result["feasible"]:
        print("No feasible route found.")

if __name__ == "__main__":
    main()