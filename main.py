from routenetics.ingestion import load_points
from routenetics.cli import args
from routenetics.network import build_matrices
from routenetics.engine import solve_brute_force
from routenetics.engine import solve_genetic_algo
from routenetics.engine import generate_report
from routenetics.engine import calculate_baseline_route
from routenetics.engine import calculate_roi
from routenetics.engine import write_route
from rich.console import Console
from rich.text import Text
from rich.rule import Rule
import time

# TODO test roi function

console = Console()

def main():
    """Runs the full RouteNetics pipeline end to end: load destinations, fetch a real-world distance/duration matrix, solve for the optimal route, write it out, and print a report with the ROI vs. an unoptimized baseline.

    Which solver runs is decided automatically by destination count: solve_brute_force()
    (guaranteed optimal, but O(n!)) is used for 8 or fewer destinations, otherwise
    solve_genetic_algo() (an approximation, but scales to much larger N) takes over — see the
    branch below for the exact cutoff and reasoning.

    Args:
        None. All inputs are pulled from the parsed CLI flags in routenetics.cli (`args`):
            args.file: name of the input CSV under data/, e.g. "points.csv".
            args.pop_size: population size passed through to solve_genetic_algo().
            args.generations: generation count passed through to solve_genetic_algo().

    Returns:
        None. This function's job is entirely side effects: it prints progress and the final
        report to the terminal via `console`, and writes the optimized route to
        output/optimized_route.csv via write_route().
    """
    start_time = time.time()
    destinations, destinations_count = load_points(f"data/{args.file}")
    start_time_matrices = time.time()
    durations, distances = build_matrices(destinations)  # calls OSRM for real-world road distances/times, not straight-line "as the crow flies" distances
    end_time_matrices = time.time()
    total_time_matrices = end_time_matrices-start_time_matrices  # timed separately from the overall run so the report can show how much of the total time was spent waiting on the OSRM API vs. actually solving

    console.print(Rule(style="bright_cyan"))
    console.print(Text(f"ROUTENETICS // Logistics Optimizer", style="bold bright_cyan"), justify="center")
    console.print(Rule(style="bright_cyan"))

    console.print(Text("[SUCCESS] ", style="green"), end="")
    console.print(Text(f"Loaded {destinations_count} destinations from '{args.file}'."))
    console.print(Text("[NETWORK] ", style="bright_cyan"), end="")
    console.print(Text(f"Initializing asynchronous HTTP pool..."))
    console.print(Text("[NETWORK] ", style="bright_cyan"), end="")
    console.print(Text(f"Fetching real-world OSRM road matrix..."))
    console.print(Text("[SUCCESS] ", style="green"), end="")
    console.print(Text(f"{destinations_count}x{destinations_count} Distance & Time Matrix built in {round(total_time_matrices, 2)}s.\n"))
    
    # Solver selection: brute force checks every permutation of stops (N-1 stops to permute, since
    # the depot at index 0 is fixed), which is N! work — past ~8 destinations that becomes far too
    # slow to run interactively, so the genetic algorithm (an approximation, not a guaranteed optimum)
    # takes over instead, trading a small amount of route quality for a solve time that scales to
    # much larger destination counts
    if destinations_count > 8:
        execution_mode = "Evolutionary Engine"

        console.print(Text("[ENGINE] ", style="bright_cyan"), end="")
        console.print(Text(f"Destination count N = {destinations_count}."))
        console.print(Text("[MODE] ", style="bright_cyan"), end="")
        console.print(Text(f"Switching to Evolutionary AI Engine (Genetic Algorithm)."))
        console.print(Text("[INFO] ", style="bright_cyan"), end="")
        console.print(Text(f"Population Size: {args.pop_size} | Target Generations: {args.generations}"))

        best_route, best_time, best_distance = solve_genetic_algo(destinations, durations, distances, args.pop_size, args.generations)


    else:
        execution_mode = "Brute Force Engine"

        console.print(Text("[ENGINE] ", style="bright_cyan"), end="")
        console.print(Text(f"Destination count N = {destinations_count}."))
        console.print(Text("[MODE] ", style="bright_cyan"), end="")
        console.print(Text(f"Switching to Brute Force Engine (Genetic Algorithm)."))

        best_route, best_time, best_distance = solve_brute_force(destinations, durations, distances)  # exhaustively checks every permutation, so the result is guaranteed optimal for this small N

        console.print(Text("[INFO] ", style="bright_cyan"), end="")
        console.print(Text(f"Brute Force Search Complete"))

    end_time = time.time()
    execution_time = end_time - start_time  # measured from the very start of main(), so this includes the OSRM fetch time as well as the solve itself

    # print(best_route)
    # print(best_time)
    # print(best_distance)

    write_route(best_route, destinations)
    
    # baseline is the "do nothing clever" comparison point: visiting every destination in whatever
    # order they appeared in the input file, with no optimization applied — this is what the ROI
    # figures below are measured against, not some theoretical worst case
    baseline_time, baseline_distance = calculate_baseline_route(destinations, durations, distances)
    roi = calculate_roi(
        best_time,
        baseline_time,
        best_distance,
        baseline_distance,
        fuel_consumption_l_per_100km=10.0,   # adjust to your vehicle
        fuel_price_per_l=1.20,          # adjust to your local fuel price
        labor_rate_per_hour=25.0,       # adjust to your driver wage
        co2_kg_per_l_fuel=2.68,         # standard diesel emissions factor
        co2_kg_per_tree_per_year=21.0,  # rough offset equivalence
    )

    generate_report(
        best_route,
        best_time,
        best_distance,
        destinations,
        execution_mode,
        execution_time,
        roi,
)
    
if __name__ == "__main__":
    main()