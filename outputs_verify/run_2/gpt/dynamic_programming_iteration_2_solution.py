from functools import lru_cache

def find_optimal_route(cost_matrix: list[list[int]], time_windows: list[tuple[int, int]], inspection_time: int, speed: int = 1) -> dict:
    n = len(cost_matrix)
    if n == 0:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}
    if n == 1:
        return {"feasible": True, "route": [0, 0], "arrival_times": [0, 0], "total_energy": 0}

    if len(time_windows) != n:
        raise ValueError("time_windows must have the same length as cost_matrix")

    for i in range(1, n):
        if not isinstance(time_windows[i], tuple) or len(time_windows[i]) != 2:
            raise ValueError("Each time window must be a tuple (earliest, latest)")
        if time_windows[i][0] > time_windows[i][1]:
            raise ValueError("Invalid time window: earliest > latest")

    def travel_time(i: int, j: int) -> int:
        if speed <= 0:
            raise ValueError("speed must be positive")
        cost = cost_matrix[i][j]
        return (cost + speed - 1) // speed

    full_mask = (1 << (n - 1)) - 1

    @lru_cache(maxsize=None)
    def dp(mask: int, last: int):
        if mask == 0:
            return (0, 0, [0], [0])

        best = None

        if last == 0:
            candidates = []
            m = mask
            bit = 0
            while m:
                if m & 1:
                    candidates.append(bit + 1)
                m >>= 1
                bit += 1
        else:
            if not (mask & (1 << (last - 1))):
                return None
            candidates = [last]

        for station in candidates:
            prev_mask = mask & ~(1 << (station - 1))
            if prev_mask == 0:
                prev_energy = 0
                prev_finish_time = 0
                prev_route = [0]
                prev_arrivals = [0]
                prev_last = 0

                arrival = prev_finish_time + travel_time(prev_last, station)
                earliest, latest = time_windows[station]
                if arrival > latest:
                    continue
                service_start = max(arrival, earliest)
                finish_time = service_start + inspection_time
                total_energy = prev_energy + cost_matrix[prev_last][station]
                route = prev_route + [station]
                arrivals = prev_arrivals + [arrival]

                candidate = (total_energy, finish_time, route, arrivals)
            else:
                prev_best = None
                m2 = prev_mask
                bit2 = 0
                while m2:
                    if m2 & 1:
                        prev_station = bit2 + 1
                        res = dp(prev_mask, prev_station)
                        if res is not None:
                            prev_energy, prev_finish_time, prev_route, prev_arrivals = res
                            arrival = prev_finish_time + travel_time(prev_station, station)
                            earliest, latest = time_windows[station]
                            if arrival <= latest:
                                service_start = max(arrival, earliest)
                                finish_time = service_start + inspection_time
                                total_energy = prev_energy + cost_matrix[prev_station][station]
                                route = prev_route + [station]
                                arrivals = prev_arrivals + [arrival]
                                cand = (total_energy, finish_time, route, arrivals)
                                if prev_best is None or cand[0] < prev_best[0] or (cand[0] == prev_best[0] and cand[1] < prev_best[1]):
                                    prev_best = cand
                    m2 >>= 1
                    bit2 += 1
                candidate = prev_best

            if candidate is not None:
                if best is None or candidate[0] < best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                    best = candidate

        return best

    best_overall = None
    m = full_mask
    bit = 0
    while m:
        if m & 1:
            last = bit + 1
            res = dp(full_mask, last)
            if res is not None:
                energy_so_far, finish_time, route, arrivals = res
                arrival_back = finish_time + travel_time(last, 0)
                total_energy = energy_so_far + cost_matrix[last][0]
                final_route = route + [0]
                final_arrivals = arrivals + [arrival_back]
                cand = (total_energy, arrival_back, final_route, final_arrivals)
                if best_overall is None or cand[0] < best_overall[0] or (cand[0] == best_overall[0] and cand[1] < best_overall[1]):
                    best_overall = cand
        m >>= 1
        bit += 1

    if best_overall is None:
        return {"feasible": False, "route": [], "arrival_times": [], "total_energy": 0}

    return {
        "feasible": True,
        "route": best_overall[2],
        "arrival_times": best_overall[3],
        "total_energy": best_overall[0],
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
        (3, 12),
        (10, 20),
        (8, 18),
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