import random
import time
from functools import lru_cache

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "feasible": True,
            "route": [],
            "total_cost": 0.0,
            "arrival_times": [],
            "start_time": 0.0,
        }

    travel = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    full_mask = (1 << n) - 1

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            earliest, latest = time_windows[last]
            start_service = max(0.0, earliest)
            if start_service > latest:
                return None
            finish = start_service + inspection_time
            return (cost_matrix[last][last] if last < len(cost_matrix) and last < len(cost_matrix[last]) else 0.0, finish, -1)

        prev_mask = mask ^ (1 << last)
        best = None
        best_cost = float("inf")
        earliest_last, latest_last = time_windows[last]

        pm = prev_mask
        while pm:
            bit = pm & -pm
            prev = bit.bit_length() - 1
            prev_state = dp(prev_mask, prev)
            if prev_state is not None:
                prev_cost, prev_finish, _ = prev_state
                arrival = prev_finish + travel[prev][last]
                start_service = max(arrival, earliest_last)
                if start_service <= latest_last:
                    finish = start_service + inspection_time
                    total_cost = prev_cost + cost_matrix[prev][last]
                    if total_cost < best_cost:
                        best_cost = total_cost
                        best = (total_cost, finish, prev)
            pm ^= bit

        return best

    best_end = None
    best_cost = float("inf")
    best_finish = None

    for last in range(n):
        state = dp(full_mask, last)
        if state is not None:
            total_cost, finish, _ = state
            if total_cost < best_cost:
                best_cost = total_cost
                best_finish = finish
                best_end = last

    if best_end is None:
        return {
            "feasible": False,
            "route": [],
            "total_cost": None,
            "arrival_times": [],
            "start_time": None,
        }

    route = []
    mask = full_mask
    last = best_end
    while last != -1:
        route.append(last)
        state = dp(mask, last)
        _, _, prev = state
        mask ^= (1 << last)
        last = prev
    route.reverse()

    arrival_times = []
    current_finish = None
    total_cost = 0.0
    for idx, node in enumerate(route):
        earliest, latest = time_windows[node]
        if idx == 0:
            arrival = 0.0
            start_service = max(arrival, earliest)
            if start_service > latest:
                return {
                    "feasible": False,
                    "route": [],
                    "total_cost": None,
                    "arrival_times": [],
                    "start_time": None,
                }
            arrival_times.append(start_service)
            current_finish = start_service + inspection_time
        else:
            prev = route[idx - 1]
            arrival = current_finish + travel[prev][node]
            start_service = max(arrival, earliest)
            if start_service > latest:
                return {
                    "feasible": False,
                    "route": [],
                    "total_cost": None,
                    "arrival_times": [],
                    "start_time": None,
                }
            arrival_times.append(start_service)
            current_finish = start_service + inspection_time
            total_cost += cost_matrix[prev][node]

    return {
        "feasible": True,
        "route": route,
        "total_cost": best_cost,
        "arrival_times": arrival_times,
        "start_time": arrival_times[0] if arrival_times else 0.0,
        "finish_time": best_finish,
    }

def _generate_feasible_case(n, seed=None):
    if seed is not None:
        random.seed(seed)

    coords = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n)]
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = coords[i]
        for j in range(n):
            xj, yj = coords[j]
            if i == j:
                cost_matrix[i][j] = 0.0
            else:
                dx = xi - xj
                dy = yi - yj
                cost_matrix[i][j] = round((dx * dx + dy * dy) ** 0.5, 2)

    inspection_time = 3.0
    order = list(range(n))
    random.shuffle(order)

    time_windows = [None] * n
    t = 0.0
    first = order[0]
    e = max(0.0, t + random.uniform(0, 5))
    l = e + random.uniform(20, 50)
    time_windows[first] = (round(e, 2), round(l, 2))
    t = e + inspection_time

    for k in range(1, n):
        prev = order[k - 1]
        cur = order[k]
        t += cost_matrix[prev][cur]
        e = max(0.0, t - random.uniform(0, 5))
        l = t + random.uniform(25, 60)
        time_windows[cur] = (round(e, 2), round(l, 2))
        t = max(t, e) + inspection_time

    return cost_matrix, time_windows, inspection_time

def main():
    n = 15
    cost_matrix, time_windows, inspection_time = _generate_feasible_case(n, seed=42)

    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start

    print("Stations:", n)
    print("Inspection time:", inspection_time)
    print("Time windows:")
    for i, tw in enumerate(time_windows):
        print(f"  {i}: {tw}")
    print("Result:")
    print(result)
    print(f"Elapsed time: {elapsed:.6f} seconds")

if __name__ == "__main__":
    main()