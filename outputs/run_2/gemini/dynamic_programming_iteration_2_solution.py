import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": True, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        if time_windows[0][0] <= 0 <= time_windows[0][1]:
            return {"feasible": True, "route": [0, 0], "arrival_times": [0, 0], "total_energy": 0}
        else:
            return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    all_visited_mask = (1 << n) - 1
    infinity = float('inf')

    # dp[mask][i] stores a tuple: (minimum cost, earliest finish time)
    dp = [[(infinity, infinity)] * n for _ in range(1 << n)]
    parent = [[None] * n for _ in range(1 << n)]

    # Base case: start at station 0 at time 0 with 0 cost
    dp[1][0] = (0, 0)

    for mask in range(1, 1 << n):
        for i in range(n):
            if (mask >> i) & 1:
                if dp[mask][i] == (infinity, infinity):
                    continue

                current_cost, current_finish_time = dp[mask][i]

                for j in range(n):
                    if not ((mask >> j) & 1):
                        earliest_j, latest_j = time_windows[j]
                        
                        travel_time = cost_matrix[i][j] / speed
                        arrival_time_at_j = current_finish_time + travel_time

                        if arrival_time_at_j > latest_j:
                            continue

                        start_inspection_at_j = max(arrival_time_at_j, earliest_j)
                        
                        insp_time_j = inspection_time if j != 0 else 0
                        finish_time_at_j = start_inspection_at_j + insp_time_j
                        
                        new_cost = current_cost + cost_matrix[i][j]
                        new_mask = mask | (1 << j)

                        if new_cost < dp[new_mask][j][0] or \
                           (new_cost == dp[new_mask][j][0] and finish_time_at_j < dp[new_mask][j][1]):
                            dp[new_mask][j] = (new_cost, finish_time_at_j)
                            parent[new_mask][j] = i

    min_total_energy = infinity
    last_node = -1
    
    for i in range(1, n):
        cost_to_i, finish_time_at_i = dp[all_visited_mask][i]
        if cost_to_i == infinity:
            continue

        travel_time_to_base = cost_matrix[i][0] / speed
        arrival_time_at_base = finish_time_at_i + travel_time_to_base
        
        _, latest_base = time_windows[0]
        if arrival_time_at_base > latest_base:
            continue

        total_energy = cost_to_i + cost_matrix[i][0]
        if total_energy < min_total_energy:
            min_total_energy = total_energy
            last_node = i
            
    if last_node == -1:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    route = []
    current_mask = all_visited_mask
    current_node = last_node
    
    while current_node is not None and current_node != 0:
        route.append(current_node)
        prev_node = parent[current_mask][current_node]
        current_mask ^= (1 << current_node)
        current_node = prev_node
    
    final_route = [0] + route[::-1] + [0]

    arrival_times = [0.0] * len(final_route)
    current_arrival_time = 0.0
    
    for i in range(len(final_route) - 1):
        u, v = final_route[i], final_route[i+1]
        
        earliest_u, _ = time_windows[u]
        insp_time_u = inspection_time if u != 0 else 0

        start_service_u = max(current_arrival_time, earliest_u)
        departure_from_u = start_service_u + insp_time_u
        
        travel = cost_matrix[u][v] / speed
        arrival_at_v = departure_from_u + travel
        
        arrival_times[i+1] = arrival_at_v
        current_arrival_time = arrival_at_v

    return {
        "feasible": True,
        "route": final_route,
        "arrival_times": arrival_times,
        "total_energy": min_total_energy
    }

def main():
    print("--- Example 1: Feasible Scenario ---")
    cost_matrix_1 = [
        [0, 10, 25, 25],
        [10, 0, 15, 20],
        [25, 15, 0, 10],
        [25, 20, 10, 0]
    ]
    inspection_time_1 = 5
    time_windows_1 = [
        (0, 200),
        (0, 20),
        (30, 60),
        (0, 40)
    ]
    
    result_1 = find_optimal_route(cost_matrix_1, time_windows_1, inspection_time_1)
    
    print(f"Feasible: {result_1['feasible']}")
    print(f"Route: {result_1['route']}")
    formatted_times_1 = [round(t, 2) for t in result_1['arrival_times']]
    print(f"Arrival Times: {formatted_times_1}")
    print(f"Total Energy: {result_1['total_energy']}")
    print("-" * 35)

    print("--- Example 2: Infeasible Scenario ---")
    cost_matrix_2 = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    inspection_time_2 = 5
    time_windows_2 = [
        (0, 1000),
        (10, 20),
        (40, 55),
        (60, 75)
    ]

    result_2 = find_optimal_route(cost_matrix_2, time_windows_2, inspection_time_2)
    
    print(f"Feasible: {result_2['feasible']}")
    print(f"Route: {result_2['route']}")
    print(f"Arrival Times: {result_2['arrival_times']}")
    print(f"Total Energy: {result_2['total_energy']}")
    print("-" * 35)

    print("--- Example 3: Single Station ---")
    cost_matrix_3 = [[0]]
    inspection_time_3 = 10
    time_windows_3 = [(0, 100)]
    
    result_3 = find_optimal_route(cost_matrix_3, time_windows_3, inspection_time_3)
    
    print(f"Feasible: {result_3['feasible']}")
    print(f"Route: {result_3['route']}")
    print(f"Arrival Times: {result_3['arrival_times']}")
    print(f"Total Energy: {result_3['total_energy']}")
    print("-" * 35)

if __name__ == "__main__":
    main()