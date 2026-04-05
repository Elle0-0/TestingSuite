def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    
    if n == 1:
        return ([0, 0], 0)
    
    # dp[mask][i] = minimum cost to reach node i having visited the set of nodes represented by mask
    # mask includes node 0 always, and node i
    # We start at node 0
    
    INF = float('inf')
    
    # Number of nodes excluding the starting node 0
    # We'll use bitmask over all n nodes
    
    # dp[mask][i] = min cost to arrive at node i, having visited exactly the nodes in mask
    # mask always includes node 0 and node i
    
    full_mask = (1 << n) - 1
    
    dp = [[INF] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    
    # Start at node 0
    dp[1 << 0][0] = 0
    
    for mask in range(1 << n):
        for u in range(n):
            if dp[mask][u] == INF:
                continue
            if not (mask & (1 << u)):
                continue
            # Try to go to node v not yet visited
            for v in range(n):
                if mask & (1 << v):
                    continue
                new_mask = mask | (1 << v)
                new_cost = dp[mask][u] + cost_matrix[u][v]
                if new_cost < dp[new_mask][v]:
                    dp[new_mask][v] = new_cost
                    parent[new_mask][v] = u
    
    # Find the minimum cost to complete the tour: visit all nodes and return to 0
    min_cost = INF
    last_node = -1
    
    for u in range(1, n):
        total = dp[full_mask][u] + cost_matrix[u][0]
        if total < min_cost:
            min_cost = total
            last_node = u
    
    # Reconstruct the path
    route = []
    mask = full_mask
    current = last_node
    
    while current != -1:
        route.append(current)
        prev = parent[mask][current]
        mask = mask ^ (1 << current)
        current = prev
    
    route.reverse()
    route.append(0)  # Return to base
    
    return (route, min_cost)


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