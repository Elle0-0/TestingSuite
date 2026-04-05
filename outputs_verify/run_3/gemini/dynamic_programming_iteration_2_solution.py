import math

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {
            "feasible": True,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }
    if n == 1:
        earliest, latest = time_windows[0]
        if earliest <= 0 <= latest:
            return {
                "feasible": True,
                "route": [0, 0],
                "arrival_times": [0, 0],
                "total_energy": 0,
            }
        else:
            return {
                "feasible": False,
                "route": [],
                "arrival_times": [],
                "total_energy": -1,
            }

    # dp state: (mask, last_station) -> (min_cost, earliest_finish_time)
    dp = {}
    parent = {}

    # Base case: start at station 0, finish time is 0 (no inspection at start)
    dp[(1, 0)] = (0, 0.0)

    for mask in range(1, 1 << n):
        for i in range(n):
            if (mask, i) in dp:
                prev_cost, prev_finish_time = dp[(mask, i)]

                for j in range(n):
                    if not ((mask >> j) & 1):  # If j is not in the mask
                        new_mask = mask | (1 << j)
                        travel_cost = cost_matrix[i][j]
                        travel_time = float(travel_cost) / speed

                        arrival_at_j = prev_finish_time + travel_time
                        earliest_j, latest_j = time_windows[j]

                        if arrival_at_j <= latest_j:
                            start_service_time = max(arrival_at_j, earliest_j)
                            # No inspection time at station 0
                            current_inspection_time = inspection_time if j != 0 else 0
                            finish_time_at_j = start_service_time + current_inspection_time

                            new_cost = prev_cost + travel_cost

                            current_best_cost, current_best_finish = dp.get((new_mask, j), (math.inf, math.inf))
                            
                            if new_cost < current_best_cost or \
                               (new_cost == current_best_cost and finish_time_at_j < current_best_finish):
                                dp[(new_mask, j)] = (new_cost, finish_time_at_j)