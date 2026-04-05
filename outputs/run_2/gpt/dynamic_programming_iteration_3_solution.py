import random
import time
from heapq import heappush, heappop

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_cost": 0,
            "feasible": True,
        }

    travel = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]
    windows = list(time_windows)
    if isinstance(inspection_time, (int, float)):
        service = [inspection_time] * n
    else:
        service = list(inspection_time)

    full_mask = (1 << n) - 1
    INF = float("inf")

    dp = [dict() for _ in range(1 << n)]
    parent = [dict() for _ in range(1 << n)]

    for i in range(n):
        start = max(0.0, windows[i][0])
        finish = start + service[i]
        if finish <= windows[i][1]:
            mask = 1 << i
            cost = 0.0
            prev = dp[mask].get(i)
            if prev is None or finish < prev[0] or (finish == prev[0] and cost < prev[1]):
                dp[mask][i] = (finish, cost)
                parent[mask][i] = (-1, 0.0, start, finish)

    for mask in range(1 << n):
        if not dp[mask]:
            continue

        items = sorted(dp[mask].items(), key=lambda kv: (kv[1][1], kv[1][0]))
        for last, (curr_finish, curr_cost) in items:
            remaining = full_mask ^ mask
            while remaining:
                bit = remaining & -remaining
                nxt = bit.bit_length() - 1
                remaining ^= bit

                arrival = curr_finish + travel[last][nxt]
                start = max(arrival, windows[nxt][0])
                finish = start + service[nxt]
                if finish > windows[nxt][1]:
                    continue

                new_mask = mask | (1 << nxt)
                new_cost = curr_cost + cost_matrix[last][nxt]
                old = dp[new_mask].get(nxt)

                if old is None or finish < old[0] or (finish == old[0] and new_cost < old[1]) or (new_cost < old[1] and finish <= old[0]):
                    dp[new_mask][nxt] = (finish, new_cost)
                    parent[new_mask][nxt] = (last, arrival, start, finish)

    best_last = None
    best_cost = INF
    best_finish = INF

    for last, (finish, cost) in dp[full_mask].items():
        if cost < best_cost or (cost == best_cost and finish < best_finish):
            best_cost = cost
            best_finish = finish
            best_last = last

    if best_last is None:
        return {
            "route": [],
            "arrival_times": [],
            "start_times": [],
            "finish_times": [],
            "total_cost": None,
            "feasible": False,
        }

    route = []
    arrival_times = []
    start_times = []
    finish_times = []

    mask = full_mask
    last = best_last

    while last != -1:
        route.append(last)
        prev, arrival, start, finish = parent[mask][last]
        arrival_times.append(arrival)
        start_times.append(start)
        finish_times.append(finish)
        mask ^= 1 << last
        last = prev

    route.reverse()
    arrival_times.reverse()
    start_times.reverse()
    finish_times.reverse()

    return {
        "route": route,
        "arrival_times": arrival_times,
        "start_times": start_times,
        "finish_times": finish_times,
        "total_cost": best_cost,
        "feasible": True,
    }

def _generate_feasible_case(n, seed=None):
    if seed is not None:
        random.seed(seed)

    points = [(random.uniform(0, 100), random.uniform(0, 100)) for _ in range(n)]
    cost_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = points[i]
        for j in range(n):
            if i == j:
                continue
            xj, yj = points[j]
            dist = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
            cost_matrix[i][j] = round(dist, 2)

    inspection_time = random.randint(2, 6)

    order = list(range(n))
    random.shuffle(order)

    time_windows = [[0.0, 0.0] for _ in range(n)]
    current_time = 0.0
    prev = None
    for idx, node in enumerate(order):
        if prev is not None:
            current_time += cost_matrix[prev][node]
        earliest = max(0.0, current_time - random.uniform(0, 5))
        slack = random.uniform(20, 60)
        latest = current_time + inspection_time + slack
        time_windows[node] = [round(earliest, 2), round(latest, 2)]
        current_time = max(current_time, earliest) + inspection_time
        prev = node

    return cost_matrix, time_windows, inspection_time

def main():
    n = 15
    cost_matrix, time_windows, inspection_time = _generate_feasible_case(n, seed=42)

    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start

    print("Stations:", n)
    print("Inspection time:", inspection_time)
    print("Time windows:", time_windows)
    print("Result:", result)
    print("Elapsed time: {:.6f} seconds".format(elapsed))

if __name__ == "__main__":
    main()