import random
import time
import sys

def find_optimal_route(cost_matrix, time_windows, inspection_time, speed=1):
    n = len(cost_matrix)
    if n == 0:
        return {'status': 'infeasible', 'cost': None, 'path': None}
    if n == 1:
        return {'status': 'success', 'cost': 0, 'path': [0, 0]}

    all_visited_mask = (1 << n) - 1
    
    memo = [[(float('inf'), float('inf')) for _ in range(n)] for _ in range(1 << n)]
    parent = [[-1 for _ in range(n)] for _ in range(1 << n)]

    start_time_at_depot = time_windows[0][0]
    memo[1][0] = (0, start_time_at_depot)

    for mask in range(1, 1 << n):
        for u in range(n):
            if (mask >> u) & 1:
                if mask == (1 << u):
                    if u != 0: continue
                
                prev_mask = mask ^ (1 << u)
                if prev_mask == 0:
                    continue

                for v in range(n):
                    if (prev_mask >> v) & 1:
                        prev_cost, prev_time = memo[prev_mask][v]
                        if prev_cost == float('inf'):
                            continue

                        travel_time = cost_matrix[v][u] / speed
                        arrival_time_at_u = prev_time + inspection_time[v] + travel_time
                        
                        start_service_at_u = max(arrival_time_at_u, time_windows[u][0])

                        if start_service_at_u > time_windows[u][1]:
                            continue
                        
                        new_cost = prev_cost + cost_matrix[v][u]

                        if new_cost < memo[mask][u][0]:
                            memo[mask][u] = (new_cost, start_service_at_u)
                            parent[mask][u] = v
                        elif new_cost == memo[mask][u][0] and start_service_at_u < memo[mask][u][1]:
                            memo[mask][u] = (new_cost, start_service_at_u)
                            parent[mask][u] = v

    min_total_cost = float('inf')
    last_station = -1

    for u in range(1, n):
        path_cost, path_time = memo[all_visited_mask][u]
        if path_cost == float('inf'):
            continue

        return_travel_time = cost_matrix[u][0] / speed
        arrival_at_depot = path_time + inspection_time[u] + return_travel_time

        if arrival_at_depot <= time_windows[0][1]:
            total_cost = path_cost + cost_matrix[u][0]
            if total_cost < min_total_cost:
                min_total_cost = total_cost
                last_station = u
    
    if last_station == -1:
        return {'status': 'infeasible', 'cost': None, 'path': None}

    path = [0]
    curr_station = last_station
    curr_mask = all_visited_mask
    
    while curr_station != 0:
        path.insert(1, curr_station)
        prev_station = parent[curr_mask][curr_station]
        curr_mask ^= (1 << curr_station)
        curr_station = prev_station

    return {
        'status': 'success',
        'cost': min_total_cost,
        'path': path
    }

def main():
    sys.setrecursionlimit(2000)
    NUM_STATIONS = 15
    MAX_COORD = 1000
    MAX_TIME = 5000
    SPEED = 1

    random.seed(42)

    coords = [(random.randint(0, MAX_COORD), random.randint(0, MAX_COORD)) for _ in range(NUM_STATIONS)]
    
    cost_matrix = [[0.0] * NUM_STATIONS for _ in range(NUM_STATIONS)]
    for i in range(NUM_STATIONS):
        for j in range(i, NUM_STATIONS):
            dist = ((coords[i][0] - coords[j][0])**2 + (coords[i][1] - coords[j][1])**2)**0.5
            cost_matrix[i][j] = dist
            cost_matrix[j][i] = dist

    inspection_time = [0] + [random.randint(10, 30) for _ in range(NUM_STATIONS - 1)]

    time_windows = [(0, MAX_TIME)]
    for _ in range(1, NUM_STATIONS):
        open_time = random.randint(0, MAX_TIME - 500)
        close_time = random.randint(open_time + 200, MAX_TIME)
        time_windows.append((open_time, close_time))

    start_time = time.time()
    
    result = find_optimal_route(
        cost_matrix=cost_matrix,
        time_windows=time_windows,
        inspection_time=inspection_time,
        speed=SPEED
    )
    
    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"Result: {result}")
    print(f"Elapsed time: {elapsed_time:.4f} seconds")

if __name__ == "__main__":
    main()