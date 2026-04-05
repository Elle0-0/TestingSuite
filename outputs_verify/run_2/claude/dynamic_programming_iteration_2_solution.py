import itertools


def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    
    if n == 1:
        return {
            "feasible": True,
            "route": [0, 0],
            "arrival_times": [0, 0],
            "total_energy": 0
        }
    
    stations = list(range(1, n))
    
    # DP with bitmask over stations 1..n-1
    # State: (visited_mask, current_station) -> (min_energy, earliest_feasible_arrival_time, route)
    # We need to track time carefully: we want minimum energy, but among min energy solutions,
    # we need one that is time-feasible.
    
    # Actually, we need to find routes that are both energy-optimal AND time-feasible.
    # But time feasibility depends on the order. We need to find the minimum energy route
    # among all time-feasible routes.
    
    # DP state: (mask, current_node) -> list of (energy_so_far, current_time) Pareto-optimal states
    # Since we want minimum energy and time affects feasibility, we need to track both.
    # To keep it tractable, for each (mask, node) we track the best (min energy) for each achievable time,
    # but that could be large. 
    
    # Simpler approach for small n: since bitmask DP with time tracking.
    # For each state (mask, node), store the minimum arrival time achievable for each energy level,
    # or more practically, store (min_energy, min_time_at_that_energy) with Pareto filtering.
    
    # Let's store for each (mask, node): a list of (energy, time) pairs where no pair dominates another.
    # A pair (e1, t1) dominates (e2, t2) if e1 <= e2 and t1 <= t2.
    
    num_stations = n - 1
    full_mask = (1 << num_stations) - 1
    
    # dp[(mask, node)] = list of (energy, time, parent_info) - Pareto optimal
    # For reconstruction, we'll store the path differently.
    
    # Actually, let's use dp[(mask, node)] = list of (energy, arrival_time) Pareto-optimal pairs
    # and separately track parents for reconstruction.
    
    INF = float('inf')
    
    # dp[mask][node] = list of (energy, time) tuples, Pareto-optimal
    dp = {}
    parent = {}  # (mask, node, energy, time) -> (prev_mask, prev_node, prev_energy, prev_time)
    
    # Initialize: start from node 0, visit first station
    for i in stations:
        bit = 1 << (i - 1)
        travel_time = cost_matrix[0][i] // speed if speed != 0 else cost_matrix[0][i]
        travel_energy = cost_matrix[0][i]
        arrival_time = travel_time  # depart at time 0
        
        tw_start, tw_end = time_windows[i]
        
        if arrival_time > tw_end:
            continue  # infeasible
        
        effective_arrival = max(arrival_time, tw_start)
        departure_time = effective_arrival + inspection_time
        
        state = (bit, i)
        dp[state] = [(travel_energy, departure_time, effective_arrival)]
        parent[(bit, i, travel_energy, departure_time)] = (0, 0, 0, 0)  # came from node 0
    
    # Expand
    for mask in range(1, full_mask + 1):
        for curr in stations:
            if not (mask & (1 << (curr - 1))):
                continue
            state = (mask, curr)
            if state not in dp:
                continue
            
            for energy, depart_time, arr_time_curr in dp[state]:
                for nxt in stations:
                    if mask & (1 << (nxt - 1)):
                        continue  # already visited
                    
                    new_mask = mask | (1 << (nxt - 1))
                    travel_energy = cost_matrix[curr][nxt]
                    travel_time = travel_energy // speed if speed != 0 else travel_energy
                    
                    arrival_time = depart_time + travel_time
                    tw_start, tw_end = time_windows[nxt]
                    
                    if arrival_time > tw_end:
                        continue
                    
                    effective_arrival = max(arrival_time, tw_start)
                    departure_time_nxt = effective_arrival + inspection_time
                    new_energy = energy + travel_energy
                    
                    new_state = (new_mask, nxt)
                    
                    # Check Pareto dominance
                    if new_state in dp:
                        dominated = False
                        to_remove = []
                        for idx, (e, t, a) in enumerate(dp[new_state]):
                            if e <= new_energy and t <= departure_time_nxt:
                                dominated = True
                                break
                            if new_energy <= e and departure_time_nxt <= t:
                                to_remove.append(idx)
                        
                        if dominated:
                            continue
                        
                        for idx in sorted(to_remove, reverse=True):
                            entry = dp[new_state][idx]
                            pkey = (new_mask, nxt, entry[0], entry[1])
                            if pkey in parent:
                                del parent[pkey]
                            dp[new_state].pop(idx)
                        
                        dp[new_state].append((new_energy, departure_time_nxt, effective_arrival))
                    else:
                        dp[new_state] = [(new_energy, departure_time_nxt, effective_arrival)]
                    
                    parent[(new_mask, nxt, new_energy, departure_time_nxt)] = (mask, curr, energy, depart_time)
    
    # Find best complete route back to 0
    best_energy = INF
    best_last = None
    best_return_time = None
    
    for curr in stations:
        state = (full_mask, curr)
        if state not in dp:
            continue
        for energy, depart_time, arr_time_curr in dp[state]:
            return_energy = cost_matrix[curr][0]
            return_time_travel = return_energy // speed if speed != 0 else return_energy
            total_energy = energy + return_energy
            arrival_at_base = depart_time + return_time_travel
            
            if total_energy < best_energy:
                best_energy = total_energy
                best_last = (full_mask, curr, energy, depart_time)
                best_return_time = arrival_at_base
    
    if best_last is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }
    
    # Reconstruct route
    route = []
    arrival_times_map = {}
    
    # Trace back
    current = best_last
    while current != (0, 0, 0, 0):
        mask, node, energy, depart_time = current
        # Find the arrival time at this node
        state = (mask, node)
        arr_time = None
        for e, t, a in dp[state]:
            if e == energy and t == depart_time:
                arr_time = a
                break
        
        route.append(node)
        arrival_times_map[node] = arr_time
        
        pkey = (mask, node, energy, depart_time)
        if pkey not in parent:
            break
        prev = parent[pkey]
        current = prev
    
    route.reverse()
    
    # Build full route with depot
    full_route = [0] + route + [0]
    arrival_times = [0]  # departure from base at time 0
    for node in route:
        arrival_times.append(arrival_times_map[node])
    arrival_times.append(best_return_time)
    
    return {
        "feasible": True,
        "route": full_route,
        "arrival_times": arrival_times,
        "total_energy": best_energy
    }


