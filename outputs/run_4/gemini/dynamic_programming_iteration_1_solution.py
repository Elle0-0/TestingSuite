import sys

def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    if n == 0:
        return [], 0
    if n == 1:
        return [0, 0], 0

    memo = [[-1] * (1 << n) for _ in range(n)]

    def solve(i, mask):
        if memo[i][mask] != -1:
            return memo[i][mask]

        if mask == (1 << i) | 1:
            memo[i][mask] = cost_matrix[0][i]
            return memo[i][mask]

        res = float('inf')
        prev_mask = mask & ~(1 << i)
        
        for j in range(1, n):
            if (prev_mask >> j) & 1:
                res = min(res, solve(j, prev_mask) + cost_matrix[j][i])
        
        memo[i][mask] = res
        return res

    final_mask = (1 << n) - 1
    min_tour_cost = float('inf')

    for i in range(1, n):
        cost = solve(i, final_mask) + cost_matrix[i][0]
        min_tour_cost = min(min_tour_cost, cost)

    route = [0]
    last_index = -1
    
    for i in range(1, n):
        cost = solve(i, final_mask) + cost_matrix[i][0]
        if abs(cost - min_tour_cost) < 1e-9:
            last_index = i
            break
            
    current_mask = final_mask
    current_index = last_index
    
    path_reconstruction = []
    
    while current_index != 0 and current_index != -1:
        path_reconstruction.append(current_index)
        prev_mask = current_mask & ~(1 << current_index)
        
        next_index = -1
        
        for j in range(1, n):
            if (prev_mask >> j) & 1:
                val = solve(j, prev_mask) + cost_matrix[j][current_index]
                if abs(val - memo[current_index][current_mask]) < 1e-9:
                    next_index = j
                    break

        if next_index == -1:
             if abs(cost_matrix[0][current_index] - memo[current_index][current_mask]) < 1e-9:
                 next_index = 0
        
        current_index = next_index
        current_mask = prev_mask

    route.extend(reversed(path_reconstruction))
    route.append(0)

    return route, int(min_tour_cost)

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