import random
import time
from functools import lru_cache

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "route": [],
            "arrival_times": [],
            "total_time": 0,
            "feasible": True,
        }

    travel = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    full_mask = (1 << n) - 1
    INF = float("inf")

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            earliest, latest = time_windows[last]
            arrival = max(0, earliest)
            if arrival > latest:
                return INF, None
            finish = arrival + inspection_time
            return finish, None

        prev_mask = mask ^ (1 << last)
        best_finish = INF
        best_prev = None
        earliest_last, latest_last = time_windows[last]

        pm = prev_mask
        while pm:
            lsb = pm & -pm
            prev = lsb.bit_length() - 1
            prev_finish, _ = dp(prev_mask, prev)
            if prev_finish != INF:
                arrival = max(prev_finish + travel[prev][last], earliest_last)
                if arrival <= latest_last:
                    finish = arrival + inspection_time
                    if finish < best_finish:
                        best_finish = finish
                        best_prev = prev
            pm ^= lsb

        return best_finish, best_prev

    best_end = None
    best_total = INF
    for last in range(n):
        total_finish, _ = dp(full_mask, last)
        if total_finish < best_total:
            best_total = total_finish
            best_end = last

    if best_end is None or best_total == INF:
        return {
            "route": [],
            "arrival_times": [],
            "total_time": None,
            "feasible": False,
        }

    route = []
    mask = full_mask
    last = best_end
    while last is not None:
        route.append(last)
        _, prev = dp(mask, last)
        mask ^= 1 << last
        last = prev
    route.reverse()

    arrival_times = []
    current_finish = None
    for idx, node in enumerate(route):
        earliest, latest = time_windows[node]
        if idx == 0:
            arrival = max(0, earliest)
        else:
            prev = route[idx - 1]
            arrival = max(current_finish + travel[prev][node], earliest)
        if arrival > latest:
            return {
                "route": [],
                "arrival_times": [],
                "total_time": None,
                "feasible": False,
            }
        arrival_times.append(arrival)
        current_finish = arrival + inspection_time

    return {
        "route": route,
        "arrival_times": arrival_times,
        "total_time": current_finish,
        "feasible": True,
    }

def main():
    random.seed(42)
    n = 15
    inspection_time = 2
    speed = 1

    cost_matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = random.randint(1, 20)
            cost_matrix[i][j] = d
            cost_matrix[j][i] = d

    time_windows = []
    current = 0
    for _ in range(n):
        start = max(0, current + random.randint(0, 5))
        end = start + random.randint(20, 50)
        time_windows.append((start, end))
        current += random.randint(1, 4)

    start_time = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.perf_counter() - start_time

    print("Cost matrix:")
    for row in cost_matrix:
        print(row)
    print("\nTime windows:")
    for i, tw in enumerate(time_windows):
        print(i, tw)
    print("\nResult:")
    print(result)
    print("\nElapsed time: {:.6f} seconds".format(elapsed))

if __name__ == "__main__":
    main()