import requests
import sys
import json

def build_matrices(destinations):
    """Fetches real-world driving durations and distances between every pair of destinations using the public OSRM (Open Source Routing Machine) Table Service.

    Builds a single request to OSRM's /table endpoint with all destination coordinates,
    which returns two NxN matrices in one call rather than requiring a separate request per
    pair of points (a naive N^2 approach would be far slower and more likely to hit rate
    limits on the public demo server).

    Args:
        destinations: list of destination dicts, each expected to have "lng" and "lat" keys
            (longitude/latitude as OSRM expects them, in that order in the URL).

    Returns:
        A 2-tuple (durations, distances):
            durations: NxN matrix (list of lists) where durations[i][j] is the driving time
                in seconds from destinations[i] to destinations[j], in the same order as the
                input list.
            distances: NxN matrix where distances[i][j] is the driving distance in meters
                from destinations[i] to destinations[j].

    Exits:
        Calls sys.exit() with an error message if the HTTP request to OSRM fails, rather than
        letting the exception propagate — this is treated as a fatal, unrecoverable error
        since the rest of the pipeline can't run without a distance/duration matrix.
    """
    url_string = "http://router.project-osrm.org/table/v1/driving/"
    for dest in destinations:
        url_string += f"{dest["lng"]},{dest["lat"]};"  # OSRM expects "lng,lat" pairs separated by semicolons
    url_string = url_string[0:-1] + "?annotations=duration,distance"  # trims the trailing ";" from the loop above, then asks OSRM for both duration and distance (by default it only returns duration)

    try:
        response = requests.get(url_string)
    except requests.HTTPError:  # covers connection failures / bad responses from the public OSRM server
        sys.exit("[ERROR] Couldn't complete API request")

    # print(json.dumps(response.json(), indent=2))

    distances = response.json()["distances"]
    durations = response.json()["durations"]
    
    return (durations, distances)