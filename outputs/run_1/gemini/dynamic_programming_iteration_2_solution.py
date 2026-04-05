import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    dp = [[(math.inf, math.inf)] * n for _ in range(1 << n)]
    path = [[-1] * n for _ in range(1 << n)]

    start_time = time_windows[0][0]
    finish_time = start_time + inspection_time

    if finish_time > time_windows[0][1]:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": -1,
        }
    
    dp[1][0] = (0, finish_time)

    for mask in range(1, 1 << n):
        for i in range(n):
            if not ((mask >> i) & 1):
                continue
            
            if dp[mask][i][0] == math.inf:
                continue

            current_cost, current_finish_time = dp[mask][i]

            for j in range(n):
                if not ((mask >> j) & 1):
                    travel_time = cost_matrix[i][j] / speed
                    new_cost = current_cost + cost_matrix[i][j]
                    arrival_at_j = current_finish_time + travel_time

                    earliest_j, latest_j = time_windows[j]

                    if arrival_at_j > latest_j:
                        continue

                    ready_time_at_j = max(arrival_at_j, earliest_j)
                    finish_time_at_j = ready_time_at_j + inspection_time
                    
                    if finish_time_at_j > latest_j:
                        continue
                    
                    new_mask = mask | (1 << j)

                    if (new_cost, finish_time_at_j) < dp[new_mask][j]:
                        dp[new_mask][j] = (new_cost, finish_time_at_j)
                        path[new_mask][j] = i

    final_mask = (1 << n) - 1
    min_total_energy = math.inf
    last_station = -1

    for i in range(1, n):
        if dp[final_mask][i][0] != math.inf:
            current_cost, current_finish_time = dp[final_mask][i]
            travel_time_to_0 = cost_matrix[i][0] / speed
            arrival_at_0 = current_finish_time + travel_time_to_0

            if arrival_at_0 <= time_windows[0][1]:
                total_energy = current_cost + cost_matrix[i][0]
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

    optimal_route = []
    current_mask = final_mask
    current_node = last_station
    while current_node != -1:
        optimal_route.append(current_node)
        prev_node = path[current_mask][current_node]
        current_mask ^= (1 << current_node)
        current_node = prev_node

    optimal_route.reverse()
    optimal_route = [0] + optimal_route + [0]

    arrival_times = [0.0] * len(optimal_route)
    arrival_times[0] = time_windows[0][0]
    
    departure_time = max(arrival_times[0], time_windows[0][0]) + inspection_time

    for i in range(len(optimal_route) - 1):
        from_node = optimal_route[i]
        to_node = optimal_route[i+1]
        
        travel_time = cost_matrix[from_node][to_node] / speed
        arrival_at_next = departure_time + travel_time
        arrival_times[i+1] = arrival_at_next
        
        if i < len(optimal_route) - 2:
            earliest, _ = time_windows[to_node]
            ready_time = max(arrival_at_next, earliest)
            departure_time = ready_time + inspection_time

    return {
        "feasible": True,
        "route": optimal_route,
        "arrival_times": arrival_times,
        "total_energy": min_total_energy,
    }


def main():
    cost_matrix = [
        [0, 20, 42, 35, 50],
        [20, 0, 30, 34, 45],
        [42, 30, 0, 12, 38],
        [35, 34, 12, 0, 25],
        [50, 45, 38, 25, 0],
    ]
    time_windows = [
        (0, 500),    # Depot 0
        (0, 100),    # Station 1
        (50, 150),   # Station 2
        (80, 200),   # Station 3
        (20, 120),   # Station 4
    ]
    inspection_time = 10
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival Times: {[round(t, 2) for t in result['arrival_times']]}")
    print(f"Total Energy: {result['total_energy']}")

    print("\n--- Infeasible Example ---")
    
    infeasible_time_windows = [
        (0, 100),
        (10, 20),
        (30, 40),
        (50, 60),
        (70, 80),
    ]

    result_infeasible = find_optimal_route(cost_matrix, infeasible_time_windows, inspection_time, speed)

    print(f"Feasible: {result_infeasible['feasible']}")
    print(f"Route: {result_infeasible['route']}")
    print(f"Arrival Times: {result_infeasible['arrival_times']}")
    print(f"Total Energy: {result_infeasible['total_energy']}")


if __name__ == "__main__":
    main()