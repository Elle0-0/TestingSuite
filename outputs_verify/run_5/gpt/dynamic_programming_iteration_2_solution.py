from functools import lru_cache

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

    if speed <= 0:
        raise ValueError("speed must be positive")

    def travel_time(i: int, j: int) -> int:
        cost = cost_matrix[i][j]
        return (cost + speed - 1) // speed

    full_mask = (1 << (n - 1)) - 1
    INF = float("inf")

    @lru_cache(maxsize=None)
    def dp(mask: int, last: int):
        if mask == (1 << (last - 1)):
            arr = travel_time(0, last)
            earliest, latest = time_windows[last]
            if arr > latest:
                return (INF, INF, None)
            start_service = max(arr, earliest)
            finish = start_service + inspection_time
            return (cost_matrix[0][last], finish, 0)

        best_energy = INF
        best_finish = INF
        best_prev = None

        prev_mask = mask ^ (1 << (last - 1))
        m = prev_mask
        while m:
            bit = m & -m
            prev = bit.bit_length()
            prev_energy, prev_finish, _ = dp(prev_mask, prev)
            if prev_energy != INF:
                arr = prev_finish + travel_time(prev, last)
                earliest, latest = time_windows[last]
                if arr <= latest:
                    start_service = max(arr, earliest)
                    finish = start_service + inspection_time
                    energy = prev_energy + cost_matrix[prev][last]
                    if energy < best_energy or (energy == best_energy and finish < best_finish):
                        best_energy = energy
                        best_finish = finish
                        best_prev = prev
            m -= bit

        return (best_energy, best_finish, best_prev)

    best_total_energy = INF
    best_last = None
    best_finish_time = INF

    mask = full_mask
    for last in range(1, n):
        energy, finish, _ = dp(mask, last)
        if energy == INF:
            continue
        total_energy = energy + cost_matrix[last][0]
        total_finish = finish + travel_time(last, 0)
        if total_energy < best_total_energy or (total_energy == best_total_energy and total_finish < best_finish_time):
            best_total_energy = total_energy
            best_last = last
            best_finish_time = total_finish

    if best_last is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    route_rev = [best_last]
    mask = full_mask
    last = best_last
    while True:
        _, _, prev = dp(mask, last)
        if prev == 0:
            break
        route_rev.append(prev)
        mask ^= (1 << (last - 1))
        last = prev

    route = [0] + route_rev[::-1] + [0]

    arrival_times = [0]
    current_time = 0
    for i in range(1, len(route) - 1):
        u = route[i - 1]
        v = route[i]
        arr = current_time + travel_time(u, v)
        arrival_times.append(arr)
        earliest, _ = time_windows[v]
        current_time = max(arr, earliest) + inspection_time

    arrival_times.append(current_time + travel_time(route[-2], route[-1]))

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
        (3, 10),
        (8, 18),
        (5, 14),
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