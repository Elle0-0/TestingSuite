import random
import time
import sys

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {'path': [], 'total_duration': 0, 'stations_visited': 0}
    if n == 1:
        return {'path': [0, 0], 'total_duration': 0, 'stations_visited': 0}

    # memo[mask][u] stores the earliest arrival time at station u,
    # having visited the set of stations represented by mask.
    memo = [[float('inf')] * n for _ in range(1 << n)]
    
    # parent[mask][u] stores the predecessor of u in the optimal path to
    # the state (mask, u), used for path reconstruction.
    parent = [[-1] * n for _ in range(1 << n)]

    # Initial state: start at depot (station 0) at time 0.
    # The mask '1' represents the set {0}.
    memo[1][0] = 0

    # Iterate through all subsets of stations (masks).
    for mask in range(1, 1 << n):
        # For each station u in the current subset.
        for u in range(n):
            if not (mask & (1 << u)):
                continue

            if memo[mask][u] == float('inf'):
                continue

            # Calculate departure time from u. Wait if we arrived early.
            departure_time_u = max(memo[mask][u], time_windows[u][0])
            if u != 0:
                departure_time_u += inspection_time

            # Try to transition to a new station v not yet in the mask.
            for v in range(n):
                if not (mask & (1 << v)):
                    travel_time_uv = cost_matrix[u][v] / speed
                    arrival_time_v = departure_time_u + travel_time_uv

                    # Check if the arrival at v is within its time window.
                    if arrival_time_v <= time_windows[v][1]:
                        new_mask = mask | (1 << v)
                        # If we found a shorter path to this new state, update it.
                        if arrival_time_v < memo[new_mask][v]:
                            memo[new_mask][v] = arrival_time_v
                            parent[new_mask][v] = u

    # After filling the DP table, find the best valid complete tour.
    best_duration = float('inf')
    best_mask = -1
    best_last_station = -1
    best_station_count = 0

    # A tour must visit at least one station besides the depot.
    for mask in range(1, 1 << n):
        num_visited = bin(mask).count('1')
        # The last station u must not be the depot.
        for u in range(1, n):
            if (mask & (1 << u)) and memo[mask][u] != float('inf'):
                # Calculate time to return to the depot from u.
                departure_time_u = max(memo[mask][u], time_windows[u][0]) + inspection_time
                return_travel_time = cost_matrix[u][0] / speed
                final_arrival_at_depot = departure_time_u + return_travel_time

                # Check if the final return is within the depot's time window.
                if final_arrival_at_depot <= time_windows[0][1]:
                    # Prioritize maximizing the number of stations visited.
                    if num_visited > best_station_count:
                        best_station_count = num_visited
                        best_duration = final_arrival_at_depot
                        best_mask = mask
                        best_last_station = u
                    # For the same number of stations, prioritize shorter duration.
                    elif num_visited == best_station_count and final_arrival_at_depot < best_duration:
                        best_duration = final_arrival_at_depot
                        best_mask = mask
                        best_last_station = u

    # If no valid tour visiting at least one station was found, return the null tour.
    if best_last_station == -1:
        return {'path': [0, 0], 'total_duration': 0, 'stations_visited': 0}

    # Reconstruct the optimal path by backtracking from the best final state.
    path = []
    curr_station = best_last_station
    curr_mask = best_mask

    while curr_station != 0:
        path.append(curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station) # Remove current station from mask
        curr_station = prev_station
    
    path.append(0)
    path.reverse()
    path.append(0) # Add final return to depot

    return {
        'path': path,
        'total_duration': best_duration,
        'stations_visited': best_station_count - 1 # Exclude depot from count
    }

def main():
    start_time = time.time()
    
    NUM_STATIONS = 15
    MAX_COORD = 200
    random.seed(42)

    # Generate a metric cost matrix based on Euclidean distances
    coords = [(random.randint(0, MAX_COORD), random.randint(0, MAX_COORD)) for _ in range(NUM_STATIONS)]
    cost_matrix = [[0.0] * NUM_STATIONS for _ in range(NUM_STATIONS)]
    for i in range(NUM_STATIONS):
        for j in range(i, NUM_STATIONS):
            dist = ((coords[i][0] - coords[j][0])**2 + (coords[i][1] - coords[j][1])**2)**0.5
            cost_matrix[i][j] = cost_matrix[j][i] = dist

    inspection_time = 10
    speed = 1.0

    time_windows = [(0.0, 0.0)] * NUM_STATIONS
    
    # Depot window must be wide enough to allow for the longest possible tour
    depot_latest_time = NUM_STATIONS * (MAX_COORD * 1.5 + inspection_time)
    time_windows[0] = (0, depot_latest_time)

    # Generate plausible random time windows for other stations
    for i in range(1, NUM_STATIONS):
        earliest_arrival_guess = cost_matrix[0][i] + random.uniform(0, 50)
        window_width = random.uniform(cost_matrix[0][i] * 0.5, cost_matrix[0][i] * 2.0) + inspection_time + 20
        latest_arrival = earliest_arrival_guess + window_width
        time_windows[i] = (earliest_arrival_guess, latest_arrival)

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    end_time = time.time()
    elapsed_time = end_time - start_time

    print("Optimal Route Found:")
    print(f"  Path: {result['path']}")
    print(f"  Stations Visited: {result['stations_visited']}")
    print(f"  Total Duration: {result['total_duration']:.2f}")
    print(f"\nElapsed time: {elapsed_time:.4f} seconds")

if __name__ == "__main__":
    main()