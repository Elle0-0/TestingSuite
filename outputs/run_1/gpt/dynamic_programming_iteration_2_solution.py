from math import inf

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }
    if n == 1:
        return {
            "feasible": True,
            "route": [0, 0],
            "arrival_times": [0, 0],
            "total_energy": 0,
        }

    if len(time_windows) != n:
        raise ValueError("time_windows must have the same length as cost_matrix")

    full_mask = (1 << (n - 1)) - 1

    dp = {}
    parent = {}

    for j in range(1, n):
        travel_time = cost_matrix[0][j] / speed
        arrival = travel_time
        earliest, latest = time_windows[j]
        if arrival <= latest:
            actual_arrival = max(arrival, earliest)
            finish_time = actual_arrival + inspection_time
            mask = 1 << (j - 1)
            dp[(mask, j)] = (cost_matrix[0][j], finish_time, actual_arrival)
            parent[(mask, j)] = (0, 0)

    for mask in range(1, full_mask + 1):
        for j in range(1, n):
            if not (mask & (1 << (j - 1))):
                continue
            state = (mask, j)
            if state not in dp:
                continue

            curr_energy, curr_finish_time, _ = dp[state]

            for k in range(1, n):
                bit = 1 << (k - 1)
                if mask & bit:
                    continue

                travel_time = cost_matrix[j][k] / speed
                arrival = curr_finish_time + travel_time
                earliest, latest = time_windows[k]

                if arrival > latest:
                    continue

                actual_arrival = max(arrival, earliest)
                finish_time = actual_arrival + inspection_time
                new_mask = mask | bit
                new_energy = curr_energy + cost_matrix[j][k]
                new_state = (new_mask, k)

                if new_state not in dp:
                    dp[new_state] = (new_energy, finish_time, actual_arrival)
                    parent[new_state] = (mask, j)
                else:
                    best_energy, best_finish_time, _ = dp[new_state]
                    if new_energy < best_energy or (new_energy == best_energy and finish_time < best_finish_time):
                        dp[new_state] = (new_energy, finish_time, actual_arrival)
                        parent[new_state] = (mask, j)

    best_final = None
    best_total_energy = inf
    best_return_arrival = None
    best_last = None

    for j in range(1, n):
        state = (full_mask, j)
        if state not in dp:
            continue
        energy_so_far, finish_time, _ = dp[state]
        return_travel_time = cost_matrix[j][0] / speed
        return_arrival = finish_time + return_travel_time
        total_energy = energy_so_far + cost_matrix[j][0]

        if total_energy < best_total_energy or (total_energy == best_total_energy and return_arrival < best_return_arrival):
            best_total_energy = total_energy
            best_return_arrival = return_arrival
            best_final = state
            best_last = j

    if best_final is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    route_reversed = []
    arrival_reversed = []
    state = best_final

    while state in dp:
        mask, j = state
        _, _, arrival_at_j = dp[state]
        route_reversed.append(j)
        arrival_reversed.append(arrival_at_j)
        prev = parent[state]
        if prev == (0, 0):
            break
        state = prev

    route = [0] + list(reversed(route_reversed)) + [0]
    arrivals = [0] + list(reversed(arrival_reversed)) + [best_return_arrival]

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrivals,
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
        (3, 12),
        (8, 20),
        (10, 18),
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