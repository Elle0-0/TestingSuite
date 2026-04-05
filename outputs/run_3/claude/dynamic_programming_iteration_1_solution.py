def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    
    if n == 1:
        return ([0, 0], 0)
    
    # dp[mask][i] = minimum cost to reach node i having visited the set of nodes represented by mask
    # mask includes node 0 and node i at minimum
    # We start at node 0, so initial state: mask = 1 (only node 0 visited), current node = 0
    
    INF = float('inf')
    full_mask = (1 << n) - 1
    
    # dp[mask][i] = min energy to have visited exactly the nodes in mask, ending at node i
    dp = [[INF] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    
    dp[1][0] = 0  # Start at node 0, only node 0 visited
    
    for mask in range(1 << n):
        for u in range(n):
            if dp[mask][u] == INF:
                continue
            if not (mask & (1 << u)):
                continue
            # Try to go to each unvisited node
            for v in range(n):
                if mask & (1 << v):
                    continue  # already visited
                new_mask = mask | (1 << v)
                new_cost = dp[mask][u] + cost_matrix[u][v]
                if new_cost < dp[new_mask][v]:
                    dp[new_mask][v] = new_cost
                    parent[new_mask][v] = u
    
    # Find the minimum cost to complete the tour: visit all nodes and return to 0
    min_energy = INF
    last_node = -1
    for u in range(1, n):
        total = dp[full_mask][u] + cost_matrix[u][0]
        if total < min_energy:
            min_energy = total
            last_node = u
    
    # Reconstruct the route
    route = []
    mask = full_mask
    current = last_node
    while current != -1:
        route.append(current)
        prev = parent[mask][current]
        mask = mask ^ (1 << current)
        current = prev
    
    # route is in reverse order (ends with 0 at the beginning after reversal)
    # Actually, the loop ends when current = -1, and the last appended should be 0
    # Let's check: when current=0, parent[1][0] = -1, so 0 gets appended and then loop ends
    
    route.reverse()
    route.append(0)  # Return to base
    
    return (route, min_energy)


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