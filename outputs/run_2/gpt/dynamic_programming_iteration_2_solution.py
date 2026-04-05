from math import inf

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        return {"feasible": True, "route": [0, 0], "arrival_times": [0, 0], "total_energy": 0}
    if len(time_windows) != n:
        raise ValueError("time_windows must have the same length as cost_matrix")

    travel_time = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]

    dp = {}
    parent = {}

    for j in range(1, n):
        earliest, latest = time_windows[j]
        arrival = travel_time[0][j]
        start_service = max(arrival, earliest)
        if start_service <= latest:
            mask = 1 << (j - 1)
            dp[(mask, j)] = (cost_matrix[0][j], arrival, start_service + inspection_time)
            parent[(mask, j)] = None

    full_mask = (1 << (n - 1)) - 1

    for mask in range(1, full_mask + 1):
        for last in range(1, n):
            state = (mask, last)
            if state not in dp:
                continue
            energy_so_far, _, depart_time = dp[state]

            for nxt in range(1, n):
                bit = 1 << (nxt - 1)
                if mask & bit:
                    continue

                arrival = depart_time + travel_time[last][nxt]
                earliest, latest = time_windows[nxt]
                start_service = max(arrival, earliest)
                if start_service > latest:
                    continue

                new_mask = mask | bit
                new_energy = energy_so_far + cost_matrix[last][nxt]
                new_state = (new_mask, nxt)
                candidate = (new_energy, arrival, start_service + inspection_time)

                if new_state not in dp:
                    dp[new_state] = candidate
                    parent[new_state] = state
                else:
                    best_energy, best_arrival, best_depart = dp[new_state]
                    if new_energy < best_energy or (
                        new_energy == best_energy and candidate[2] < best_depart
                    ):
                        dp[new_state] = candidate
                        parent[new_state] = state

    best_final = None
    best_total_energy = inf

    for last in range(1, n):
        state = (full_mask, last)
        if state not in dp:
            continue
        energy_so_far, _, depart_time = dp[state]
        return_arrival = depart_time + travel_time[last][0]
        total_energy = energy_so_far + cost_matrix[last][0]
        if total_energy < best_total_energy:
            best_total_energy = total_energy
            best_final = (state, return_arrival)

    if best_final is None:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    state, base_arrival = best_final
    reversed_route = []
    while state is not None:
        mask, last = state
        reversed_route.append(last)
        state = parent[state]

    route = [0] + list(reversed(reversed_route)) + [0]

    arrival_times = [0]
    current_time = 0.0
    for i in range(1, len(route)):
        prev_node = route[i - 1]
        node = route[i]
        current_time += travel_time[prev_node][node]
        arrival_times.append(current_time)
        if node != 0:
            earliest, _ = time_windows[node]
            current_time = max(current_time, earliest) + inspection_time

    normalized_arrivals = []
    for t in arrival_times:
        if abs(t - round(t)) < 1e-9:
            normalized_arrivals.append(int(round(t)))
        else:
            normalized_arrivals.append(t)

    return {
        "feasible": True,
        "route": route,
        "arrival_times": normalized_arrivals,
        "total_energy": int(best_total_energy),
    }

def main():
    cost_matrix = [
        [0, 4, 6, 8],
        [4, 0, 5, 3],
        [6, 5, 0, 4],
        [8, 3, 4, 0],
    ]

    time_windows = [
        (0, float("inf")),
        (3, 10),
        (8, 16),
        (7, 14),
    ]

    inspection_time = 2

    result = find_optimal_route(cost_matrix, time_windows, inspection_time)

    print("Feasible:", result["feasible"])
    print("Route:", result["route"])
    print("Arrival times:", result["arrival_times"])
    print("Total energy:", result["total_energy"])

if __name__ == "__main__":
    main()