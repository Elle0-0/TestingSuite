from math import inf

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0 or speed <= 0:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }

    if len(time_windows) != n:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }

    def travel_time(i: int, j: int) -> int:
        return (cost_matrix[i][j] + speed - 1) // speed

    full_mask = (1 << (n - 1)) - 1
    dp = {}
    parent = {}

    for j in range(1, n):
        arrival = travel_time(0, j)
        earliest, latest = time_windows[j]
        start_service = max(arrival, earliest)
        if start_service <= latest:
            mask = 1 << (j - 1)
            energy = cost_matrix[0][j]
            key = (mask, j)
            state = (energy, start_service)
            if key not in dp or state < dp[key]:
                dp[key] = state
                parent[key] = (0, 0)

    for mask_size in range(1, n):
        current_keys = [k for k in dp.keys() if bin(k[0]).count("1") == mask_size]
        for mask, last in current_keys:
            energy_so_far, time_so_far = dp[(mask, last)]
            depart_time = time_so_far + inspection_time
            for nxt in range(1, n):
                bit = 1 << (nxt - 1)
                if mask & bit:
                    continue
                arrival = depart_time + travel_time(last, nxt)
                earliest, latest = time_windows[nxt]
                start_service = max(arrival, earliest)
                if start_service > latest:
                    continue
                new_mask = mask | bit
                new_energy = energy_so_far + cost_matrix[last][nxt]
                key = (new_mask, nxt)
                state = (new_energy, start_service)
                if key not in dp or state < dp[key]:
                    dp[key] = state
                    parent[key] = (mask, last)

    best_energy = inf
    best_finish_time = inf
    best_last = None

    for last in range(1, n):
        key = (full_mask, last)
        if key not in dp:
            continue
        energy_so_far, time_so_far = dp[key]
        total_energy = energy_so_far + cost_matrix[last][0]
        finish_time = time_so_far + inspection_time + travel_time(last, 0)
        if (total_energy, finish_time) < (best_energy, best_finish_time):
            best_energy = total_energy
            best_finish_time = finish_time
            best_last = last

    if best_last is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0
        }

    route_reversed = [best_last]
    mask = full_mask
    last = best_last
    while True:
        prev_mask, prev_node = parent[(mask, last)]
        if prev_node == 0 and prev_mask == 0:
            break
        route_reversed.append(prev_node)
        mask, last = prev_mask, prev_node

    route = [0] + list(reversed(route_reversed)) + [0]

    arrival_times = [0]
    current_time = 0
    for idx in range(1, len(route) - 1):
        prev_node = route[idx - 1]
        node = route[idx]
        arrival = current_time + travel_time(prev_node, node)
        earliest, _ = time_windows[node]
        service_start = max(arrival, earliest)
        arrival_times.append(service_start)
        current_time = service_start + inspection_time

    arrival_times.append(current_time + travel_time(route[-2], 0))

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": best_energy
    }

def main():
    cost_matrix = [
        [0, 4, 6, 8],
        [4, 0, 5, 3],
        [6, 5, 0, 4],
        [8, 3, 4, 0]
    ]

    time_windows = [
        (0, 10**9),
        (3, 10),
        (8, 15),
        (12, 20)
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