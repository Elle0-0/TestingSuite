import time
import random
import math

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {'path': [], 'cost': 0, 'time': 0}
    if n == 1:
        depot_departure = max(time_windows[0][0], 0 + inspection_time)
        return {'path': [0, 0], 'cost': 0, 'time': depot_departure}

    dp = [[(float('inf'), float('inf')) for _ in range(n)] for _ in range(1 << n)]
    parent = [[-1 for _ in range(n)] for _ in range(1 << n)]

    start_time = time_windows[0][0]
    dp[1][0] = (0, start_time)

    for mask in range(1, 1 << n):
        for u in range(n):
            if not (mask & (1 << u)):
                continue

            prev_cost, departure_time_u = dp[mask][u]
            if prev_cost == float('inf'):
                continue

            for v in range(n):
                if not (mask & (1 << v)):
                    new_mask = mask | (1 << v)
                    travel_cost = cost_matrix[u][v]
                    travel_time = travel_cost / speed
                    
                    arrival_time_v = departure_time_u + travel_time
                    start_service_v = max(arrival_time_v, time_windows[v][0])

                    if start_service_v > time_windows[v][1]:
                        continue
                    
                    departure_time_v = start_service_v + inspection_time
                    new_cost = prev_cost + travel_cost

                    if new_cost < dp[new_mask][v][0] or \
                       (new_cost == dp[new_mask][v][0] and departure_time_v < dp[new_mask][v][1]):
                        dp[new_mask][v] = (new_cost, departure_time_v)
                        parent[new_mask][v] = u

    full_mask = (1 << n) - 1
    min_total_cost = float('inf')
    last_station = -1
    final_arrival_time = float('inf')

    for u in range(1, n):
        if dp[full_mask][u][0] != float('inf'):
            cost_to_u, departure_from_u = dp[full_mask][u]
            
            return_cost = cost_matrix[u][0]
            total_cost = cost_to_u + return_cost
            
            arrival_at_depot = departure_from_u + (return_cost / speed)
            
            if arrival_at_depot <= time_windows[0][1]:
                if total_cost < min_total_cost:
                    min_total_cost = total_cost
                    last_station = u
                    final_arrival_time = arrival_at_depot

    if last_station == -1:
        return {'path': [], 'cost': float('inf'), 'time': float('inf')}

    path = []
    curr_station = last_station
    curr_mask = full_mask

    while curr_station != 0:
        path.append(curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station
    
    path.append(0)
    path.reverse()
    path.append(0)

    return {
        'path': path,
        'cost': min_total_cost,
        'time': final_arrival_time
    }

def main():
    start_time = time.time()
    
    num_stations = 15
    total_nodes = num_stations + 1 
    random.seed(42)

    locations = []
    for _ in range(total_nodes):
        locations.append((random.uniform(0, 100), random.uniform(0, 100)))

    cost_matrix = [[0.0] * total_nodes for _ in range(total_nodes)]
    for i in range(total_nodes):
        for j in range(i, total_nodes):
            dist = math.sqrt((locations[i][0] - locations[j][0])**2 + (locations[i][1] - locations[j][1])**2)
            cost_matrix[i][j] = dist
            cost_matrix[j][i] = dist
            
    inspection_time = 10
    speed = 1

    time_windows = [[0, 0] for _ in range(total_nodes)]
    depot_due_time = 0
    for i in range(1, total_nodes):
        travel_to_i = cost_matrix[0][i] / speed
        ready = travel_to_i + random.uniform(5, 30)
        due = ready + random.uniform(20, 50)
        time_windows[i] = [ready, due]
        
        # Ensure depot due time is sufficient for a round trip
        potential_round_trip_time = ready + inspection_time + (cost_matrix[i][0] / speed)
        if potential_round_trip_time > depot_due_time:
            depot_due_time = potential_round_trip_time

    time_windows[0] = [0, depot_due_time * 2.5] # Give a generous window for the depot

    print(f"Generated a random test case with {num_stations} stations.")
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    end_time = time.time()
    elapsed_time = end_time - start_time

    print("\n--- Optimal Route Found ---")
    if result['cost'] != float('inf'):
        print(f"Path: {result['path']}")
        print(f"Total Cost (Distance): {result['cost']:.2f}")
        print(f"Total Time: {result['time']:.2f}")
    else:
        print("No feasible solution found.")
    
    print(f"\nElapsed time: {elapsed_time:.4f} seconds")

main()