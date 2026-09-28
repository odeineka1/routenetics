import itertools
import random
import csv
from routenetics.cli import args
from rich.console import Console
from rich.text import Text
from rich.rule import Rule

console = Console()

def solve_brute_force(destinations, durations, distances):
    """Finds the exact shortest-duration route by exhaustively checking every possible visiting order.

    The route always starts and ends at destination 0 (treated as the depot), so only the
    remaining len(destinations)-1 stops are permuted. This guarantees the true optimum, but
    runs in O(n!) time, so it's only practical for small destination counts (RouteNetics
    switches to the genetic algorithm above N=8 for this reason).

    Args:
        destinations: list of destination dicts (each with at least a "name", used elsewhere
            for display; this function only relies on the list's length and index positions).
        durations: an NxN matrix (list of lists) where durations[i][j] is the travel time in
            seconds from destination i to destination j.
        distances: an NxN matrix where distances[i][j] is the travel distance in meters from
            destination i to destination j.

    Returns:
        A 3-tuple (best_route, best_duration, best_distance):
            best_route: list of destination indices in visiting order (starts/ends at 0),
                chosen to minimize duration, not distance.
            best_duration: total travel time of best_route, in seconds.
            best_distance: total travel distance of best_route, in meters (the distance of the
                same route that won on duration, not the shortest distance across all routes).
    """
    best_duration = float("inf")
    best_distance = float("inf")
    best_route = []
    for permutation in itertools.permutations(range(1, len(destinations))):  # permute every stop except the depot, which is fixed at both ends
        route = []
        route.append(0)
        route += list(permutation)
        route.append(0)

        duration = calculate_duration(route, durations)
        distance = calculate_distance(route, distances)
        if duration < best_duration:
            best_duration = duration
            best_route = route  # route is picked by lowest duration, not lowest distance
            best_distance = distance  # distance is stored from the same route that won on duration, so the two always describe one real route
    return (best_route, best_duration, best_distance)

