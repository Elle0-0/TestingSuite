def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    
    if n == 1:
        return ([0, 0], 0)
    
    # dp[mask][i] = minimum cost to visit all stations in mask, ending at station i
    # mask is a bitmask of visited stations (excluding station 0 which is always the start)
    # We use stations 1..n-1 as the ones to visit
    
    num_nodes = n - 1  # stations 1 to n-1
    full_mask = (1 << num_nodes) - 1
    
    INF = float('inf')
    
    # dp[mask][i] where i is index in 0..num_nodes-1 representing station i+1
    dp = [[INF] * num_nodes for _ in range(1 << num_nodes)]
    parent = [[-1] * num_nodes for _ in range(1 << num_nodes)]
    
    # Initialize: start from station 0, go to each station i+1
    for i in range(num_nodes):
        mask = 1 << i
        dp[mask][i] = cost_matrix[0][i + 1]
    
    # Fill DP table
    for mask in range(1, 1 << num_nodes):
        for last in range(num_nodes):
            if not (mask & (1 << last)):
                continue
            if dp[mask][last] == INF:
                continue
            # Try to go to next unvisited station
            for next_station in range(num_nodes):
                if mask & (1 << next_station):
                    continue
                new_mask = mask | (1 << next_station)
                new_cost = dp[mask][last] + cost_matrix[last + 1][next_station + 1]
                if new_cost < dp[new_mask][next_station]:
                    dp[new_mask][next_station] = new_cost
                    parent[new_mask][next_station] = last
    
    # Find the minimum cost to complete the tour (return to station 0)
    min_cost = INF
    last_station = -1
    for i in range(num_nodes):
        total = dp[full_mask][i] + cost_matrix[i + 1][0]
        if total < min_cost:
            min_cost = total
            last_station = i
    
    # Reconstruct the route
    route = []
    mask = full_mask
    current = last_station
    while current != -1:
        route.append(current + 1)  # convert back to actual station index
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