def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    
    if n == 1:
        return ([0, 0], 0)
    
    # dp[mask][i] = minimum cost to reach node i having visited the set of nodes represented by mask
    # mask includes node 0 always, and node i
    # We start at node 0
    
    INF = float('inf')
    
    # Number of nodes excluding node 0
    # We'll represent the set of visited nodes (excluding 0) as a bitmask of n-1 bits
    # Bit j corresponds to node j+1
    
    num_nodes = n - 1
    full_mask = (1 << num_nodes) - 1
    
    # dp[mask][i] where i is in range(num_nodes), representing node i+1
    # mask is a bitmask of which of nodes 1..n-1 have been visited
    dp = [[INF] * num_nodes for _ in range(1 << num_nodes)]
    parent = [[-1] * num_nodes for _ in range(1 << num_nodes)]
    
    # Initialize: starting from node 0, go to each node i+1
    for i in range(num_nodes):
        mask = 1 << i
        dp[mask][i] = cost_matrix[0][i + 1]
    
    # Fill DP
    for mask in range(1, 1 << num_nodes):
        for last in range(num_nodes):
            if not (mask & (1 << last)):
                continue
            if dp[mask][last] == INF:
                continue
            # Try to go to next unvisited node
            for nxt in range(num_nodes):
                if mask & (1 << nxt):
                    continue
                new_mask = mask | (1 << nxt)
                new_cost = dp[mask][last] + cost_matrix[last + 1][nxt + 1]
                if new_cost < dp[new_mask][nxt]:
                    dp[new_mask][nxt] = new_cost
                    parent[new_mask][nxt] = last
    
    # Find the minimum cost to complete the tour (return to node 0)
    min_cost = INF
    best_last = -1
    for last in range(num_nodes):
        total = dp[full_mask][last] + cost_matrix[last + 1][0]
        if total < min_cost:
            min_cost = total
            best_last = last
    
    # Reconstruct the route
    route = []
    mask = full_mask
    current = best_last
    while current != -1:
        route.append(current + 1)  # Convert back to actual node index
        prev = parent[mask][current]
        mask = mask ^ (1 << current)
        current = prev
    
    route.reverse()
    route = [0] + route + [0]
    
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