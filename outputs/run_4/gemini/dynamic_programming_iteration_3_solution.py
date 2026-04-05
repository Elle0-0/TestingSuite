import time
import random
import math

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    n = len(cost_matrix)
    # dp[mask][i] = (cost, finish_time) for a path ending at station i, visiting stations in mask
    dp = [[(float('inf'), float('inf')) for _ in range(n)] for _ in range(1 << n)]
    parent = [[-1 for _ in range(n)] for _ in range(1 << n)]

    # Initialize paths starting from the depot (station 0)
    for i in range(1, n):
        travel_time = cost_matrix[0][i] / speed
        arrival_time = travel_time
        
        wait_time = max(0, time_windows[i][0] - arrival_time)
        start_inspection_time = arrival_time + wait_time
        
        if start_inspection_time <= time_windows[i][1]:
            finish_time = start_inspection_time + inspection_time
            mask = 1 | (1 << i)
            dp[mask][i] = (cost_matrix[0][i], finish_time)
            parent[mask][i] = 0

    # Iterate through all subsets of stations (masks)
    for mask in range(1, 1 << n):
        for j in range(1, n):
            # If station j is in the current set
            if (mask >> j) & 1:
                # If there's a valid path to j with this mask
                if dp[mask][j][0] == float('inf'):
                    continue
                
                cost_to_j, time_at_j = dp[mask][j]
                
                # Try to extend the path to an unvisited station k
                for k in range(1, n):
                    if not ((mask >> k) & 1):
                        new_mask = mask | (1 << k)
                        travel_time = cost_matrix[j][k] / speed
                        arrival_at_k = time_at_j + travel_time
                        
                        wait_time = max(0, time_windows[k][0] - arrival_at_k)
                        start_inspection = arrival_at_k + wait_time
                        
                        if start_inspection <= time_windows[k][1]:
                            finish_time = start_inspection + inspection_time
                            new_cost = cost_to_j + cost_matrix[j][k]
                            
                            existing_cost, existing_finish = dp[new_mask][k]
                            # Update if new path is cheaper or equally cheap but faster
                            if new_cost < existing_cost or \
                               (new_cost == existing_cost and finish_time < existing_finish):
                                dp[new_mask][k] = (new_cost, finish_time)
                                parent[new_mask][k] = j

    # Find the best complete path returning to the depot
    final_mask = (1 << n) - 1
    min_total_cost = float('inf')
    last_station = -1

    for j in range(1, n):
        cost_to_j, time_at_j = dp[final_mask][j]
        if cost_to_j != float('inf'):
            return_travel_time = cost_matrix[j][0] / speed
            
            # Check if we can return to the depot in time
            if time_at_j + return_travel_time <= time_windows[0][1]:
                total_cost = cost_to_j + cost_matrix[j][0]
                if total_cost < min_total_cost:
                    min_total_cost = total_cost
                    last_station = j

    if last_station == -1:
        return {"cost": float('inf'), "path": []}

    # Reconstruct the path from the parent pointers
    path = []
    curr_station = last_station
    curr_mask = final_mask
    while curr_station != 0:
        path.append(curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station
    
    path.append(0)
    path.reverse()
    path.append(0)
    
    return {"cost": min_total_cost, "path": path}

def main():
    num_stations = 15
    random.seed(42)

    coords = [[random.random() * 200 for _ in range(2)] for _ in range(num_stations)]
    
    cost_matrix = [[0.0 for _ in range(num_stations)] for _ in range(num_stations)]
    for i in range(num_stations):
        for j in range(num_stations):
            p1 = coords[i]
            p2 = coords[j]
            distance = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
            cost_matrix[i][j] = distance
            
    inspection_time = 10
    speed = 1.0
    time_windows = [(0, 0)] * num_stations
    time_windows[0] = (0, 2000)

    for i in range(1, num_stations):
        dist_from_depot = cost_matrix[0][i]
        arrival_est = dist_from_depot / speed
        start_time = arrival_est + random.uniform(0, 50)
        window_duration = random.uniform(30, 80) + inspection_time
        end_time = start_time + window_duration
        time_windows[i] = (start_time, end_time)

    start_time_solve = time.time()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    end_time_solve = time.time()
    
    elapsed_time = end_time_solve - start_time_solve
    
    print(result)
    print(f"Elapsed time: {elapsed_time:.4f} seconds")

if __name__ == "__main__":
    main()