from functools import lru_cache

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)

    if n == 0 or len(time_windows) != n or speed <= 0 or inspection_time < 0:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    for row in cost_matrix:
        if len(row) != n:
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

    def travel_time(i: int, j: int) -> float:
        energy = cost_matrix[i][j]
        if energy < 0:
            return float("inf")
        return energy / speed

    all_mask = (1 << (n - 1)) - 1

    @lru_cache(maxsize=None)
    def dp(mask: int, last: int):
        if mask == all_mask:
            back_time = travel_time(last, 0)
            back_energy = cost_matrix[last][0]
            if back_time == float("inf") or back_energy < 0:
                return None
            return (back_energy, [(0, back_time, back_time)])

        best = None

        for nxt in range(1, n):
            bit = 1 << (nxt - 1)
            if mask & bit:
                continue

            move_time = travel_time(last, nxt)
            move_energy = cost_matrix[last][nxt]
            if move_time == float("inf") or move_energy < 0:
                continue

            sub = dp(mask | bit, nxt)
            if sub is None:
                continue

            sub_energy, sub_path = sub

            first_arrival_from_nxt = sub_path[0][1]
            latest_allowed = time_windows[nxt][1]

            latest_feasible_arrival_at_nxt = min(
                latest_allowed,
                first_arrival_from_nxt - inspection_time
            )

            tw_start = time_windows[nxt][0]
            arrival_at_nxt = max(move_time, tw_start)

            if arrival_at_nxt > latest_feasible_arrival_at_nxt:
                continue

            shifted_path = []
            depart_nxt = arrival_at_nxt + inspection_time
            for station, rel_arrival, rel_finish in sub_path:
                shifted_path.append((station, depart_nxt + rel_arrival, depart_nxt + rel_finish))

            total_energy = move_energy + sub_energy
            candidate = (total_energy, [(nxt, arrival_at_nxt, depart_nxt)] + shifted_path)

            if best is None or total_energy < best[0]:
                best = candidate

        return best

    result = dp(0, 0)
    if result is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    total_energy, path = result
    route = [0]
    arrival_times = [0]

    for station, arrival, _ in path:
        route.append(station)
        arrival_times.append(arrival)

    feasible = route[0] == 0 and route[-1] == 0 and len(route) == n + 1

    if not feasible:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    return {
        "feasible": True,
        "route": route,
        "arrival_times": arrival_times,
        "total_energy": total_energy,
    }

def main():
    cost_matrix = [
        [0, 4, 6, 8],
        [4, 0, 5, 3],
        [6, 5, 0, 7],
        [8, 3, 7, 0],
    ]

    time_windows = [
        (0, 10**9),
        (3, 12),
        (8, 20),
        (10, 18),
    ]

    inspection_time = 2

    result = find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1)

    print("Feasible:", result["feasible"])
    print("Route:", result["route"])
    print("Arrival times:", result["arrival_times"])
    print("Total energy:", result["total_energy"])

if __name__ == "__main__":
    main()