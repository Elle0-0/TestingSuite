import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        return {"feasible": True, "route": [0, 0], "arrival_times": [time_windows[0][0], time_windows[0][0]], "total_energy": 0}

    dp = [[(math.inf, math.inf) for _ in range(n)] for _ in range(1 << n)]
    parent = [[-1 for _ in range(n)] for _ in range(1 << n)]

    start_node = 0
    start_mask = 1 << start_node
    dp[start_mask][start_node] = (0, time_windows[start_node][0])

    for mask in range(1, 1 << n):
        for u in range(n):
            if not (mask & (1 << u)):
                continue

            prev_mask = mask ^ (1 << u)
            if prev_mask == 0:
                continue

            for v in range(n):
                if not (prev_mask & (1 << v)):
                    continue

                prev_cost, prev_arrival_time = dp[prev_mask][v]
                if prev_cost == math.inf:
                    continue

                service_time_at_v = inspection_time if v != start_node else 0
                departure_time_from_v = max(prev_arrival_time, time_windows[v][0]) + service_time_at_v

                travel_time = cost_matrix[v][u] / speed
                arrival_time_at_u = departure_time_from_v + travel_time

                if arrival_time_at_u <= time_windows[u][1]:
                    new_cost = prev_cost + cost_matrix[v][u]
                    
                    current_cost, current_arrival_time = dp[mask][u]
                    if new_cost < current_cost or (new_cost == current_cost and arrival_time_at_u < current_arrival_time):
                        dp[mask][u] = (new_cost, arrival_time_at_u)
                        parent[mask][u] = v

    final_mask = (1 << n) - 1
    min_total_energy = math.inf
    last_node_in_route = -1

    for i in range(n):
        if i == start_node:
            continue

        cost_so_far, arrival_at_i = dp[final_mask][i]
        if cost_so_far == math.inf:
            continue
        
        service_time_at_i = inspection_time if i != start_node else 0
        departure_from_i = max(arrival_at_i, time_windows[i][0]) + service_time_at_i
        
        travel_time_to_base = cost_matrix[i][start_node] / speed
        arrival_at_base = departure_from_i + travel_time_to_base

        if arrival_at_base <= time_windows[start_node][1]:
            total_energy = cost_so_far + cost_matrix[i][start_node]
            if total_energy < min_total_energy:
                min_total_energy = total_energy
                last_node_in_route = i
    
    if last_node_in_route == -1:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    route = []
    curr_node = last_node_in_route
    curr_mask = final_mask
    while curr_node != -1:
        route.append(curr_node)
        prev_node = parent[curr_mask][curr_node]
        curr_mask ^= (1 << curr_node)
        curr_node = prev_node
    
    route = route[::-1]
    route.insert(0, start_node)
    route.append(start_node)

    arrival_times = [0.0] * len(route)
    current_time = float(time_windows[start_node][0])
    arrival_times[0] = current_time

    for i in range(len(route) - 1):
        u, v = route[i], route[i+1]
        
        service_time_at_u = inspection_time if u != start_node else 0
        departure_time = max(current_time, time_windows[u][0]) + service_time_at_u
        
        travel_time = cost_matrix[u][v] / speed
        current_time = departure_time + travel_time
        arrival_times[i+1] = current_time

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": min_total_energy
    }

def main():
    cost_matrix = [
        [0, 29, 20, 21, 15],
        [29, 0, 15, 17, 28],
        [20, 15, 0, 28, 23],
        [21, 17, 28, 0, 10],
        [15, 28, 23, 10, 0]
    ]
    time_windows = [
        (0, 200),
        (10, 80),
        (30, 100),
        (50, 130),
        (0, 150)
    ]
    inspection_time = 10
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("Example 1: Feasible case")
    print(f"Feasible: {result['feasible']}")
    print(f"Route: {result['route']}")
    print(f"Arrival Times: {[round(t, 2) for t in result['arrival_times']]}")
    print(f"Total Energy: {result['total_energy']}")
    print("-" * 20)

    time_windows_infeasible = [
        (0, 200),
        (10, 25), # Too tight
        (30, 100),
        (50, 130),
        (0, 150)
    ]
    
    result_infeasible = find_optimal_route(cost_matrix, time_windows_infeasible, inspection_time, speed)

    print("Example 2: Infeasible case")
    print(f"Feasible: {result_infeasible['feasible']}")
    print(f"Route: {result_infeasible['route']}")
    print(f"Arrival Times: {result_infeasible['arrival_times']}")
    print(f"Total Energy: {result_infeasible['total_energy']}")

if __name__ == "__main__":
    main()