def solve_genetic_algo(destinations, durations, distances, pop_size, generations):
    """Approximates the shortest-duration route using a genetic algorithm, for destination counts too large for solve_brute_force() to handle in reasonable time.

    High-level algorithm:
    1. Seed a population of `pop_size` random valid routes (generation 0).
    2. For each generation: keep the top performers unchanged (elitism), then breed the rest
       of the new population by picking two parents via tournament selection and combining
       them with order crossover (see crossover()), which occasionally mutates the child.
    3. Track whether the best duration has stopped improving across generations
       (stagnation); if it stagnates for too long, gradually raise the mutation rate so the
       population can escape a local optimum, then reset it once progress resumes.
    4. After the final generation, return the best route found.

    Several alternate mechanisms (forced breeding with "immigrant" routes, a diversity-based
    stagnation measure) were tried and are left commented out below rather than deleted, in
    case they're revisited later.

    Args:
        destinations: list of destination dicts; only its length is used here (to size each
            route), the contents aren't read directly.
        durations: NxN matrix of travel times in seconds, durations[i][j] = time from i to j.
        distances: NxN matrix of travel distances in meters, distances[i][j] = distance from
            i to j. Only used once, to compute the final best_distance after evolution ends.
        pop_size: number of candidate routes kept in each generation.
        generations: number of breeding generations to run before stopping (the loop actually
            runs generations+1 times, since generation 0 is the random seed population and is
            printed/evaluated like any other generation).

    Returns:
        A 3-tuple (best_route, best_time, best_distance):
            best_route: list of destination indices in visiting order (starts/ends at 0) from
                the final generation's best individual.
            best_time: that route's total duration in seconds, rounded to the nearest second.
            best_distance: that route's total distance in meters, rounded to 1 decimal place.
    """
    
    next_generation = []
    next_generation_immigrants = []

    # Duration stagnation 
    mutation_rate = 0.02
    duration_stagnation_count = 0
    duration_stagnation_count_threshold = 9

    # Diversity stagnation
    # dq = deque([])
    # smoothed_diversity_stagnation = 0
    # diversity_stagnation_threshold = 0.12
    # diversity_stagnation_count = 0
    # diversity_stagnation_count_threshold = 3
    # immigrants_count = 0
    # immigrant_ceiling = int(pop_size * 0.15)
    # immigrant_increment = max(1, int(immigrant_ceiling / 12))

    # Generation 0: seed the population with pop_size random valid routes (depot fixed at both ends).
    # Each individual is stored as a (duration, route) tuple so the population can be sorted by
    # duration directly, without a separate key function.
    print("\nCompiling initial random population... ")
    while len(next_generation) < pop_size:
        route = [i for i in range(1, len(destinations))]
        random.shuffle(route)
        route.insert(0, 0)
        route.append(0)
        
        duration = calculate_duration(route, durations)
        if not (duration, route) in next_generation:  # avoids seeding duplicate routes into gen 0, which would waste population slots
            next_generation.append((duration, route))
        
    next_generation = sorted(next_generation)  # sorted by duration (tuple's first element), so index 0 is always the current best individual
    
    # Generations 1+: each iteration breeds a new population from the current one and reports progress
    print("Running evolution:\n")
    for i in range(0, generations+1):
        current_generation = next_generation
        current_generation_immigrants = next_generation_immigrants
        next_generation = []

        # value is 0-1
        # diversity_stagnation = measure_diversity(current_generation)

        # dq.append(diversity_stagnation)
        # if len(dq) == 10:
        #     smoothed_diversity_stagnation = statistics.mean(dq)
        #     dq.popleft()
        
        # print(f"BEST POP in gen {i}: {current_generation[0]} \nmutation rate: {mutation_rate} \ndur stag: {duration_stagnation_count}")
        # print(f"GENERATION {i}: {current_generation}")
        best_time = round(current_generation[0][0])
        best_hours = int(best_time/3600)  # break the best duration (in seconds) into h/m/s for the progress printout
        best_minutes = int(best_time%3600/60)
        best_seconds = best_time%3600%60

        best_time_str = f"Best Time: {best_hours}h {best_minutes}m {best_seconds}s"

        if i != generations:
            print(f"Generation: {i}/{args.generations} | {best_time_str} | Mutation rate: {round(mutation_rate*100)}%")
        else:
            # last iteration: this is the final evolved population, so lock in its best individual as the answer
            print(f"Generation: {i}/{args.generations} | {best_time_str} | Evolution complete.")

            best_route = current_generation[0][1]

            best_distance = calculate_distance(best_route, distances) # in meters
            best_distance = round(best_distance, 1)


        print()
        # Elites injection: carry the top ~2% of the current generation forward unchanged into the next
        # generation, so a good route can never be lost to unlucky crossover/mutation
        elite_rate = 0.02
        elites_count = max(1, int(pop_size*elite_rate))
        elite_pop = current_generation[:elites_count]
        next_generation += elite_pop

        # Forced breeding with immigrants
        # for _ in range(immigrants_count):
        #     if not current_generation_immigrants:
        #         break

        #     tournament_sample = random.sample(current_generation, k=3)
        #     tournament_sample = sorted(tournament_sample)
        #     parent1 = tournament_sample[0]

        #     parent2 = random.choice(current_generation_immigrants)

        #     child_route = crossover(parent1, parent2, mutation_rate)
        #     duration = calculate_duration(child_route, durations)
        #     next_generation.append((duration, child_route))

                
        # Normal breeding: fill the rest of the new population via tournament selection (pick 3 random
        # individuals, keep the best of the 3 as a parent) for each of the two parents, then combine
        # them with crossover(). Repeated until next_generation reaches pop_size.
        # while len(next_generation) < pop_size-immigrants_count:
        while len(next_generation) < pop_size:
            tournament_sample = random.sample(current_generation, k=3)
            tournament_sample = sorted(tournament_sample)
            parent1 = tournament_sample[0]

            tournament_sample = random.sample(current_generation, k=3)
            tournament_sample = sorted(tournament_sample)
            parent2 = tournament_sample[0]
            
            child_route = crossover(parent1, parent2, mutation_rate)
            duration = calculate_duration(child_route, durations)
            next_generation.append((duration, child_route)) 

        # Immigrants injection
        # next_generation_immigrants = []
        # while len(next_generation) < pop_size:
        #     route = [i for i in range(1, len(destinations))]
        #     random.shuffle(route)
        #     route.insert(0, 0)
        #     route.append(0)
            
        #     duration = calculate_duration(route, durations)
        #     next_generation.append((duration, route))
        #     next_generation_immigrants.append((duration, route))
        
        next_generation = sorted(next_generation)

        # Duration stagnation tracking for mutation_rate adjustment: if the best individual in the new
        # generation is identical to the best in the previous one, the population has stopped improving.
        # After duration_stagnation_count_threshold consecutive stagnant generations, nudge the mutation
        # rate up (capped at 1.0) to inject more randomness and help escape a local optimum. As soon as
        # a new best is found, reset both the stagnation counter and the mutation rate back to baseline.
        if next_generation[0] == current_generation[0]:
            duration_stagnation_count += 1
        else:
            duration_stagnation_count = 0
            mutation_rate = 0.02
        
        if duration_stagnation_count > duration_stagnation_count_threshold:
            mutation_rate = min(1, mutation_rate+0.01)

        # Diversity stagnation tracking for immigrant injection
        # if smoothed_diversity_stagnation > diversity_stagnation_threshold:
        #     diversity_stagnation_count += 1
        # else:
        #     diversity_stagnation_count = 0
        #     immigrants_count = max(0, immigrants_count-immigrant_increment)
        
        # if diversity_stagnation_count > diversity_stagnation_count_threshold:
        #     immigrants_count = min(immigrant_ceiling, immigrants_count+immigrant_increment)
    
