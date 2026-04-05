def find_optimal_route(cost_matrix: list[list[int]]) -> tuple[list[int], int]:
    n = len(cost_matrix)
    if n == 0:
        return [], 0
    if n == 1:
        return [0, 0], 0

    dp = [[float('inf')] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]

    dp[1][0] = 0

    for mask in range(1, 1 << n):
        for i in range(n):
            if (mask >> i) & 1:
                prev_mask = mask ^ (1 << i)
                if prev_mask == 0:
                    continue
                
                for j in range(n):
                    if (prev_mask >> j) & 1:
                        cost = dp[prev_mask][j] + cost_matrix[j][i]
                        if cost < dp[mask][i]:
                            dp[mask][i] = cost
                            parent[mask][i] = j
                            
    final_mask = (1 << n) - 1
    min_total_energy = float('inf')
    last_station = -1

    for i in range(1, n):
        total_energy = dp[final_mask][i] + cost_matrix[i][0]
        if total_energy < min_total_energy:
            min_total_energy = total_energy
            last_station = i

    if last_station == -1:
        return [0], 0

    route = []
    current_station = last_station
    current_mask = final_mask

    while current_station != 0:
        route.append(current_station)
        prev_station = parent[current_mask][current_station]
        current_mask ^= (1 << current_station)
        current_station = prev_station
        
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

    optimal_route, total_energy = find_optimal_route(cost_matrix)
    print("Optimal route:", optimal_route)
    print("Total energy:", total_energy)


if __name__ == "__main__":
    main()