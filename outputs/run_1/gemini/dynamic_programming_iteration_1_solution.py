import sys

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    memo = [[-1] * n for _ in range(1 << n)]
    path = [[-1] * n for _ in range(1 << n)]
    
    def solve(mask, pos):
        if mask == (1 << n) - 1:
            return cost_matrix[pos][0] if cost_matrix[pos][0] > 0 else float('inf')

        if memo[mask][pos] != -1:
            return memo[mask][pos]

        min_cost = float('inf')
        best_next_node = -1

        for next_node in range(n):
            if not (mask & (1 << next_node)):
                current_cost = cost_matrix[pos][next_node] + solve(mask | (1 << next_node), next_node)
                if current_cost < min_cost:
                    min_cost = current_cost
                    best_next_node = next_node
        
        memo[mask][pos] = min_cost
        path[mask][pos] = best_next_node
        return min_cost

    total_energy = solve(1, 0)

    route = [0]
    current_mask = 1
    current_pos = 0
    while len(route) < n:
        next_node = path[current_mask][current_pos]
        route.append(next_node)
        current_mask |= (1 << next_node)
        current_pos = next_node
    
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
    print(f"Optimal route: {route}")
    print(f"Total energy: {total_energy}")

if __name__ == "__main__":
    main()