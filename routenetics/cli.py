import argparse

"""Defines RouteNetics' command-line arguments and parses them at import time.

`args` is built once here and imported directly by main.py, engine.py, etc. (e.g.
`from routenetics.cli import args`), rather than each module constructing/parsing its own
argparse.ArgumentParser — this keeps the CLI flags defined in exactly one place.

Flags:
    --file: name of the input CSV (relative to the data/ folder, per main.py's
        f"data/{args.file}"), defaults to "points.csv".
    --pop_size: population size for the genetic algorithm (only used when destinations_count
        > 8, see main.py), defaults to 5000.
    --generations: number of generations the genetic algorithm runs for, defaults to 100.
"""

parser = argparse.ArgumentParser()

parser.add_argument("--file", default="points.csv", help="input file")
parser.add_argument("--pop_size", default=500, help="population size", type=int)
parser.add_argument("--generations", default=300,  help="generations", type=int)

args = parser.parse_args()  # parsed immediately at import time, so every module that imports `args` gets the same already-parsed values