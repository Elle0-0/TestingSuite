import time
import random

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    num_stations = len(cost_matrix)

    dp = [[float('inf')] * num_stations for _ in range(1 << num_stations)]
    parent = [[-1] * num_stations for _ in range(1 << num_stations)]

    start_service_depot = time_windows[0][0]
    dp[1][0] = start_service_depot + inspection_time

    for mask in range(1, 1 << num_stations):
        for i in range(num_stations):
            if (mask >> i) & 1:
                if dp[mask][i] == float('inf'):
                    continue

                departure_time_from_i = dp[mask][i]

                for j in range(num_stations):
                    if not ((mask >> j) & 1):
                        travel_time = cost_matrix[i][j] / speed
                        arrival_time_at_j = departure_time_from_i + travel_time
                        
                        ready_time_j, due_time_j = time_windows[j]

                        if arrival_time_at_j > due_time_j:
                            continue

                        start_service_time_at_j = max(arrival_time_at_j, ready_time_j)
                        
                        departure_time_from_j = start_service_time_at_j + inspection_time
                        
                        new_mask = mask | (1 << j)

                        if departure_time_from_j < dp[new_mask][j]:
                            dp[new_mask][j] = departure_time_from_j
                            parent[new_mask][j] = i

    min_cost = float('inf')
    best_last_station = -1
    best_mask = -1

    depot_ready_time, depot_due_time = time_windows[0]

    for mask in range(1, 1 << num_stations):
        for i in range(1, num_stations):
            if (mask >> i) & 1:
                if dp[mask][i] != float('inf'):
                    return_travel_time = cost_matrix[i][0] / speed
                    arrival_at_depot = dp[mask][i] + return_travel_time

                    if arrival_at_depot <= depot_due_time:
                        cost = arrival_at_depot - depot_ready_time
                        if cost < min_cost:
                            min_cost = cost
                            best_last_station = i
                            best_mask = mask
    
    if best_last_station == -1:
        depot_only_cost = inspection_time
        if depot_only_cost < min_cost:
             return {'cost': depot_only_cost, 'path': [0, 0], 'visited_stations': []}
        return {'cost': float('inf'), 'path': [], 'visited_stations': []}

    path = []
    curr_station = best_last_station
    curr_mask = best_mask

    while curr_station != -1:
        path.append(curr_station)
        if curr_station == 0:
            break
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station
    
    path.reverse()
    
    path.append(0)

    visited_stations = sorted(list(set([s for s in path if s != 0])))

    return {'cost': min_cost, 'path': path, 'visited_stations': visited_stations}


def main():
    start_time = time.time()
    
    NUM_STATIONS = 15
    INSPECTION_TIME = 10
    MAX_COORD = 100
    MAX_DURATION = 200
    RANDOM_SEED = 42

    random.seed(RANDOM_SEED)

    positions = {i: (random.randint(0, MAX_COORD), random.randint(0, MAX_COORD)) for i in range(NUM_STATIONS)}

    cost_matrix = [[0.0] * NUM_STATIONS for _ in range(NUM_STATIONS)]
    for i in range(NUM_STATIONS):
        for j in range(i, NUM_STATIONS):
            dist = ((positions[i][0] - positions[j][0]) ** 2 + (positions[i][1] - positions[j][1]) ** 2) ** 0.5
            cost_matrix[i][j] = cost_matrix[j][i] = dist

    time_windows = [(0, 0)] * NUM_STATIONS
    depot_end_time = sum(max(row) for row in cost_matrix) * 2
    time_windows[0] = (0, depot_end_time)

    for i in range(1, NUM_STATIONS):
        ready_time = random.randint(0, int(depot_end_time / 2))
        due_time = ready_time + random.randint(MAX_DURATION, MAX_DURATION * 2)
        time_windows[i] = (ready_time, due_time)
    
    result = find_optimal_route(cost_matrix, time_windows, INSPECTION_TIME)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    if result['cost'] != float('inf'):
        print(f"Optimal Cost: {result['cost']:.2f}")
        print(f"Optimal Path: {result['path']}")
        print(f"Visited Stations: {result['visited_stations']}")
    else:
        print("No feasible route found.")

    print(f"Elapsed Time: {elapsed_time:.4f} seconds")


if __name__ == '__main__':
    main()