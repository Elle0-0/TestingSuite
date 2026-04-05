import sys

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    if n == 0:
        return [], 0
    if n == 1:
        return [0, 0], 0

    memo = {}
    path_memo = {}
    
    # Set a higher recursion limit for larger N, although not strictly necessary for N=4
    # This is a good practice for recursive DP solutions.
    required_recursion_limit = n * n * (1 << n)
    if sys.getrecursionlimit() < required_recursion_limit:
        sys.setrecursionlimit(required_recursion_limit)

    def solve(mask: int, pos: int) -> int:
        if mask == (1 << n) - 1:
            return cost_matrix[pos][0]

        if (mask, pos) in memo:
            return memo[(mask, pos)]

        min_cost = float('inf')
        best_next_city = -1

        for next_city in range(n):
            if not ((mask >> next_city) & 1):
                cost = cost_matrix[pos][next_city] + solve(mask | (1 << next_city), next_city)
                if cost < min_cost:
                    min_cost = cost
                    best_next_city = next_city
        
        memo[(mask, pos)] = min_cost
        path_memo[(mask, pos)] = best_next_city
        return min_cost

    total_energy = solve(1 << 0, 0)

    route = [0]
    mask = 1 << 0
    current_pos = 0
    while mask != (1 << n) - 1:
        next_city = path_memo.get((mask, current_pos))
        if next_city is None:
            # Should not happen in a fully connected graph
            return [], -1
        route.append(next_city)
        mask |= (1 << next_city)
        current_pos = next_city
    
    route.append(0)

    return route, total_energy

def main():
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]

    optimal_route, total_energy = find_optimal_route(cost_matrix)
    
    print(f"Optimal route: {optimal_route}")
    print(f"Total energy: {total_energy}")

main()