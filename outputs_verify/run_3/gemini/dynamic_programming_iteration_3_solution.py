import time
import random
import sys

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {'cost': 0, 'path': []}
    if n == 1:
        return {'cost': 0, 'path': [0]}

    all_visited_mask = (1 << n) - 1
    
    dp = [[(float('inf'), float('inf')) for _ in range(n)] for _ in range(1 << n)]
    path_pred = [[-1 for _ in range(n)] for _ in range(1 << n)]

    # dp[mask][i] = (min_cost, earliest_finish_time) to visit stations in mask, ending at i
    
    # Base case: Start at the depot (station 0)
    # The "path" starts at time 0, but we must respect the depot's opening time.
    start_time = time_windows[0][0]
    dp[1][0] = (0, start_time)

    for mask in range(1, 1 << n):
        for u in range(n):
            if not (mask & (1 << u)):
                continue

            cost_u, time_u = dp[mask][u]
            if cost_u == float('inf'):
                continue

            for v in range(n):
                if not (mask & (1 << v)):
                    # Calculate time and cost to travel from u to v
                    travel_dist = cost_matrix[u][v]
                    if travel_dist == -1: continue # No path

                    travel_time = travel_dist / speed
                    
                    arrival_time_v = time_u + travel_time
                    
                    # Wait if arriving early
                    start_time_v = max(arrival_time_v, time_windows[v][0])
                    
                    finish_time_v = start_time_v + inspection_time

                    # Check time window constraint at v
                    if finish_time_v <= time_windows[v][1]:
                        new_mask = mask | (1 << v)
                        new_cost = cost_u + travel_dist
                        
                        current_cost_v, current_time_v = dp[new_mask][v]
                        
                        if new_cost < current_cost_v or \
                           (new_cost == current_cost_v and finish_time_v < current_time_v):
                            dp[new_mask][v] = (new_cost, finish_time_v)
                            path_pred[new_mask][v] = u

    # Find the optimal final path that returns to the depot
    min_total_cost = float('inf')
    last_station = -1

    for u in range(1, n):
        cost_u, time_u = dp[all_visited_mask][u]
        if cost_u == float('inf'):
            continue

        return_dist = cost_matrix[u][0]
        if return_dist == -1: continue

        return_time = return_dist / speed
        arrival_at_depot = time_u + return_time

        if arrival_at_depot <= time_windows[0][1]:
            total_cost = cost_u + return_dist
            if total_cost < min_total_cost:
                min_total_cost = total_cost
                last_station = u

    if last_station == -1:
        return {'cost': float('inf'), 'path': []}

    # Reconstruct path
    optimal_path = []
    current_mask = all_visited_mask
    current_station = last_station

    while current_station != 0:
        optimal_path.append(current_station)
        predecessor = path_pred[current_mask][current_station]
        current_mask ^= (1 << current_station)
        current_station = predecessor
    
    optimal_path.append(0)
    optimal_path.reverse()
    
    return {'cost': min_total_cost, 'path': optimal_path}

def main():
    num_stations = 15
    random.seed(42)
    
    max_coord = 500
    coords = [(random.randint(0, max_coord), random.randint(0, max_coord)) for _ in range(num_stations)]
    
    cost_matrix = [[0.0] * num_stations for _ in range(num_stations)]
    for i in range(num_stations):
        for j in range(i, num_stations):
            dist = ((coords[i][0] - coords[j][0])**2 + (coords[i][1] - coords[j][1])**2)**0.5
            cost_matrix[i][j] = cost_matrix[j][i] = dist

    inspection_time = 10
    speed = 1.0
    
    time_windows = [(0, 0)] * num_stations
    # Depot (station 0) has a wide window
    time_windows[0] = (0, 20000)
    
    # Other stations have windows based on distance from depot
    for i in range(1, num_stations):
        dist_from_depot = cost_matrix[0][i] / speed
        earliest_arrival = dist_from_depot
        
        # Add some slack
        window_start = earliest_arrival + random.uniform(0, 150)
        window_end = window_start + random.uniform(100, 300)
        time_windows[i] = (window_start, window_end)

    print(f"Solving for {num_stations} stations...")
    start_time = time.perf_counter()
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    end_time = time.perf_counter()
    elapsed_time = end_time - start_time
    
    print("\n--- Results ---")
    if result['cost'] != float('inf'):
        print(f"Optimal cost: {result['cost']:.2f}")
        path_str = " -> ".join(map(str, result['path']))
        print(f"Optimal path: {path_str} -> 0")
    else:
        print("No feasible solution found.")
    
    print(f"\nElapsed time: {elapsed_time:.4f} seconds")

if __name__ == "__main__":
    main()