import random
import time
from functools import lru_cache

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "feasible": True,
            "cost": 0,
            "route": [],
            "arrival_times": [],
            "start_time": 0,
        }

    travel = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    windows = [tuple(w) for w in time_windows]

    @lru_cache(maxsize=None)
    def dp(mask, last):
        if mask == (1 << last):
            earliest, latest = windows[last]
            start_service = max(0.0, earliest)
            if start_service > latest:
                return None
            finish = start_service + inspection_time
            return (finish, start_service, -1, 0.0)

        prev_mask = mask ^ (1 << last)
        best = None
        best_finish = float("inf")

        m = prev_mask
        while m:
            lsb = m & -m
            prev = lsb.bit_length() - 1
            prev_state = dp(prev_mask, prev)
            if prev_state is not None:
                prev_finish = prev_state[0]
                arrival = prev_finish + travel[prev][last]
                earliest, latest = windows[last]
                start_service = max(arrival, earliest)
                if start_service <= latest:
                    finish = start_service + inspection_time
                    if finish < best_finish:
                        best_finish = finish
                        best = (finish, start_service, prev, arrival)
            m ^= lsb

        return best

    full_mask = (1 << n) - 1
    best_last = -1
    best_finish = float("inf")
    for last in range(n):
        state = dp(full_mask, last)
        if state is not None and state[0] < best_finish:
            best_finish = state[0]
            best_last = last

    if best_last == -1:
        return {
            "feasible": False,
            "cost": None,
            "route": [],
            "arrival_times": [],
            "start_time": None,
        }

    route = []
    arrival_times = []
    service_start_times = []
    mask = full_mask
    last = best_last

    while last != -1:
        state = dp(mask, last)
        route.append(last)
        arrival_times.append(state[3] if state[2] != -1 else 0.0)
        service_start_times.append(state[1])
        prev = state[2]
        mask ^= 1 << last
        last = prev

    route.reverse()
    arrival_times.reverse()
    service_start_times.reverse()

    total_travel_cost = 0.0
    for i in range(1, len(route)):
        total_travel_cost += cost_matrix[route[i - 1]][route[i]]

    return {
        "feasible": True,
        "cost": total_travel_cost,
        "route": route,
        "arrival_times": arrival_times,
        "service_start_times": service_start_times,
        "completion_time": best_finish,
        "start_time": service_start_times[0] if service_start_times else 0.0,
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

    inspection_time = 3.0

    base_route = list(range(n))
    random.shuffle(base_route)

    current_time = 0.0
    service_times = [0.0] * n
    for idx, station in enumerate(base_route):
        if idx == 0:
            arrival = 0.0
        else:
            prev = base_route[idx - 1]
            arrival = current_time + cost_matrix[prev][station]
        start = arrival + random.uniform(0, 5)
        service_times[station] = start
        current_time = start + inspection_time

    time_windows = []
    for i in range(n):
        center = service_times[i]
        left_slack = random.uniform(5, 20)
        right_slack = random.uniform(20, 50)
        earliest = max(0.0, center - left_slack)
        latest = center + right_slack
        time_windows.append((round(earliest, 2), round(latest, 2)))

    return cost_matrix, time_windows, inspection_time

def main():
    cost_matrix, time_windows, inspection_time = _generate_random_test_case(15)
    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start
    print("Result:")
    print(result)
    print(f"Elapsed time: {elapsed:.6f} seconds")

if __name__ == "__main__":
    main()