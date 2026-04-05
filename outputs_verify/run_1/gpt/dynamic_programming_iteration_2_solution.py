from math import inf

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0 or speed <= 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
    if len(time_windows) != n:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        return {"feasible": True, "route": [0, 0], "arrival_times": [0, 0], "total_energy": 0}

    def travel_time(i: int, j: int) -> int:
        return cost_matrix[i][j] / speed

    full_mask = (1 << n) - 1
    dp = {}
    parent = {}

    start_mask = 1
    dp[(start_mask, 0)] = (0, 0)
    parent[(start_mask, 0)] = None

    for mask in range(1 << n):
        if not (mask & 1):
            continue
        for last in range(n):
            state = (mask, last)
            if state not in dp:
                continue
            curr_energy, curr_finish_time = dp[state]

            for nxt in range(1, n):
                if mask & (1 << nxt):
                    continue

                arrival = curr_finish_time + travel_time(last, nxt)
                earliest, latest = time_windows[nxt]
                if arrival > latest:
                    continue

                service_start = max(arrival, earliest)
                finish_time = service_start + inspection_time
                new_mask = mask | (1 << nxt)
                new_energy = curr_energy + cost_matrix[last][nxt]
                new_state = (new_mask, nxt)

                if new_state not in dp:
                    dp[new_state] = (new_energy, finish_time)
                    parent[new_state] = (mask, last, arrival)
                else:
                    best_energy, best_finish = dp[new_state]
                    if new_energy < best_energy or (new_energy == best_energy and finish_time < best_finish):
                        dp[new_state] = (new_energy, finish_time)
                        parent[new_state] = (mask, last, arrival)

    best_end_state = None
    best_total_energy = inf
    best_return_arrival = None

    for last in range(n):
        state = (full_mask, last)
        if state not in dp:
            continue
        curr_energy, curr_finish_time = dp[state]
        return_arrival = curr_finish_time + travel_time(last, 0)
        total_energy = curr_energy + cost_matrix[last][0]
        if total_energy < best_total_energy:
            best_total_energy = total_energy
            best_end_state = state
            best_return_arrival = return_arrival
        elif total_energy == best_total_energy:
            if best_return_arrival is None or return_arrival < best_return_arrival:
                best_end_state = state
                best_return_arrival = return_arrival

    if best_end_state is None:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    route_rev = []
    arrivals_rev = []
    state = best_end_state

    while state is not None:
        mask, last = state
        route_rev.append(last)
        prev = parent[state]
        if prev is None:
            arrivals_rev.append(0)
            break
        prev_mask, prev_last, arrival = prev
        arrivals_rev.append(arrival)
        state = (prev_mask, prev_last)

    route = list(reversed(route_rev))
    arrival_times = list(reversed(arrivals_rev))
    route.append(0)
    arrival_times.append(best_return_arrival)

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": int(best_total_energy),
    }

def main():
    cost_matrix = [
        [0, 4, 8, 6],
        [4, 0, 5, 3],
        [8, 5, 0, 4],
        [6, 3, 4, 0],
    ]

    time_windows = [
        (0, 10**9),
        (3, 12),
        (10, 20),
        (5, 15),
    ]

    inspection_time = 2
    speed = 1

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed)

    print("Feasible:", result["feasible"])
    print("Route:", result["route"])
    print("Arrival times:", result["arrival_times"])
    print("Total energy:", result["total_energy"])

if __name__ == "__main__":
    main()