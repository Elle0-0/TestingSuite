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
            "total_time": 0.0,
            "total_cost": 0.0,
        }

    travel = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    full_mask = (1 << n) - 1
    INF = float("inf")

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            a = max(0.0, time_windows[last][0])
            if a > time_windows[last][1]:
                return (INF, INF, -1)
            f = a + inspection_time
            return (f, 0.0, -1)

        prev_mask = mask ^ (1 << last)
        best_finish = INF
        best_cost = INF
        best_prev = -1
        latest_last = time_windows[last][1]

        pm = prev_mask
        while pm:
            bit = pm & -pm
            prev = bit.bit_length() - 1
            prev_finish, prev_cost, _ = dp(prev_mask, prev)
            if prev_finish != INF:
                arrival = prev_finish + travel[prev][last]
                start = max(arrival, time_windows[last][0])
                if start <= latest_last:
                    finish = start + inspection_time
                    total_cost = prev_cost + cost_matrix[prev][last]
                    if finish < best_finish or (finish == best_finish and total_cost < best_cost):
                        best_finish = finish
                        best_cost = total_cost
                        best_prev = prev
            pm ^= bit

        return (best_finish, best_cost, best_prev)

    best_last = -1
    best_finish = INF
    best_cost = INF

    for last in range(n):
        finish, cost, _ = dp(full_mask, last)
        if finish < best_finish or (finish == best_finish and cost < best_cost):
            best_finish = finish
            best_cost = cost
            best_last = last

    if best_last == -1 or best_finish == INF:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_time": None,
            "total_cost": None,
        }

    route = []
    mask = full_mask
    last = best_last
    while last != -1:
        route.append(last)
        _, _, prev = dp(mask, last)
        mask ^= (1 << last)
        last = prev
    route.reverse()

    arrival_times = []
    start_times = []
    finish_times = []

    current_finish = None
    prev = None
    total_cost = 0.0

    for node in route:
        if prev is None:
            arrival = 0.0
        else:
            arrival = current_finish + travel[prev][node]
            total_cost += cost_matrix[prev][node]
        start = max(arrival, time_windows[node][0])
        if start > time_windows[node][1]:
            return {
                "feasible": False,
                "route": [],
                "arrival_times": [],
                "start_times": [],
                "finish_times": [],
                "total_time": None,
                "total_cost": None,
            }
        finish = start + inspection_time
        arrival_times.append(arrival)
        start_times.append(start)
        finish_times.append(finish)
        current_finish = finish
        prev = node

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "start_times": start_times,
        "finish_times": finish_times,
        "total_time": finish_times[-1] if finish_times else 0.0,
        "total_cost": total_cost,
    }

def _generate_feasible_test_case(n=15, inspection_time=2, speed=1, seed=None):
    if seed is not None:
        random.seed(seed)

    coords = [(random.randint(0, 100), random.randint(0, 100)) for _ in range(n)]
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = coords[i]
        for j in range(n):
            if i == j:
                continue
            xj, yj = coords[j]
            dist = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
            cost_matrix[i][j] = round(dist, 2)

    order = list(range(n))
    random.shuffle(order)

    time_windows = [[0.0, 0.0] for _ in range(n)]
    current_time = 0.0
    prev = None
    for node in order:
        if prev is not None:
            current_time += cost_matrix[prev][node] / speed
        earliest = max(0.0, current_time - random.uniform(0, 5))
        latest = current_time + random.uniform(15, 35)
        time_windows[node] = [round(earliest, 2), round(latest, 2)]
        current_time = max(current_time, earliest) + inspection_time
        prev = node

    return cost_matrix, time_windows

def main():
    n = 15
    inspection_time = 2
    speed = 1

    cost_matrix, time_windows = _generate_feasible_test_case(
        n=n,
        inspection_time=inspection_time,
        speed=speed,
        seed=42,
    )

    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)
    elapsed = time.perf_counter() - start

    print("Stations:", n)
    print("Inspection time:", inspection_time)
    print("Speed:", speed)
    print("Time windows:", time_windows)
    print("Result:", result)
    print("Elapsed time: {:.6f} seconds".format(elapsed))

if __name__ == "__main__":
    main()