# def measure_diversity(generation):
#     routes = [gen[1] for gen in generation]
#     subset_size = 60
#     subset = random.sample(routes, k=subset_size)

#     all_directions_list = []
#     route_directions = set()
#     for route in subset:
#         route_directions = set()
#         for i in range(len(route)-1):
#             route_directions.add((route[i], route[i+1]))
            
#         all_directions_list.append(route_directions)

#     shared_edges = 0
#     max_shared_edges = 0
#     for i in range(len(all_directions_list)-1):
#         for j in range(i+1, len(all_directions_list)):
#             shared_edges += len(all_directions_list[i] & all_directions_list[j])
#             max_shared_edges += len(all_directions_list[0])

#     diversity_stagnation = shared_edges/max_shared_edges

#     return diversity_stagnation

    return(best_route, best_time, best_distance)
    # return(best_route_str)
    
def crossover(parent1, parent2, mutation_rate):
    """Breeds one child route from two parent routes using order crossover (OX), then randomly mutates it.

    Order crossover works like this: pick two random cut points in the route (excluding the
    fixed depot at each end), copy the slice between those cut points directly from parent1,
    then fill in the remaining, still-empty positions using the stops from parent2 in the
    order they appear there, skipping any stop already copied from parent1. This preserves a
    contiguous "building block" of parent1's route while still inheriting parent2's relative
    ordering for everything else — which matters for a routing problem, since what's being
    optimized is really the sequence/adjacency of stops, not just which stops are included
    (both parents already contain every destination exactly once).

    With probability `mutation_rate`, the child then undergoes a simple swap mutation: a
    random contiguous segment of the child route is reversed in place. This introduces new
    orderings that crossover alone couldn't produce from the existing parents.

    Args:
        parent1: a (duration, route) tuple, same format as an entry in the population list
            used by solve_genetic_algo() — only the route (index 1) is used here.
        parent2: a (duration, route) tuple, same format as parent1.
        mutation_rate: float between 0 and 1, the probability that the mutation step below
            is applied to the resulting child route.

    Returns:
        child_route: a list of destination indices representing the new route, starting and
            ending at the depot (index 0).
    """
    parent_route1 = parent1[1][1:-1]  # strip the depot (index 0 and -1) since it's fixed and re-added at the end
    parent_route2 = parent2[1][1:-1]

    child_route = [None for i in range(0, len(parent_route1))]

    cut1 = random.randint(0, len(parent_route1)-1) 
    cut2 = random.randint(0, len(parent_route1)-1)
    while cut1 == cut2:  # ensures the two cut points are distinct, so the copied slice is never empty
        cut2 = random.randint(0, len(parent_route1)-1)
    cut1, cut2 = sorted([cut1, cut2])

    copied_indeces = set()
    for i in range(cut1, cut2+1):  # copy the slice between the two cut points straight from parent1, preserving its exact order
        child_route[i] = parent_route1[i]
        copied_indeces.add(parent_route1[i])

    child_pointer = 0
    for i in parent_route2:  # walk parent2 in order, placing each stop not already copied into the next open slot in child_route
        if not i in copied_indeces:
            while child_pointer < len(child_route) and child_route[child_pointer] != None:
                child_pointer += 1
            child_route[child_pointer] = i

    # Mutation: with probability mutation_rate, pick two random cut points and reverse everything
    # between them (a classic "reversal" mutation for permutation/TSP-style problems, since it always
    # produces another valid route where every stop still appears exactly once)
    if random.random() < mutation_rate:
        # print("MUTATION HAPPENED")
        cut1 = random.randint(0, len(child_route)-1) 
        cut2 = random.randint(0, len(child_route)-1)
        while cut1 == cut2:
            cut2 = random.randint(0, len(child_route)-1)
        cut1, cut2 = sorted([cut1, cut2])

        child_route[cut1:cut2+1] = child_route[cut1:cut2+1][::-1]
    
    child_route.insert(0, 0)  # re-add the depot at both ends, since it was stripped off at the start
    child_route.append(0)
    
    return child_route

