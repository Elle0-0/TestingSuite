def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    
    if n == 1:
        return ([0, 0], 0)
    
    if n == 2:
        return ([0, 1, 0], cost_matrix[0][1] + cost_matrix[1][0])
    
    # dp[mask][i] = minimum cost to reach node i having visited the set of nodes represented by mask
    # mask includes node i and node 0
    # Nodes 1..n-1 are the ones we need to visit
    
    INF = float('inf')
    
    # Number of nodes excluding node 0
    num_other = n - 1
    full_mask = (1 << num_other) - 1
    
    # dp[mask][i] where i is 0-indexed among nodes 1..n-1 (so i represents node i+1)
    dp = [[INF] * num_other for _ in range(1 << num_other)]
    parent = [[-1] * num_other for _ in range(1 << num_other)]
    
    # Initialize: start from node 0, go to each node i+1
    for i in range(num_other):
        mask = 1 << i
        dp[mask][i] = cost_matrix[0][i + 1]
    
    # Fill DP table
    for mask in range(1, 1 << num_other):
        for last in range(num_other):
            if not (mask & (1 << last)):
                continue
            if dp[mask][last] == INF:
                continue
            
            for next_node in range(num_other):
                if mask & (1 << next_node):
                    continue
                new_mask = mask | (1 << next_node)
                new_cost = dp[mask][last] + cost_matrix[last + 1][next_node + 1]
                if new_cost < dp[new_mask][next_node]:
                    dp[new_mask][next_node] = new_cost
                    parent[new_mask][next_node] = last
    
    # Find the minimum cost to complete the tour (return to node 0)
    min_cost = INF
    last_node = -1
    for i in range(num_other):
        total = dp[full_mask][i] + cost_matrix[i + 1][0]
        if total < min_cost:
            min_cost = total
            last_node = i
    
    # Reconstruct the path
    route = []
    mask = full_mask
    current = last_node
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