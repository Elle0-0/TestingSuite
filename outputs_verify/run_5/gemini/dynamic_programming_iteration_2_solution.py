import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": -1}
    if n == 1:
        if 0 >= time_windows[0][0] and 0 <= time_windows[0][1]:
            return {"feasible": True, "route": [0, 0], "arrival_times": [0.0, 0.0], "total_energy": 0}
        else:
            return {"feasible": False, "route": [], "arrival_times": [], "total_energy": -1}

    dp = [[(math.inf, math.inf)] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]

    dp[1][0] = (0, 0)

    for mask in range(1, 1 << n):
        for i in range(n):
            if not ((mask >> i) & 1):
                continue
            
            prev_mask = mask ^ (1 << i)
            if prev_mask == 0:
                continue

            for j in range(n):
                if (prev_mask >> j) & 1:
                    prev_energy, prev_arrival_time = dp[prev_mask][j]

                    if prev_energy == math.inf:
                        continue

                    departure_time_from_j = max(prev_arrival_time, time_windows[j][0])
                    if j != 0:
                        departure_time_from_j += inspection_time

                    travel_time = cost_matrix[j][i] / speed
                    new_arrival_time = departure_time_from_j + travel_time

                    if new_arrival_time <= time_windows[i][1]:
                        actual_arrival_time = max(new_arrival_time, time_windows[i][0])
                        new_energy = prev_energy + cost_matrix[j][i]
                        
                        current_energy, current_arrival = dp[mask][i]
                        if new_energy < current_energy or \
                           (new_energy == current_energy and actual_arrival_time < current_arrival):
                            dp[mask][i] = (new_energy, actual_arrival_time)
                            parent[mask][i] = j

    final_mask = (1 << n) - 1
    min_total_energy = math.inf
    last_station = -1

    for j in range(1, n):
        energy_at_j, arrival_at_j = dp[final_mask][j]
        if energy_at_j == math.inf:
            continue

        departure_from_j = max(arrival_at_j, time_windows[j][0]) + inspection_time
        travel_to_0 = cost_matrix[j][0] / speed
        arrival_at_0 = departure_from_j + travel_to_0
        
        if arrival_at_0 <= time_windows[0][1]:
            total_energy = energy_at_j + cost_matrix[j][0]
            if total_energy < min_total_energy:
                min_total_energy = total_energy
                last_station = j

    if last_station == -1:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": -1}

    route = []
    curr_mask = final_mask
    curr_station = last_station
    while curr_station != 0:
        route.append(curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station
    
    route.append(0)
    route.reverse()
    route.append(0)

    final_arrival_times = [0.0]
    time = 0.0
    for i in range(len(route) - 1):
        u, v = route[i], route[i+1]
        
        departure_time = max(time, time_windows[u][0])
        if u != 0:
            departure_time += inspection_time
            
        time = departure_time + (cost_matrix[u][v] / speed)
        final_arrival_times.append(time)

    return {
        "feasible": True,
        "route": route,
        "arrival_times": final_arrival_times,
        "total_energy": int(min_total_energy)
    }

def main():
    cost_matrix = [
        [0, 10, 80, 20],
        [10, 0, 25, 30],
        [80, 25, 0, 35],
        [20, 30, 35, 0]
    ]
    
    time_windows = [
        (0, 1000), 
        (0, 20),   
        (30, 80),  
        (0, 100),   
    ]
    
    inspection_time = 5
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    print(f"feasible = {result['feasible']}")
    if result['feasible']:
        print(f"route = {result['route']}")
        arrival_times_str = [f"{t:.2f}" for t in result['arrival_times']]
        print(f"arrival_times = {arrival_times_str}")
        print(f"total_energy = {result['total_energy']}")

if __name__ == "__main__":
    main()