def calculate_duration(route, durations):
    """Sums the travel time between each consecutive pair of stops in a route.

    Args:
        route: list of destination indices in visiting order (e.g. [0, 3, 1, 2, 0]).
        durations: NxN matrix where durations[i][j] is the travel time in seconds from
            destination i to destination j.

    Returns:
        Total travel time for the route, in seconds, as the sum of durations[route[i]][route[i+1]]
        over every consecutive pair of stops.
    """
    duration = 0
    for i in range(len(route)-1):
        duration += durations[route[i]][route[i+1]]
    
    return duration

def calculate_distance(route, distances):
    """Sums the travel distance between each consecutive pair of stops in a route.

    Args:
        route: list of destination indices in visiting order (e.g. [0, 3, 1, 2, 0]).
        distances: NxN matrix where distances[i][j] is the travel distance in meters from
            destination i to destination j.

    Returns:
        Total travel distance for the route, in meters, as the sum of distances[route[i]][route[i+1]]
        over every consecutive pair of stops.
    """
    distance = 0
    for i in range(len(route)-1):
        distance += distances[route[i]][route[i+1]]
    
    return distance

def generate_report(best_route, best_time, best_distance, destinations, execution_mode, execution_time, roi):
    """Prints the final terminal report for a completed run: the optimized route as a readable path, its total driving time/distance, and the fuel/labor/CO2 ROI versus the unoptimized baseline route.

    Args:
        best_route: list of destination indices in visiting order (the optimized route).
        best_time: total duration of best_route, in seconds.
        best_distance: total distance of best_route, in meters (this function converts it to
            kilometers for display, so the caller should pass the raw meter value).
        destinations: list of destination dicts, each expected to have a "name" key, used to
            turn best_route's indices into a human-readable path string.
        execution_mode: display string identifying which solver was used ("Brute Force Engine"
            or "Evolutionary Engine"), shown in the report header.
        execution_time: wall-clock seconds the solver took to run, shown in the report header.
        roi: the dict returned by calculate_roi(), containing the saved distance/fuel/labor/
            CO2/tree figures printed in the sustainability section.

    Returns:
        None. This function only prints to the console and writes nothing itself (the CSV
        export happens separately, in write_route()).
    """
    best_route_str = f""
    for j in range(len(best_route)):  # build the "A -> B -> C" path string shown in the report
        destination = best_route[j]
        if j != 0:
            best_route_str += f" -> {destinations[destination]["name"]}"
        else:
            best_route_str += f"{destinations[destination]["name"]}"

    best_hours = int(best_time/3600)  # convert the total duration in seconds into h/m/s for display
    best_minutes = int(best_time%3600/60)
    best_seconds = best_time%3600%60
    best_time_str = f"{best_hours}h {best_minutes}m {best_seconds}s"

    best_distance /= 1000 # from meters to kilometers
    best_distance_str = f"{round(best_distance, 1)} km"

    console.print(Rule(style="bright_cyan"))
    console.print(Text(f"✨ ROUTENETICS REPORT", style="bold bright_cyan"), justify="center")
    console.print(Rule(style="bright_cyan"))
    console.print(Text(f"[Execution Mode] ", style="bright_cyan"), end="")
    console.print(Text(f"{execution_mode}"))
    console.print(Text(f"[Solve Time] ", style="bright_cyan"), end="")
    console.print(Text(f"{round(execution_time, 1)} seconds"))
    console.print(Text(f"[Optimal Route]\n", style="bright_cyan"), end="")
    console.print(Text(f"{best_route_str}"))
    console.print(Text(f"[Driving Time] ", style="bright_cyan"), end="")
    console.print(Text(f"{best_time_str}"))
    console.print(Text(f"[Travel Distance] ", style="bright_cyan"), end="")
    console.print(Text(f"{best_distance_str}"))
    console.print(Rule(style="bright_cyan"))

    console.print(Text(f"🌲 SUSTAINABILITY & FINANCIAL ROI (Vs. Inputted Unoptimized Baseline)", style="bold bright_cyan"), justify="center")
    console.print(Rule(style="bright_cyan"))
    console.print(Text(f"[FUEL] ", style="bright_cyan"), end="")
    console.print(Text(f"Distance Saved: {roi["saved_distance"]:,} km | Fuel Cost Saved: ${roi["saved_fuel_price"]:,}"))
    console.print(Text(f"[LABOR] ", style="bright_cyan"), end="")
    console.print(Text(f"Labor Time Saved: {roi["saved_labor"]} | Labor Cost Saved: ${roi["saved_labor_price"]:,}"))
    console.print(Text(f"[ROI] ", style="bright_cyan"), end="")
    console.print(Text(f"Total Dispatch Savings: ${roi["total_savings"]} per run"))
    console.print(Text(f"[CO2] ", style="bright_cyan"), end="")
    console.print(Text(f"Carbon Emissions Reduced: {roi["saved_co2"]:,} kg | Trees Saved: {roi["saved_trees"]:,}"))
    console.print(Rule(style="bright_cyan"))

    console.print(Text(f"[SUCCESS] ", style="bright_cyan"), end="")
    console.print(Text(f"Dispatch schedule pipeline written to 'output/optimized_route.csv'"))
    
