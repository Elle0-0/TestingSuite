import math

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    if n <= 1:
        return ([0, 0] if n == 1 else []), 0

    dp = [[math.inf] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]

    dp[1][0] = 0

    for mask in range(1, 1 << n):
        for u in range(n):
            if (mask >> u) & 1:
                prev_mask = mask ^ (1 << u)
                if prev_mask == 0:
                    continue
                
                for v in range(n):
                    if (prev_mask >> v) & 1:
                        if dp[prev_mask][v] != math.inf:
                            new_cost = dp[prev_mask][v] + cost_matrix[v][u]
                            if new_cost < dp[mask][u]:
                                dp[mask][u] = new_cost
                                parent[mask][u] = v

    final_mask = (1 << n) - 1
    min_total_energy = math.inf
    last_city = -1

    for u in range(1, n):
        if dp[final_mask][u] != math.inf:
            total_cost = dp[final_mask][u] + cost_matrix[u][0]
            if total_cost < min_total_energy:
                min_total_energy = total_cost
                last_city = u
    
    if last_city == -1:
        if n > 1: # For simple cases like n=2
             min_total_energy = dp[final_mask][n-1] + cost_matrix[n-1][0]
             last_city = n-1
        else: # Should not be reachable due to initial checks
            return ([], 0)

    route = []
    current_mask = final_mask
    current_city = last_city

    while current_city != 0:
        route.append(current_city)
        prev_city = parent[current_mask][current_city]
        current_mask ^= (1 << current_city)
        current_city = prev_city

    route.append(0)
    route.reverse()
    route.append(0)

    return route, int(min_total_energy)

def main():
    cost_matrix = [
        [0, 10, 15, 20],
        [10, 0, 35, 25],
        [15, 35, 0, 30],
        [20, 25, 30, 0]
    ]

    optimal_path, total_cost = find_optimal_route(cost_matrix)
    print("Optimal route:", optimal_path)
    print("Total energy:", total_cost)

main()