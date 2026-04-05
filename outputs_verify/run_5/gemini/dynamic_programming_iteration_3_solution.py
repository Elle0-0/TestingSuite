import time
import random
import math

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    num_subsets = 1 << n

    # dp[mask][i] = (earliest_arrival_time, min_cost_for_that_time)
    dp = [[(float('inf'), float('inf'))] * n for _ in range(num_subsets)]
    parent = [[-1] * n for _ in range(num_subsets)]

    # Base case: start at depot (station 0) at time 0 with cost 0
    dp[1][0] = (0, 0)

    for mask in range(1, num_subsets):
        for i in range(n):
            # If station i is not in the current subset, skip
            if not ((mask >> i) & 1):
                continue
            
            # The mask representing the path before visiting i
            prev_mask = mask ^ (1 << i)
            if prev_mask == 0:
                continue

            for j in range(n):
                # If station j is not in the previous subset, skip
                if not ((prev_mask >> j) & 1):
                    continue
                
                prev_arrival_time, prev_cost = dp[prev_mask][j]

                if prev_arrival_time == float('inf'):
                    continue

                # Time when service at j can start (wait if arriving early)
                service_start_time_j = max(prev_arrival_time, time_windows[j][0])
                
                # Time of departure from j after inspection
                departure_time_j = service_start_time_j + inspection_time

                travel_time_ji = cost_matrix[j][i] / speed
                new_arrival_time_i = departure_time_j + travel_time_ji
                
                # Check if arrival at i is within its time window
                if new_arrival_time_i <= time_windows[i][1]:
                    new_cost = prev_cost + cost_matrix[j][i]
                    current_arrival, current_cost = dp[mask][i]

                    # Prioritize earlier arrival. If arrival times are equal, prioritize lower cost.
                    if new_arrival_time_i < current_arrival or \
                       (new_arrival_time_i == current_arrival and new_cost < current_cost):
                        dp[mask][i] = (new_arrival_time_i, new_cost)
                        parent[mask][i] = j

    # Find the optimal full tour by checking return to depot from all possible final stations
    final_mask = num_subsets - 1
    min_total_cost = float('inf')
    best_last_station = -1

    for i in range(1, n):
        arrival_at_i, cost_to_i = dp[final_mask][i]
        
        if arrival_at_i == float('inf'):
            continue

        # Time to return to depot
        service_start_time_i = max(arrival_at_i, time_windows[i][0])
        departure_time_i = service_start_time_i + inspection_time
        return_travel_time = cost_matrix[i][0] / speed
        final_arrival_time = departure_time_i + return_travel_time

        if final_arrival_time <= time_windows[0][1]:
            total_cost = cost_to_i + cost_matrix[i][0]
            if total_cost < min_total_cost:
                min_total_cost = total_cost
                best_last_station = i

    # If no feasible tour was found
    if best_last_station == -1:
        return {'cost': float('inf'), 'route': []}

    # Reconstruct the optimal path
    route = []
    curr_mask = final_mask
    curr_station = best_last_station
    
    while curr_station != -1:
        route.append(curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station
        
    route.reverse()
    route.append(0) # Add final return to depot

    return {'cost': min_total_cost, 'route': route}

def main():
    start_time = time.time()
    
    NUM_STATIONS = 15
    MAX_COORD = 1000
    INSPECTION_TIME = 30
    SPEED = 50
    DEPOT_END_TIME = 2000

    random.seed(42)

    locations = [(random.randint(0, MAX_COORD), random.randint(0, MAX_COORD)) for _ in range(NUM_STATIONS)]
    
    cost_matrix = [[0.0] * NUM_STATIONS for _ in range(NUM_STATIONS)]
    for i in range(NUM_STATIONS):
        for j in range(NUM_STATIONS):
            cost_matrix[i][j] = math.hypot(locations[i][0] - locations[j][0], locations[i][1] - locations[j][1])

    time_windows = [(0.0, 0.0)] * NUM_STATIONS
    time_windows[0] = (0, DEPOT_END_TIME)

    for i in range(1, NUM_STATIONS):
        travel_time_from_depot = cost_matrix[0][i] / SPEED
        earliest_arrival = travel_time_from_depot + 10 
        tw_start = random.uniform(earliest_arrival, earliest_arrival + 300)
        tw_end = tw_start + random.uniform(100, 400)
        time_windows[i] = (tw_start, tw_end)

    print(f"Generated a random test case with {NUM_STATIONS} stations.")
    
    result = find_optimal_route(cost_matrix, time_windows, INSPECTION_TIME, SPEED)
    
    end_time = time.time()
    
    print("\n--- Optimal Route ---")
    if result['route']:
        print(f"Minimum Cost: {result['cost']:.2f}")
        print(f"Route: {' -> '.join(map(str, result['route']))}")
    else:
        print("No feasible route found.")
    
    print(f"\nElapsed time: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    main()