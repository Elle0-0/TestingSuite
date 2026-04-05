import sys

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    memo = {}
    path_memo = {}
    all_visited = (1 << n) - 1

    def solve(current_station: int, visited_mask: int) -> int:
        if visited_mask == all_visited:
            return cost_matrix[current_station][0]

        state = (current_station, visited_mask)
        if state in memo:
            return memo[state]

        min_cost = sys.maxsize
        best_next_station = -1

        for next_station in range(n):
            if not (visited_mask & (1 << next_station)):
                new_cost = cost_matrix[current_station][next_station] + solve(
                    next_station, visited_mask | (1 << next_station)
                )

                if new_cost < min_cost:
                    min_cost = new_cost
                    best_next_station = next_station
        
        memo[state] = min_cost
        path_memo[state] = best_next_station
        
        return min_cost

    total_energy = solve(0, 1)

    route = [0]
    current_station = 0
    visited_mask = 1
    
    while len(route) < n:
        next_station = path_memo[(current_station, visited_mask)]
        route.append(next_station)
        visited_mask |= (1 << next_station)
        current_station = next_station
        
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