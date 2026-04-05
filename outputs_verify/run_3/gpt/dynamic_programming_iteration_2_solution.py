from functools import lru_cache

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0 or speed <= 0:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    if len(time_windows) != n:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    all_visited_mask = (1 << n) - 1

    def travel_time(i: int, j: int) -> int:
        dist = cost_matrix[i][j]
        return (dist + speed - 1) // speed

    @lru_cache(maxsize=None)
    def dp(mask: int, current: int):
        if mask == all_visited_mask:
            end_time = 0
            energy = cost_matrix[current][0]
            back_arrival = end_time + travel_time(current, 0)
            return energy, (0,), (back_arrival,)

        best = None

        for nxt in range(1, n):
            if mask & (1 << nxt):
                continue

            sub = dp(mask | (1 << nxt), nxt)
            if sub is None:
                continue

            suffix_energy, suffix_route, suffix_arrivals = sub
            next_station_arrival = suffix_arrivals[0]
            latest_start_allowed = time_windows[nxt][1]

            latest_departure = next_station_arrival - inspection_time
            latest_arrival_from_current = latest_departure
            latest_depart_from_current = latest_arrival_from_current - travel_time(current, nxt)

            if latest_depart_from_current < 0:
                continue

            arrival_at_nxt = latest_arrival_from_current
            if arrival_at_nxt > latest_start_allowed:
                continue

            start_service_at_nxt = max(arrival_at_nxt, time_windows[nxt][0])
            if start_service_at_nxt > time_windows[nxt][1]:
                continue

            energy = cost_matrix[current][nxt] + suffix_energy
            route = (nxt,) + suffix_route
            arrivals = (arrival_at_nxt,) + suffix_arrivals

            candidate = (energy, route, arrivals)
            if best is None or candidate[0] < best[0]:
                best = candidate

        return best

    result = dp(1, 0)
    if result is None:
        return {
            "feasible": False,
            "route": [],
            "arrival_times": [],
            "total_energy": 0,
        }

    total_energy, suffix_route, suffix_arrivals = result
    route = [0] + list(suffix_route)
    arrival_times = [0] + list(suffix_arrivals)

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
        [6, 5, 0, 4],
        [8, 3, 4, 0],
    ]

    time_windows = [
        (0, 10**9),
        (3, 10),
        (10, 20),
        (16, 30),
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