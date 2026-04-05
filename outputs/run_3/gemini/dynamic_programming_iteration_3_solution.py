import time
import random
import math

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {"path": [], "cost": 0}
    if n == 1:
        # Assuming the tour is just staying at the depot
        return {"path": [0], "cost": 0}

    # memo[mask][u] = (min_cost, earliest_arrival_time)
    memo = [[(float('inf'), float('inf')) for _ in range(n)] for _ in range(1 << n)]
    
    # parent[mask][u] = predecessor_of_u in the path to this state
    parent = [[None for _ in range(n)] for _ in range(1 << n)]

    # Base case: start at the depot (station 0) at its earliest possible time
    start_time = time_windows[0][0]
    memo[1][0] = (0, start_time)

    # Iterate through all subsets of stations
    for mask in range(1, 1 << n):
        for u in range(n):
            # Consider only states where station u is the last in the path
            if (mask >> u) & 1:
                # If this state is unreachable, skip
                if memo[mask][u][0] == float('inf'):
                    continue

                current_cost, current_time = memo[mask][u]
                
                # Time we can depart from station u after inspection
                departure_time = current_time + inspection_time

                # Try to extend the path to an unvisited station v
                for v in range(n):
                    if not ((mask >> v) & 1):
                        travel_dist = cost_matrix[u][v]
                        travel_time = travel_dist / speed
                        arrival_time_at_v = departure_time + travel_time
                        
                        # Wait if we arrive early
                        start_service_at_v = max(arrival_time_at_v, time_windows[v][0])

                        # Check if the time window is missed
                        if start_service_at_v > time_windows[v][1]:
                            continue

                        new_mask = mask | (1 << v)
                        new_cost = current_cost + travel_dist
                        new_time = start_service_at_v
                        
                        # If we found a cheaper path to this new state, update it
                        if new_cost < memo[new_mask][v][0]:
                            memo[new_mask][v] = (new_cost, new_time)
                            parent[new_mask][v] = u

    # After filling the DP table, find the complete tour with the minimum cost
    final_mask = (1 << n) - 1
    min_total_cost = float('inf')
    last_station = -1

    # Find the best last station before returning to the depot
    for u in range(1, n):
        path_cost, path_time = memo[final_mask][u]
        if path_cost == float('inf'):
            continue

        return_dist = cost_matrix[u][0]
        return_time = return_dist / speed
        departure_time_from_u = path_time + inspection_time
        arrival_at_depot = departure_time_from_u + return_time

        # Check if the final return to the depot is within its time window
        if arrival_at_depot <= time_windows[0][1]:
            total_cost = path_cost + return_dist
            if total_cost < min_total_cost:
                min_total_cost = total_cost
                last_station = u

    # If no feasible tour was found
    if last_station == -1:
        return {"path": [], "cost": float('inf')}

    # Reconstruct the optimal path by backtracking
    path = []
    current_mask = final_mask
    current_station = last_station

    while current_station is not None:
        path.append(current_station)
        prev_station = parent[current_mask][current_station]
        current_mask ^= (1 << current_station)
        current_station = prev_station
        
    path.reverse()
    path.insert(0, 0) # Start from depot
    path.append(0)    # Return to depot
    
    return {"path": path, "cost": min_total_cost}

def main():
    NUM_STATIONS = 15
    MAX_COORD = 500
    INSPECTION_TIME = 10
    SPEED = 1
    random.seed(42)

    print(f"Generating a random test case with {NUM_STATIONS} stations...")

    coords = [(random.randint(0, MAX_COORD), random.randint(0, MAX_COORD)) for _ in range(NUM_STATIONS)]
    
    cost_matrix = [[math.hypot(c1[0]-c2[0], c1[1]-c2[1]) for c2 in coords] for c1 in coords]

    # Generate plausible time windows
    max_travel_time_per_leg = math.hypot(MAX_COORD, MAX_COORD) / SPEED
    avg_time_per_station = max_travel_time_per_leg / 2 + INSPECTION_TIME
    total_estimated_time = avg_time_per_station * NUM_STATIONS * 1.5 

    time_windows = [(0, total_estimated_time)]
    for i in range(1, NUM_STATIONS):
        center = (total_estimated_time / NUM_STATIONS) * i
        window_width = random.uniform(avg_time_per_station * 1.5, avg_time_per_station * 4)
        start_time = max(0, center - window_width / 2)
        end_time = start_time + window_width
        time_windows.append((start_time, end_time))

    print("Solving for optimal route...")
    start_time_solve = time.time()
    result = find_optimal_route(cost_matrix, time_windows, INSPECTION_TIME, SPEED)
    end_time_solve = time.time()

    print("\n" + "="*20 + " RESULTS " + "="*20)
    if not result["path"]:
        print("No feasible solution found.")
    else:
        print(f"Optimal Path Found: {result['path']}")
        print(f"Total Cost (Energy): {result['cost']:.2f}")

    elapsed_time = end_time_solve - start_time_solve
    print(f"\nSolution found in: {elapsed_time:.4f} seconds")
    print("="*49)


if __name__ == "__main__":
    main()