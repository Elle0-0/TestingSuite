import sys

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    num_stations = len(cost_matrix)
    memo = {}
    path_memo = {}
    all_visited_mask = (1 << num_stations) - 1

    def solve_tsp(current_node: int, visited_mask: int) -> int:
        if visited_mask == all_visited_mask:
            return cost_matrix[current_node][0]

        state = (current_node, visited_mask)
        if state in memo:
            return memo[state]

        min_cost = sys.maxsize
        best_next_node = -1

        for next_node in range(num_stations):
            if not (visited_mask & (1 << next_node)):
                new_mask = visited_mask | (1 << next_node)
                cost = cost_matrix[current_node][next_node] + solve_tsp(next_node, new_mask)

                if cost < min_cost:
                    min_cost = cost
                    best_next_node = next_node
        
        memo[state] = min_cost
        path_memo[state] = best_next_node
        return min_cost

    initial_mask = 1 << 0
    total_energy = solve_tsp(0, initial_mask)

    route = [0]
    current_node = 0
    current_mask = initial_mask
    while current_mask != all_visited_mask:
        state = (current_node, current_mask)
        next_node = path_memo[state]
        route.append(next_node)
        current_mask |= (1 << next_node)
        current_node = next_node
    
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

if __name__ == "__main__":
    main()