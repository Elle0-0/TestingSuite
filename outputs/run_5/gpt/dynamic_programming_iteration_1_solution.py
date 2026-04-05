from typing import List, Tuple, Dict

def find_optimal_route(cost_matrix: List[List[int]]) -> Tuple[List[int], int]:
    n = len(cost_matrix)
    if n == 0:
        return ([], 0)
    if n == 1:
        return ([0, 0], 0)

    dp: Dict[Tuple[int, int], int] = {}
    parent: Dict[Tuple[int, int], int] = {}

    for j in range(1, n):
        mask = 1 << (j - 1)
        dp[(mask, j)] = cost_matrix[0][j]
        parent[(mask, j)] = 0

    full_mask = (1 << (n - 1)) - 1

    for mask in range(1, full_mask + 1):
        for j in range(1, n):
            if not (mask & (1 << (j - 1))):
                continue
            if mask == (1 << (j - 1)):
                continue

            prev_mask = mask ^ (1 << (j - 1))
            best_cost = float("inf")
            best_prev = -1

            for k in range(1, n):
                if not (prev_mask & (1 << (k - 1))):
                    continue
                candidate = dp[(prev_mask, k)] + cost_matrix[k][j]
                if candidate < best_cost:
                    best_cost = candidate
                    best_prev = k

            dp[(mask, j)] = best_cost
            parent[(mask, j)] = best_prev

    best_total = float("inf")
    last_city = -1

    for j in range(1, n):
        total = dp[(full_mask, j)] + cost_matrix[j][0]
        if total < best_total:
            best_total = total
            last_city = j

    route_reversed = [0]
    mask = full_mask
    city = last_city

    while city != 0:
        route_reversed.append(city)
        prev_city = parent[(mask, city)]
        mask ^= 1 << (city - 1)
        city = prev_city

    route = list(reversed(route_reversed))
    route.append(0)

    return (route, int(best_total))

def main() -> None:
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]

    route, total_energy = find_optimal_route(cost_matrix)
    print("Optimal route:", route)
    print("Total energy:", total_energy)

if __name__ == "__main__":
    main()