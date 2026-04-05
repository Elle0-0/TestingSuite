import random
import time
from typing import List, Tuple, Dict, Any

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_travel_cost": 0,
            "total_travel_time": 0.0,
            "feasible": True,
        }

    travel_time = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]

    full_mask = (1 << n) - 1

    dp = [dict() for _ in range(1 << n)]
    parent = [dict() for _ in range(1 << n)]

    for j in range(n):
        open_j, close_j = time_windows[j]
        arrival = 0.0
        start = max(arrival, open_j)
        finish = start + inspection_time
        if finish <= close_j:
            mask = 1 << j
            dp[mask][j] = (finish, 0)
            parent[mask][j] = (-1, 0.0, start, finish)

    for mask in range(1 << n):
        if not dp[mask]:
            continue

        items = sorted(dp[mask].items(), key=lambda x: x[1][0])
        frontier = []
        best_cost = float("inf")
        for last, (fin, cst) in items:
            if cst < best_cost:
                frontier.append((last, fin, cst))
                best_cost = cst

        for last, fin, cst in frontier:
            row_time = travel_time[last]
            row_cost = cost_matrix[last]
            remaining = full_mask ^ mask
            while remaining:
                bit = remaining & -remaining
                nxt = bit.bit_length() - 1
                remaining ^= bit

                arrival = fin + row_time[nxt]
                open_n, close_n = time_windows[nxt]
                start = arrival if arrival >= open_n else open_n
                finish = start + inspection_time
                if finish > close_n:
                    continue

                new_mask = mask | bit
                new_cost = cst + row_cost[nxt]
                prev = dp[new_mask].get(nxt)

                if prev is None or finish < prev[0] or (finish == prev[0] and new_cost < prev[1]):
                    dp[new_mask][nxt] = (finish, new_cost)
                    parent[new_mask][nxt] = (last, arrival, start, finish)
                elif new_cost < prev[1]:
                    dominated = False
                    for other_last, (other_fin, other_cost) in dp[new_mask].items():
                        if other_last == nxt:
                            continue
                        if other_fin <= finish and other_cost <= new_cost:
                            dominated = True
                            break
                    if not dominated:
                        dp[new_mask][nxt] = (finish, new_cost)
                        parent[new_mask][nxt] = (last, arrival, start, finish)

    if not dp[full_mask]:
        return {
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_travel_cost": None,
            "total_travel_time": None,
            "feasible": False,
        }

    best_last = None
    best_finish = None
    best_cost = None
    for last, (fin, cst) in dp[full_mask].items():
        if best_cost is None or cst < best_cost or (cst == best_cost and fin < best_finish):
            best_last = last
            best_finish = fin
            best_cost = cst

    route = []
    arrival_times = []
    start_times = []
    finish_times = []

    mask = full_mask
    last = best_last
    while last != -1:
        prev_last, arrival, start, finish = parent[mask][last]
        route.append(last)
        arrival_times.append(arrival)
        start_times.append(start)
        finish_times.append(finish)
        mask ^= 1 << last
        last = prev_last

    route.reverse()
    arrival_times.reverse()
    start_times.reverse()
    finish_times.reverse()

    total_travel_time = 0.0
    for i in range(1, len(route)):
        total_travel_time += travel_time[route[i - 1]][route[i]]

    return {
        "route": route,
        "arrival_times": arrival_times,
        "start_times": start_times,
        "finish_times": finish_times,
        "total_travel_cost": best_cost,
        "total_travel_time": total_travel_time,
        "feasible": True,
    }

def generate_random_test_case(n=15, seed=None):
    if seed is not None:
        random.seed(seed)

    coords = [(random.randint(0, 100), random.randint(0, 100)) for _ in range(n)]
    cost_matrix = [[0] * n for _ in range(n)]

    for i in range(n):
        xi, yi = coords[i]
        for j in range(n):
            if i == j:
                continue
            xj, yj = coords[j]
            dist = int(round(((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5)) + 1
            cost_matrix[i][j] = dist

    inspection_time = random.randint(2, 6)

    greedy_order = list(range(n))
    random.shuffle(greedy_order)

    current_time = 0
    time_windows = [None] * n
    first = greedy_order[0]
    open_first = max(0, random.randint(0, 10))
    close_first = open_first + inspection_time + random.randint(20, 60)
    time_windows[first] = (open_first, close_first)
    current_time = max(0, open_first) + inspection_time

    for idx in range(1, n):
        prev = greedy_order[idx - 1]
        cur = greedy_order[idx]
        travel = cost_matrix[prev][cur]
        earliest = current_time + travel
        slack_before = random.randint(0, 10)
        open_t = max(0, earliest - slack_before)
        close_t = earliest + inspection_time + random.randint(20, 80)
        time_windows[cur] = (open_t, close_t)
        current_time = max(earliest, open_t) + inspection_time

    return cost_matrix, time_windows, inspection_time

def main():
    cost_matrix, time_windows, inspection_time = generate_random_test_case(n=15, seed=42)

    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start

    print("Inspection time:", inspection_time)
    print("Time windows:")
    for i, tw in enumerate(time_windows):
        print(f"Station {i}: {tw}")
    print("\nResult:")
    print(result)
    print(f"\nElapsed time: {elapsed:.6f} seconds")

if __name__ == "__main__":
    main()