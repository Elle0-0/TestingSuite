from functools import lru_cache

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    if n == 0:
        return ([], 0)
    if n == 1:
        return ([0, 0], 0)

    @lru_cache(maxsize=None)
    def dp(pos: int, mask: int) -> int:
        if mask == (1 << n) - 1:
            return cost_matrix[pos][0]
        best = float('inf')
        for nxt in range(n):
            if not (mask & (1 << nxt)):
                best = min(best, cost_matrix[pos][nxt] + dp(nxt, mask | (1 << nxt)))
        return best

    route = [0]
    pos = 0
    mask = 1
    total_energy = dp(0, 1)

    while mask != (1 << n) - 1:
        best_nxt = None
        best_cost = float('inf')
        for nxt in range(n):
            if not (mask & (1 << nxt)):
                current_cost = cost_matrix[pos][nxt] + dp(nxt, mask | (1 << nxt))
                if current_cost < best_cost:
                    best_cost = current_cost
                    best_nxt = nxt
        route.append(best_nxt)
        pos = best_nxt
        mask |= 1 << best_nxt

    route.append(0)
    return route, total_energy

def main():
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