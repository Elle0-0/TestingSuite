import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": True, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        start_time = time_windows[0][0]
        end_time = time_windows[0][1]
        if start_time <= 0 <= end_time:
            return {"feasible": True, "route": [0, 0], "arrival_times": [0.0, 0.0], "total_energy": 0}
        else:
            return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    dp = [[(math.inf, math.inf) for _ in range(n)] for _ in range(1 << n)]
    parent = [[-1 for _ in range(n)] for _ in range(1 << n)]

    start_node_arrival_time = 0.0
    dp[1][0] = (0, start_node_arrival_time)

    for mask in range(1, 1 << n):
        for u in range(n):
            if not ((mask >> u) & 1):
                continue
            
            if dp[mask][u][0] == math.inf:
                continue

            current_cost, current_arrival_time = dp[mask][u]
            earliest_u, _ = time_windows[u]
            
            service_start_time = max(current_arrival_time, earliest_u)
            
            current_inspection_time = inspection_time if u != 0 else 0
            departure_time = service_start_time + current_inspection_time

            for v in range(n):
                if not ((mask >> v) & 1):
                    travel_time = cost_matrix[u][v] / speed
                    new_arrival_time = departure_time + travel_time
                    
                    earliest_v, latest_v = time_windows[v]

                    if new_arrival_time <= latest_v:
                        new_mask = mask | (1 << v)
                        new_cost = current_cost + cost_matrix[u][v]
                        
                        if (new_cost, new_arrival_time) < dp[new_mask][v]:
                            dp[new_mask][v] = (new_cost, new_arrival_time)
                            parent[new_mask][v] = u

    final_mask = (1 << n) - 1
    min_total_energy = math.inf
    last_station = -1

    for u in range(1, n):
        if dp[final_mask][u][0] != math.inf:
            cost_to_u, arrival_time_at_u = dp[final_mask][u]
            earliest_u, _ = time_windows[u]

            service_start_time_u = max(arrival_time_at_u, earliest_u)
            departure_time_u = service_start_time_u + inspection_time
            
            travel_time_to_base = cost_matrix[u][0] / speed
            final_arrival_time = departure_time_u + travel_time_to_base
            
            _, latest_at_base = time_windows[0]

            if final_arrival_time <= latest_at_base:
                total_energy = cost_to_u + cost_matrix[u][0]
                if total_energy < min_total_energy:
                    min_total_energy = total_energy
                    last_station = u

    if last_station == -1:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    route = []
    curr_mask = final_mask
    curr_node = last_station
    while curr_node != 0:
        route.append(curr_node)
        prev_node = parent[curr_mask][curr_node]
        curr_mask ^= (1 << curr_node)
        curr_node = prev_node
    
    route.append(0)
    route.reverse()
    route.append(0)

    arrival_times = []
    current_time = 0.0
    
    for i in range(len(route) - 1):
        u = route[i]
        v = route[i+1]
        
        arrival_times.append(current_time)
        
        earliest_u, _ = time_windows[u]
        service_start_time = max(current_time, earliest_u)
        
        current_inspection_time = inspection_time if u != 0 else 0
        departure_time = service_start_time + current_inspection_time
        
        travel_time = cost_matrix[u][v] / speed
        current_time = departure_time + travel_time

    arrival_times.append(current_time)

    return {
        "feasible": True,
        "route": route,
        "arrival_times": [float(t) for t in arrival_times],
        "total_energy": int(min_total_energy)
    }

def main():
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]

    time_windows = [
        (0, 1000), 
        (10, 50),
        (40, 80),
        (50, 100)
    ]
    
    inspection_time = 5
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print("feasible:", result["feasible"])
    print("route:", result["route"])
    print("arrival_times:", result["arrival_times"])
    print("total_energy:", result["total_energy"])

if __name__ == "__main__":
    main()