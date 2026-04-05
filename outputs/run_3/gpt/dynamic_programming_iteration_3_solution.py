import random
import time
from bisect import bisect_left

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {
            "route": [],
            "arrival_times": [],
            "total_cost": 0,
            "feasible": True,
        }

    travel = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]

    windows = [(float(a), float(b)) for a, b in time_windows]
    insp = float(inspection_time)

    size = 1 << n
    inf = float("inf")

    states_by_mask = [[] for _ in range(size)]
    best_cost = {}

    parent = {}

    for i in range(n):
        start = max(0.0, windows[i][0])
        if start <= windows[i][1]:
            mask = 1 << i
            cost = 0.0
            key = (mask, i, start)
            best_cost[key] = cost
            parent[key] = None
            states_by_mask[mask].append((i, start))

    for mask in range(size):
        if not states_by_mask[mask]:
            continue

        current_states = states_by_mask[mask]
        current_states.sort(key=lambda x: (x[0], x[1]))

        for last, arr_time in current_states:
            state_key = (mask, last, arr_time)
            curr_cost = best_cost[state_key]

            finish_time = arr_time + insp

            remaining = ((1 << n) - 1) ^ mask
            while remaining:
                bit = remaining & -remaining
                nxt = bit.bit_length() - 1
                remaining ^= bit

                arrival = finish_time + travel[last][nxt]
                if arrival < windows[nxt][0]:
                    arrival = windows[nxt][0]
                if arrival > windows[nxt][1]:
                    continue

                new_mask = mask | (1 << nxt)
                new_cost = curr_cost + cost_matrix[last][nxt]
                new_key = (new_mask, nxt, arrival)

                old = best_cost.get(new_key, inf)
                if new_cost < old:
                    best_cost[new_key] = new_cost
                    parent[new_key] = state_key
                    states_by_mask[new_mask].append((nxt, arrival))

    full_mask = (1 << n) - 1
    best_final_key = None
    best_final_cost = inf

    if states_by_mask[full_mask]:
        for last, arr_time in states_by_mask[full_mask]:
            key = (full_mask, last, arr_time)
            c = best_cost[key]
            if c < best_final_cost:
                best_final_cost = c
                best_final_key = key

    if best_final_key is None:
        best_partial_key = None
        best_count = -1
        best_partial_cost = inf

        for key, c in best_cost.items():
            mask, last, arr_time = key
            count = mask.bit_count()
            if count > best_count or (count == best_count and c < best_partial_cost):
                best_count = count
                best_partial_cost = c
                best_partial_key = key

        if best_partial_key is None:
            return {
                "route": [],
                "arrival_times": [],
                "total_cost": None,
                "feasible": False,
            }

        route, arrivals = _reconstruct(best_partial_key, parent)
        return {
            "route": route,
            "arrival_times": arrivals,
            "total_cost": best_partial_cost,
            "feasible": False,
            "visited_count": best_count,
        }

    route, arrivals = _reconstruct(best_final_key, parent)
    return {
        "route": route,
        "arrival_times": arrivals,
        "total_cost": best_final_cost,
        "feasible": True,
    }

def _reconstruct(final_key, parent):
    route = []
    arrivals = []
    key = final_key
    while key is not None:
        mask, last, arr_time = key
        route.append(last)
        arrivals.append(arr_time)
        key = parent[key]
    route.reverse()
    arrivals.reverse()
    return route, arrivals

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
            d = ((xi - xj) ** 2 + (yi - yj) ** 2) ** 0.5
            cost_matrix[i][j] = round(d, 2)

    inspection_time = 2.0

    base_order = list(range(n))
    random.shuffle(base_order)

    current_time = 0.0
    time_windows = [None] * n
    prev = base_order[0]
    start0 = random.uniform(0, 10)
    time_windows[prev] = (max(0.0, start0 - 5), start0 + 20)
    current_time = start0 + inspection_time

    for idx in range(1, n):
        node = base_order[idx]
        travel = cost_matrix[prev][node]
        earliest = current_time + travel
        slack_before = random.uniform(0, 10)
        slack_after = random.uniform(20, 60)
        a = max(0.0, earliest - slack_before)
        b = earliest + slack_after
        time_windows[node] = (round(a, 2), round(b, 2))
        current_time = max(earliest, a) + inspection_time
        prev = node

    return cost_matrix, time_windows, inspection_time

def main():
    cost_matrix, time_windows, inspection_time = _generate_random_test_case(15, seed=42)
    start = time.perf_counter()
    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)
    elapsed = time.perf_counter() - start
    print("Time windows:", time_windows)
    print("Result:", result)
    print("Elapsed time: {:.6f} seconds".format(elapsed))

if __name__ == "__main__":
    main()