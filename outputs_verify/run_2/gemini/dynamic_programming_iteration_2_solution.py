import collections

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    start_node = 0

    if n == 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    # Handle n=1 case separately
    if n == 1:
        start_time, end_time = time_windows[0]
        if start_time + inspection_time <= end_time:
            return {
                "feasible": True,
                "route": [0, 0],
                "arrival_times": [start_time, start_time],
                "total_energy": 0
            }
        else:
            return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
            
    # DP state: dp[(mask, u)] = (min_energy, earliest_departure_time)
    # mask is a bitmask of visited nodes, u is the last visited node.
    dp = {}
    parent = {}

    # Base case: start at the depot (node 0)
    start_arrival_time = time_windows[start_node][0]
    start_depart_time = max(0, start_arrival_time) + inspection_time
    
    # Check if starting is even possible
    if start_depart_time > time_windows[start_node][1]:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    dp[(1 << start_node, start_node)] = (0, start_depart_time)

    # Iterate through all subsets of nodes
    for mask in range(1, 1 << n):
        for prev_node in range(n):
            if (mask >> prev_node) & 1:
                if (mask, prev_node) not in dp:
                    continue
                
                prev_energy, prev_depart_time = dp[(mask, prev_node)]

                for next_node in range(n):
                    # If next_node is not in the current path
                    if not ((mask >> next_node) & 1):
                        travel_cost = cost_matrix[prev_node][next_node]
                        travel_time = travel_cost / speed
                        
                        arrival_time = prev_depart_time + travel_time
                        earliest, latest = time_windows[next_node]

                        # Check time window constraint
                        if arrival_time > latest:
                            continue

                        # Drone waits if it arrives early
                        ready_time = max(arrival_time, earliest)
                        depart_time = ready_time + inspection_time
                        
                        new_energy = prev_energy + travel_cost
                        new_mask = mask | (1 << next_node)

                        # Update DP table if a better path is found
                        if (new_mask, next_node) not in dp or \
                           new_energy < dp[(new_mask, next_node)][0] or \
                           (new_energy == dp[(new_mask, next_node)][0] and depart_time < dp[(new_mask, next_node)][1]):
                            dp[(new_mask, next_node)] = (new_energy, depart_time)
                            parent[(new_mask, next_node)] = prev_node

    # Find the optimal final path that returns to the depot
    final_mask = (1 << n) - 1
    min_total_energy = float('inf')
    best_last_node = -1

    for last_node in range(n):
        if (final_mask, last_node) in dp:
            last_energy, last_depart_time = dp[(final_mask, last_node)]
            return_cost = cost_matrix[last_node][start_node]
            return_time = return_cost / speed
            
            arrival_at_base = last_depart_time + return_time

            if arrival_at_base <= time_windows[start_node][1]:
                total_energy = last_energy + return_cost
                if total_energy < min_total_energy:
                    min_total_energy = total_energy
                    best_last_node = last_node

    if best_last_node == -1:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    # Reconstruct the path
    route = [start_node]
    curr_node = best_last_node
    mask = final_mask
    temp_path = []
    while curr_node != start_node:
        temp_path.append(curr_node)
        prev_node = parent[(mask, curr_node)]
        mask ^= (1 << curr_node)
        curr_node = prev_node
    route.extend(reversed(temp_path))
    route.append(start_node)

    # Reconstruct arrival times for the optimal route
    arrival_times = [0.0] * len(route)
    # Arrive at base at its earliest time
    arrival_times[0] = float(time_windows[route[0]][0])
    current_depart_time = max(arrival_times[0], time_windows[route[0]][0]) + inspection_time
    
    for i in range(1, len(route)):
        prev_node_idx = route[i-1]
        curr_node_idx = route[i]
        
        travel_cost = cost_matrix[prev_node_idx][curr_node_idx]
        travel_time = travel_cost / speed
        
        current_arrival_time = current_depart_time + travel_time
        arrival_times[i] = current_arrival_time
        
        if i < len(route) - 1: # Don't calculate departure for the final return to base
             current_depart_time = max(current_arrival_time, time_windows[curr_node_idx][0]) + inspection_time

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": min_total_energy
    }

def main():
    # Example from problem description
    # 4 stations: 0 (base), 1, 2, 3
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]

    # Time windows for each station (earliest, latest)
    # Using a feasible example
    time_windows = [
        (0, 200),    # Station 0 (Base)
        (10, 40),    # Station 1
        (45, 75),    # Station 2
        (80, 110)    # Station 3
    ]

    inspection_time = 5
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    print(f"Feasible: {result['feasible']}")
    if result['feasible']:
        print(f"Route: {result['route']}")
        # Format arrival times for readability
        formatted_times = [f"{t:.2f}" for t in result['arrival_times']]
        print(f"Arrival Times: {formatted_times}")
        print(f"Total Energy: {result['total_energy']}")

    print("\n--- Infeasible Example ---")
    infeasible_time_windows = [
        (0, 100),
        (20, 30),
        (0, 20),
        (90, 100)
    ]
    infeasible_result = find_optimal_route(cost_matrix, infeasible_time_windows, inspection_time, speed)
    print(f"Feasible: {infeasible_result['feasible']}")
    if not infeasible_result['feasible']:
        print("No feasible route found.")


if __name__ == "__main__":
    main()