def calculate_baseline_route(destinations, durations, distances):
    """Computes the total duration and distance of the "naive" baseline route — destinations visited in whatever order they appear in the input data, with no optimization — so the optimized route's savings can be measured against it.

    Args:
        destinations: list of destination dicts; only its length is used, to build the
            baseline visiting order [0, 1, 2, ..., N-1, 0] (ending back at the depot, like
            the optimized routes do).
        durations: NxN matrix of travel times in seconds between destinations.
        distances: NxN matrix of travel distances in meters between destinations.

    Returns:
        A 2-tuple (baseline_duration, baseline_distance): the total time in seconds and
        distance in meters of visiting every destination in input order and returning to
        the depot.
    """
    baseline_route = [i for i in range(len(destinations))] + [0]  # returns to the depot at the end, same as every optimized route, so the comparison is like for like
    baseline_duration = calculate_duration(baseline_route, durations)
    baseline_distance = calculate_distance(baseline_route, distances)

    return (baseline_duration, baseline_distance)

def calculate_roi(
        best_time,
        baseline_time,
        best_distance,
        baseline_distance,
        fuel_consumption_l_per_100km = 10.0,   # adjust to your vehicle
        fuel_price_per_l=1.20,          # adjust to your local fuel price
        labor_rate_per_hour=25.0,       # adjust to your driver wage
        co2_kg_per_l_fuel=2.68,         # standard diesel emissions factor
        co2_kg_per_tree_per_year=21.0,  # rough offset equivalence
):
    """Converts the time and distance saved by the optimized route (vs. the baseline) into labor cost, fuel cost, CO2 emissions, and total dollar savings, using the rate assumptions passed in as keyword arguments.

    The savings are computed independently along two axes: labor cost comes from the time
    saved (fewer driving hours at the given wage), while fuel cost and CO2 come from the
    distance saved (less fuel burned over a shorter route) — the two are not the same thing,
    since a shorter route isn't always a faster one and vice versa.

    Args:
        best_time: total duration of the optimized route, in seconds.
        baseline_time: total duration of the baseline route, in seconds.
        best_distance: total distance of the optimized route, in meters.
        baseline_distance: total distance of the baseline route, in meters.
        fuel_consumption_l_per_100km: vehicle's fuel consumption rate, in liters per 100km.
        fuel_price_per_l: local fuel price, in currency units per liter.
        labor_rate_per_hour: driver's hourly wage, in currency units per hour.
        co2_kg_per_l_fuel: CO2 emitted per liter of fuel burned, in kg (2.68 is a standard
            figure for diesel).
        co2_kg_per_tree_per_year: rough amount of CO2 (in kg) a single tree offsets per year,
            used only to translate the CO2 savings into an intuitive "trees saved" figure.

    Returns:
        A dict with the following keys, each pre-rounded for display:
            saved_distance: distance saved, in kilometers (best vs. baseline).
            saved_fuel_price: fuel cost saved, in currency units.
            saved_labor: time saved, as a formatted "Xh Ym" string.
            saved_labor_price: labor cost saved, in currency units.
            total_savings: saved_labor_price + saved_fuel_price combined.
            saved_co2: CO2 emissions avoided, in kg.
            saved_trees: saved_co2 expressed as an equivalent number of trees per year.
    """
    saved_time = baseline_time-best_time
    saved_distance = baseline_distance/1000-best_distance/1000  # baseline minus best, same direction as saved_time, so a shorter optimized route gives a positive saving

    saved_labor = round(saved_time/3600, 1)

    saved_labor_hours = int(saved_time/3600)
    saved_labor_minutes = int(saved_time%3600/60)
    saved_labor_str = f"{saved_labor_hours}h {saved_labor_minutes}m"

    saved_labor_price = round(saved_time/3600*labor_rate_per_hour, 1)  # uses the unrounded hours so rounding saved_labor to 0.1h doesn't shift the price
    saved_fuel = (saved_distance/100)*fuel_consumption_l_per_100km  # fuel use scales with distance, not time, so this uses saved_distance rather than saved_time
    saved_fuel_price = saved_fuel*fuel_price_per_l

    saved_co2 = saved_fuel*co2_kg_per_l_fuel
    saved_trees = saved_co2/co2_kg_per_tree_per_year  # rough equivalent number of trees needed to offset that much CO2 in a year, purely illustrative

    total_savings = saved_labor_price + saved_fuel_price

    return {
        "saved_distance": round(saved_distance, 1),
        "saved_fuel_price": round(saved_fuel_price, 1),
        "saved_labor": saved_labor_str,
        "saved_labor_price": round(saved_labor_price, 1),
        "total_savings": round(total_savings, 1),
        "saved_co2": round(saved_co2, 1),
        "saved_trees": round(saved_trees, 1),
    }

def write_route(route, destinations):
    """Writes the optimized route to output/optimized_route.csv as an ordered list of stops, one row per stop in visiting order.

    Args:
        route: list of destination indices in visiting order.
        destinations: list of destination dicts, each expected to have "name", "lat", and
            "lng" keys, used to populate each output row.

    Returns:
        None. Writes directly to output/optimized_route.csv (overwriting any existing file
        at that path) and returns nothing.
    """
    with open("output/optimized_route.csv", "w") as file: 
        writer = csv.DictWriter(file, fieldnames=["point_name", "latitude", "longitude"])
        for i in route: 
            writer.writerow({"point_name": destinations[i]["name"], "latitude": destinations[i]["lat"], "longitude": destinations[i]["lng"]})