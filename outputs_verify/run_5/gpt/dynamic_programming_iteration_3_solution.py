import random
import time
from functools import lru_cache

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "feasible": True,
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_travel_cost": 0.0,
            "total_time": 0.0,
        }

    travel_time = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    windows = [tuple(w) for w in time_windows]
    ALL = (1 << n) - 1

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            earliest = travel_time[0][last] if last != 0 else 0.0
            start = max(earliest, windows[last][0])
            if start > windows[last][1]:
                return None
            finish = start + inspection_time
            return (finish, travel_time[0][last], -1)

        prev_mask = mask ^ (1 << last)
        best = None

        pm = prev_mask
        while pm:
            lsb = pm & -pm
            prev = lsb.bit_length() - 1
            prev_state = dp(prev_mask, prev)
            if prev_state is not None:
                prev_finish, prev_cost, _ = prev_state
                arrival = prev_finish + travel_time[prev][last]
                start = max(arrival, windows[last][0])
                if start <= windows[last][1]:
                    finish = start + inspection_time
                    total_cost = prev_cost + cost_matrix[prev][last]
                    candidate = (finish, total_cost, prev)
                    if best is None or finish < best[0] or (finish == best[0] and total_cost < best[1]):
                        best = candidate
            pm ^= lsb

        return best

    best_end = None
    best_state = None

    for last in range(n):
        state = dp(ALL, last)
        if state is not None:
            finish, total_cost, prev = state
            if best_state is None or finish < best_state[0] or (finish == best_state[0] and total_cost < best_state[1]):
                best_state = state
                best_end = last

    if best_state is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_travel_cost": None,
            "total_time": None,
        }

    route = []
    mask = ALL
    last = best_end
    while last != -1:
        route.append(last)
        _, _, prev = dp(mask, last)
        mask ^= (1 << last)
        last = prev
    route.reverse()

    arrival_times = []
    start_times = []
    finish_times = []

    current_finish = 0.0
    prev = None
    for idx, node in enumerate(route):
        if idx == 0:
            arrival = travel_time[0][node] if node != 0 else 0.0
        else:
            arrival = current_finish + travel_time[prev][node]
        start = max(arrival, windows[node][0])
        finish = start + inspection_time
        arrival_times.append(arrival)
        start_times.append(start)
        finish_times.append(finish)
        current_finish = finish
        prev = node

    total_travel_cost = 0.0
    if route:
        total_travel_cost += cost_matrix[0][route[0]] if route[0] != 0 else 0.0
        for i in range(1, len(route)):
            total_travel_cost += cost_matrix[route[i - 1]][route[i]]

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "start_times": start_times,
        "finish_times": finish_times,
        "total_travel_cost": total_travel_cost,
        "total_time": finish_times[-1] if finish_times else 0.0,
    }

def _generate_random_test_case(n=15, seed=None):
    if seed is not None:
        random.seed(seed)

    coords = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n)]
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = coords[i]
        for j in range(n):
            xj, yj = coords[j]
            dx = xi - xj
            dy = yi - yj
            cost_matrix[i][j] = (dx * dx + dy * dy) ** 0.5

    inspection_time = 2.0
    base_route = list(range(n))
    current_time = 0.0
    time_windows = []

    for idx, node in enumerate(base_route):
        if idx == 0:
            arrival = 0.0
        else:
            arrival = current_time + cost_matrix[base_route[idx - 1]][node]
        slack_before = random.uniform(0, 20)
        start = arrival + slack_before
        width = random.uniform(30, 80)
        end = start + width
        time_windows.append((max(0.0, start - random.uniform(5, 15)), end))
        current_time = max(arrival, time_windows[-1][0]) + inspection_time

    return cost_matrix, time_windows, inspection_time

def main():
    cost_matrix, time_windows, inspection_time = _generate_random_test_case(n=15, seed=42)
    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start
    print("Result:")
    print(result)
    print(f"Elapsed time: {elapsed:.6f} seconds")

if __name__ == "__main__":
    main()