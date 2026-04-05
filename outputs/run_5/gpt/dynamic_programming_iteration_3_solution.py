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

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            earliest, latest = windows[last]
            start = max(0.0, earliest)
            finish = start + inspection_time
            if finish <= latest:
                return (0.0, start, -1)
            return None

        prev_mask = mask ^ (1 << last)
        best = None

        for prev in range(n):
            if not (prev_mask & (1 << prev)):
                continue
            prev_state = dp(prev_mask, prev)
            if prev_state is None:
                continue

            prev_cost, prev_finish, _ = prev_state
            arrival = prev_finish + travel_time[prev][last]
            earliest, latest = windows[last]
            start = max(arrival, earliest)
            finish = start + inspection_time
            if finish > latest:
                continue

            total_cost = prev_cost + cost_matrix[prev][last]
            candidate = (total_cost, finish, prev)

            if best is None:
                best = candidate
            else:
                if total_cost < best[0] or (total_cost == best[0] and finish < best[1]):
                    best = candidate

        return best

    full_mask = (1 << n) - 1
    best_end = None
    best_result = None

    for last in range(n):
        state = dp(full_mask, last)
        if state is None:
            continue
        total_cost, finish, prev = state
        candidate = (total_cost, finish, last)
        if best_result is None:
            best_result = candidate
            best_end = last
        else:
            if total_cost < best_result[0] or (total_cost == best_result[0] and finish < best_result[1]):
                best_result = candidate
                best_end = last

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

    route = []
    mask = full_mask
    last = best_end
    while last != -1:
        route.append(last)
        state = dp(mask, last)
        prev = state[2]
        mask ^= (1 << last)
        last = prev
    route.reverse()

    arrival_times = []
    start_times = []
    finish_times = []

    current_finish = 0.0
    total_travel_cost = 0.0

    for idx, station in enumerate(route):
        if idx == 0:
            arrival = 0.0
        else:
            prev = route[idx - 1]
            arrival = current_finish + travel_time[prev][station]
            total_travel_cost += cost_matrix[prev][station]

        earliest, latest = windows[station]
        start = max(arrival, earliest)
        finish = start + inspection_time

        arrival_times.append(arrival)
        start_times.append(start)
        finish_times.append(finish)

        current_finish = finish

    return {
        "route": route,
        "arrival_times": arrival_times,
        "start_times": start_times,
        "finish_times": finish_times,
        "total_travel_cost": total_travel_cost,
        "total_time": finish_times[-1] if finish_times else 0.0,
        "feasible": True,
    }

def _generate_random_test_case(n=15, seed=None):
    if seed is not None:
        random.seed(seed)

    coords = [(random.randint(0, 100), random.randint(0, 100)) for _ in range(n)]
    cost_matrix = [[0] * n for _ in range(n)]

    for i in range(n):
        xi, yi = coords[i]
        for j in range(n):
            xj, yj = coords[j]
            if i == j:
                cost_matrix[i][j] = 0
            else:
                dist = abs(xi - xj) + abs(yi - yj)
                cost_matrix[i][j] = dist + random.randint(0, 10)

    inspection_time = random.randint(2, 6)

    base_order = list(range(n))
    random.shuffle(base_order)

    time_windows = [None] * n
    current_time = 0
    for idx, station in enumerate(base_order):
        slack_before = random.randint(0, 10)
        width = random.randint(60, 140)
        earliest = current_time + slack_before
        latest = earliest + width
        time_windows[station] = (earliest, latest)
        current_time = earliest + inspection_time + random.randint(5, 20)

    return cost_matrix, time_windows, inspection_time

def main():
    cost_matrix, time_windows, inspection_time = _generate_random_test_case(n=15, seed=42)

    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start

    print("Inspection time:", inspection_time)
    print("Time windows:", time_windows)
    print("Result:", result)
    print("Elapsed time: {:.6f} seconds".format(elapsed))

if __name__ == "__main__":
    main()