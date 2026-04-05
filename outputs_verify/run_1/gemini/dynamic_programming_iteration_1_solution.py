def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    memo = [[-1] * (1 << n) for _ in range(n)]
    parent = [[-1] * (1 << n) for _ in range(n)]

    def solve_tsp(u, mask):
        if mask == (1 << n) - 1:
            return cost_matrix[u][0]

        if memo[u][mask] != -1:
            return memo[u][mask]

        min_cost = float('inf')
        next_station = -1

        for v in range(n):
            if not (mask & (1 << v)):
                new_cost = cost_matrix[u][v] + solve_tsp(v, mask | (1 << v))
                if new_cost < min_cost:
                    min_cost = new_cost
                    next_station = v

        memo[u][mask] = min_cost
        parent[u][mask] = next_station
        return min_cost

    total_energy = solve_tsp(0, 1 << 0)

    route = [0]
    mask = 1 << 0
    current_station = 0
    while len(route) < n:
        next_station = parent[current_station][mask]
        route.append(next_station)
        mask |= (1 << next_station)
        current_station = next_station
    route.append(0)

    return route, int(total_energy)

def main():
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]

    route, total_energy = find_optimal_route(cost_matrix)

    print(route)
    print(total_energy)

if __name__ == "__main__":
    main()