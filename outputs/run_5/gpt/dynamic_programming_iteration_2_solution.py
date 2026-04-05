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

    full_mask = (1 << (n - 1)) - 1

    def travel_time(i: int, j: int) -> int:
        return cost_matrix[i][j] / speed

    dp = {}
    parent = {}

    for j in range(1, n):
        arrival = travel_time(0, j)
        earliest, latest = time_windows[j]
        if arrival <= latest:
            service_start = max(arrival, earliest)
            finish_time = service_start + inspection_time
            mask = 1 << (j - 1)
            key = (mask, j)
            dp[key] = (cost_matrix[0][j], finish_time, arrival)
            parent[key] = (0, 0)

    for mask in range(1, full_mask + 1):
        for j in range(1, n):
            if not (mask & (1 << (j - 1))):
                continue
            key = (mask, j)
            if key not in dp:
                continue

            current_energy, current_finish, _ = dp[key]

            for k in range(1, n):
                bit = 1 << (k - 1)
                if mask & bit:
                    continue

                arrival = current_finish + travel_time(j, k)
                earliest, latest = time_windows[k]
                if arrival > latest:
                    continue

                service_start = max(arrival, earliest)
                finish_time = service_start + inspection_time
                new_mask = mask | bit
                new_key = (new_mask, k)
                new_energy = current_energy + cost_matrix[j][k]

                if new_key not in dp:
                    dp[new_key] = (new_energy, finish_time, arrival)
                    parent[new_key] = (mask, j)
                else:
                    best_energy, best_finish, _ = dp[new_key]
                    if new_energy < best_energy or (new_energy == best_energy and finish_time < best_finish):
                        dp[new_key] = (new_energy, finish_time, arrival)
                        parent[new_key] = (mask, j)

    best_final = None
    best_total_energy = inf

    for j in range(1, n):
        key = (full_mask, j)
        if key not in dp:
            continue
        energy, finish_time, _ = dp[key]
        total_energy = energy + cost_matrix[j][0]
        if total_energy < best_total_energy:
            best_total_energy = total_energy
            best_final = j

    if best_final is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    route_rev = []
    mask = full_mask
    j = best_final
    while mask != 0:
        route_rev.append(j)
        prev_mask, prev_j = parent[(mask, j)]
        mask, j = prev_mask, prev_j

    route = [0] + list(reversed(route_rev)) + [0]

    arrival_times = [0]
    current_time = 0
    for idx in range(1, len(route) - 1):
        prev_station = route[idx - 1]
        station = route[idx]
        arrival = current_time + travel_time(prev_station, station)
        arrival_times.append(arrival)
        earliest, _ = time_windows[station]
        service_start = max(arrival, earliest)
        current_time = service_start + inspection_time

    arrival_times.append(current_time + travel_time(route[-2], 0))

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": int(best_total_energy),
    }

def main():
    cost_matrix = [
        [0, 4, 6, 8],
        [4, 0, 3, 5],
        [6, 3, 0, 4],
        [8, 5, 4, 0],
    ]

    time_windows = [
        (0, float("inf")),
        (3, 10),
        (8, 16),
        (10, 20),
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