def main():
    # Example: 4 stations (0 is base, 1-3 are monitoring stations)
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]
    
    # Time windows: (earliest, latest) for each station
    # Station 0 (base) has no constraint
    time_windows = [
        (0, 1000),   # base - not used
        (5, 50),     # station 1: can arrive between time 5 and 50
        (10, 60),    # station 2: can arrive between time 10 and 60
        (30, 80),    # station 3: can arrive between time 30 and 80
    ]
    
    inspection_time = 5  # 5 time units at each station
    speed = 1  # 1 unit distance per time unit
    
    print("=== Drone Route Optimization with Time Windows ===")
    print(f"Number of stations: {len(cost_matrix) - 1} (plus base)")
    print(f"Inspection time: {inspection_time}")
    print(f"Speed: {speed}")
    print(f"Time windows: {time_windows[1:]}")
    print()
    
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    
    print(f"Feasible: {result['feasible']}")
    if result['feasible']:
        print(f"Optimal Route: {result['route']}")
        print(f"Arrival Times: {result['arrival_times']}")
        print(f"Total Energy: {result['total_energy']}")
        
        print("\nDetailed Schedule:")
        for i, station in enumerate(result['route']):
            arrival = result['arrival_times'][i]
            if station == 0:
                if i == 0:
                    print(f"  Depart base (station 0) at time {arrival}")
                else:
                    print(f"  Return to base (station 0) at time {arrival}")
            else:
                tw = time_windows[station]
                print(f"  Station {station}: arrive at time {arrival} (window: [{tw[0]}, {tw[1]}])")
    else:
        print("No feasible route found!")
    
    # Demonstrate infeasible case
    print("\n=== Infeasible Example ===")
    tight_windows = [
        (0, 1000),
        (5, 8),     # very tight window for station 1
        (5, 8),     # very tight window for station 2
        (5, 8),     # very tight window for station 3
    ]
    
    result2 = find_optimal_route(cost_matrix, tight_windows, inspection_time, speed)
    print(f"Feasible: {result2['feasible']}")
    if not result2['feasible']:
        print("No feasible route found (as expected with very tight windows).")


if __name__ == "__main__":
    main()