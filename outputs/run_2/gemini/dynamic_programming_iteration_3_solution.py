import time
import random
import math

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {'path': [], 'cost': 0, 'time': 0}

    service_times = [inspection_time] * n
    service_times[0] = 0

    dp = [[(math.inf, math.inf)] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]

    dp[1][0] = (0, time_windows[0][0])

    for mask in range(1, 1 << n):
        if not (mask & 1):
            continue

        for j in range(n):
            if not (mask & (1 << j)):
                continue

            prev_mask = mask ^ (1 << j)
            if prev_mask == 0:
                continue

            for i in range(n):
                if not (prev_mask & (1 << i)):
                    continue

                prev_cost, prev_start_service_time_at_i = dp[prev_mask][i]

                if prev_cost == math.inf:
                    continue

                departure_time_from_i = prev_start_service_time_at_i + service_times[i]
                travel_time_ij = cost_matrix[i][j] / speed
                arrival_time_at_j = departure_time_from_i + travel_time_ij

                if arrival_time_at_j > time_windows[j][1]:
                    continue

                start_service_time_at_j = max(arrival_time_at_j, time_windows[j][0])
                
                new_cost_to_j = prev_cost + cost_matrix[i][j]

                if (new_cost_to_j, start_service_time_at_j) < dp[mask][j]:
                    dp[mask][j] = (new_cost_to_j, start_service_time_at_j)
                    parent[mask][j] = i

    min_total_cost = math.inf
    final_arrival_time = math.inf
    best_mask = -1
    last_station_in_path = -1

    if time_windows[0][0] <= 0 <= time_windows[0][1]:
        min_total_cost = 0.0
        final_arrival_time = 0.0
        best_mask = 1
        last_station_in_path = 0

    for mask in range(1, 1 << n):
        if not (mask & 1):
            continue
        for i in range(n):
            if not (mask & (1 << i)):
                continue
            
            cost, start_service_time = dp[mask][i]
            if cost == math.inf:
                continue

            travel_time_to_depot = cost_matrix[i][0] / speed
            arrival_at_depot = start_service_time + service_times[i] + travel_time_to_depot
            
            if arrival_at_depot > time_windows[0][1]:
                continue

            total_cost = cost + cost_matrix[i][0]
            
            if total_cost < min_total_cost:
                min_total_cost = total_cost
                final_arrival_time = arrival_at_depot
                best_mask = mask
                last_station_in_path = i
            elif total_cost == min_total_cost and arrival_at_depot < final_arrival_time:
                final_arrival_time = arrival_at_depot
                best_mask = mask
                last_station_in_path = i

    if best_mask == -1:
        return {'path': [], 'cost': 0, 'time': 0}

    path = []
    current_mask = best_mask
    current_station = last_station_in_path
    
    while current_station != -1:
        path.append(current_station)
        prev_mask = current_mask ^ (1 << current_station)
        prev_station = parent[current_mask][current_station]
        current_mask = prev_mask
        current_station = prev_station
    
    path.reverse()
    
    return {'path': path, 'cost': min_total_cost, 'time': final_arrival_time}

def main():
    start_time = time.time()
    
    num_stations = 15
    random.seed(42)

    coords = [(random.randint(0, 100), random.randint(0, 100)) for _ in range(num_stations)]
    
    cost_matrix = [[0.0] * num_stations for _ in range(num_stations)]
    for i in range(num_stations):
        for j in range(num_stations):
            dist = math.sqrt((coords[i][0] - coords[j][0])**2 + (coords[i][1] - coords[j][1])**2)
            cost_matrix[i][j] = dist

    time_windows = []
    time_windows.append((0, 1000)) 
    for i in range(1, num_stations):
        start = random.randint(50, 400)
        end = start + random.randint(100, 300)
        time_windows.append((start, end))

    inspection_time = 10
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Result: {result}")
    print(f"Elapsed time: {elapsed_time:.4f} seconds")

if __name__ == '__main__':
    main()