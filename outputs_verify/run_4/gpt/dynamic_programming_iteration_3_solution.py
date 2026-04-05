import random
import time
from functools import lru_cache

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_travel_cost": 0,
            "total_time": 0,
            "feasible": True,
        }

    travel_time = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    windows = [tuple(w) for w in time_windows]

    full_mask = (1 << n) - 1

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            earliest, latest = windows[last]
            start = max(0.0, earliest)
            finish = start + inspection_time
            if finish <= latest:
                return (0.0, start, None)
            return None

        prev_mask = mask ^ (1 << last)
        best = None
        best_key = None

        earliest_last, latest_last = windows[last]

        pm = prev_mask
        while pm:
            lsb = pm & -pm
            prev = lsb.bit_length() - 1
            pm ^= lsb

            prev_res = dp(prev_mask, prev)
            if prev_res is None:
                continue

            prev_cost, prev_finish, _ = prev_res
            arrival = prev_finish + travel_time[prev][last]
            start = max(arrival, earliest_last)
            finish = start + inspection_time

            if finish > latest_last:
                continue

            total_cost = prev_cost + cost_matrix[prev][last]
            key = (total_cost, finish)

            if best is None or key < best_key:
                best = (total_cost, finish, prev)
                best_key = key

        return best

    best_end = None
    best_result = None
    best_key = None

    for last in range(n):
        res = dp(full_mask, last)
        if res is None:
            continue
        total_cost, finish, prev = res
        key = (total_cost, finish)
        if best_result is None or key < best_key:
            best_result = (total_cost, finish, last)
            best_key = key

    if best_result is None:
        return {
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_travel_cost": None,
            "total_time": None,
            "feasible": False,
        }

    total_cost, total_time, last = best_result

    route = []
    mask = full_mask
    cur = last
    while cur is not None:
        route.append(cur)
        res = dp(mask, cur)
        prev = res[2]
        mask ^= (1 << cur)
        cur = prev
    route.reverse()

    arrival_times = []
    start_times = []
    finish_times = []

    current_finish = 0.0
    prev = None
    for node in route:
        if prev is None:
            arrival = 0.0
        else:
            arrival = current_finish + travel_time[prev][node]
        start = max(arrival, windows[node][0])
        finish = start + inspection_time

        arrival_times.append(arrival)
        start_times.append(start)
        finish_times.append(finish)

        current_finish = finish
        prev = node

    return {
        "route": route,
        "arrival_times": arrival_times,
        "start_times": start_times,
        "finish_times": finish_times,
        "total_travel_cost": total_cost,
        "total_time": total_time,
        "feasible": True,
    }

def _generate_random_test_case(n=15, seed=None):
    if seed is not None:
        random.seed(seed)

    coords = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n)]
    cost_matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        xi, yi = coords[i]
        for j in range(n):
            if i == j:
                continue
            xj, yj = coords[j]
            dist = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
            cost_matrix[i][j] = round(dist, 2)

    inspection_time = 2.0
    base_order = list(range(n))
    random.shuffle(base_order)

    time_windows = [None] * n
    current_time = 0.0
    prev = None
    for node in base_order:
        if prev is not None:
            current_time += cost_matrix[prev][node]
        earliest = max(0.0, current_time - random.uniform(5, 15))
        latest = current_time + inspection_time + random.uniform(20, 50)
        time_windows[node] = (round(earliest, 2), round(latest, 2))
        current_time = max(current_time, earliest) + inspection_time
        prev = node

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