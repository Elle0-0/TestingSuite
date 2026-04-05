from math import inf

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        return {"feasible": True, "route": [0, 0], "arrival_times": [0, 0], "total_energy": 0}

    if len(time_windows) != n:
        raise ValueError("time_windows must have the same length as cost_matrix")
    if speed <= 0:
        raise ValueError("speed must be positive")
    if inspection_time < 0:
        raise ValueError("inspection_time must be non-negative")

    travel_time = [[cost_matrix[i][j] / speed for j in range(n)] for i in range(n)]

    dp = {}
    parent = {}

    for j in range(1, n):
        earliest, latest = time_windows[j]
        arrival = travel_time[0][j]
        start_service = max(arrival, earliest)
        if start_service <= latest:
            mask = 1 << (j - 1)
            dp[(mask, j)] = {
                "energy": cost_matrix[0][j],
                "depart_time": start_service + inspection_time,
                "arrival": arrival,
            }
            parent[(mask, j)] = (0, 0)

    full_mask = (1 << (n - 1)) - 1

    for mask in range(1, full_mask + 1):
        for j in range(1, n):
            if not (mask & (1 << (j - 1))):
                continue
            state = (mask, j)
            if state not in dp:
                continue

            curr_energy = dp[state]["energy"]
            curr_depart_time = dp[state]["depart_time"]

            for k in range(1, n):
                bit = 1 << (k - 1)
                if mask & bit:
                    continue

                arrival = curr_depart_time + travel_time[j][k]
                earliest, latest = time_windows[k]
                start_service = max(arrival, earliest)

                if start_service > latest:
                    continue

                new_mask = mask | bit
                new_energy = curr_energy + cost_matrix[j][k]
                new_depart_time = start_service + inspection_time
                new_state = (new_mask, k)

                candidate_better = False
                if new_state not in dp:
                    candidate_better = True
                else:
                    best = dp[new_state]
                    if new_energy < best["energy"]:
                        candidate_better = True
                    elif new_energy == best["energy"] and new_depart_time < best["depart_time"]:
                        candidate_better = True

                if candidate_better:
                    dp[new_state] = {
                        "energy": new_energy,
                        "depart_time": new_depart_time,
                        "arrival": arrival,
                    }
                    parent[new_state] = (mask, j)

    best_end = None
    best_total_energy = inf

    for j in range(1, n):
        state = (full_mask, j)
        if state not in dp:
            continue
        total_energy = dp[state]["energy"] + cost_matrix[j][0]
        if total_energy < best_total_energy:
            best_total_energy = total_energy
            best_end = j

    if best_end is None:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    route_backwards = []
    arrival_backwards = []

    mask = full_mask
    j = best_end
    final_station = best_end

    while j != 0:
        state = (mask, j)
        route_backwards.append(j)
        arrival_backwards.append(dp[state]["arrival"])
        mask, j = parent[state]

    route = [0] + list(reversed(route_backwards)) + [0]
    arrival_times = [0] + list(reversed(arrival_backwards))
    return_arrival = dp[(full_mask, final_station)]["depart_time"] + travel_time[final_station][0]
    arrival_times.append(return_arrival)

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
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
        (8, 18),
        (10, 20),
    ]

    inspection_time = 2

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)

    print("Feasible:", result["feasible"])
    print("Route:", result["route"])
    print("Arrival times:", result["arrival_times"])
    print("Total energy:", result["total_energy"])

if __name__ == "__main__":
    main()