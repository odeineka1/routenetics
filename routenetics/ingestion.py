import csv
import sys

def load_points(file_name):
    """Reads a CSV of delivery points and converts each row into a destination dict ready for the distance/duration matrix builder.

    Expects the CSV to have "point_name", "latitude", and "longitude" columns (matching the
    format write_route() writes back out in the engine module). Coordinates are parsed as
    floats here so downstream code (build_matrices, calculate_distance, etc.) never has to
    worry about them still being strings.

    Args:
        file_name: path to the input CSV file, e.g. "data/points.csv".

    Returns:
        A 2-tuple (destinations, destinations_count):
            destinations: list of dicts, one per row, each shaped as
                {"name": <str>, "lat": <float>, "lng": <float>}.
            destinations_count: total number of rows read from the file, used elsewhere for
                display and for deciding whether to brute-force or run the genetic algorithm.

    Exits:
        Calls sys.exit() with an error message (including the offending row number) if a
        row's latitude/longitude can't be parsed as a float, rather than letting a malformed
        input file crash later with a less useful error.
    """
    destinations = []
    destinations_count = 0

    with open(file_name) as file:
        reader = csv.DictReader(file)
        for row in reader:
            destinations_count += 1  # incremented before the try block so it's already correct for the error message below
            try:
                row["latitude"] = float(row["latitude"])
                row["longitude"] = float(row["longitude"])
            except ValueError:
                sys.exit(f"[ERROR] Invalid coordinates found on row {destinations_count}")

            destinations.append({"name": row["point_name"], "lat": row["latitude"], "lng": row["longitude"]})  # renamed here to "lat"/"lng" to match what build_matrices() and the engine expect

    return (destinations, destinations_count)