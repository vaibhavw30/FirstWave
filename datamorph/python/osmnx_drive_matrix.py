"""
Datamorph Python action — Stage ⑥: osmnx_drive_matrix  (runs in PARALLEL, ~30-60 min)
FirstWave | GT Hacklytics 2026

No upstream dependency — wire it parallel to Stages ①-⑤; Stages ⑦/⑧ wait on it.

Inputs:
  OpenStreetMap (downloaded via OSMnx)
  data/ems_stations.json   (optional — adds station origins)
Output:
  backend/artifacts/drive_time_matrix.pkl   dict[(origin_key, dest_zone)] = seconds
  backend/artifacts/nyc_graph.pkl, zone_nodes.pkl (caches)

Mirrors: pipeline/06_osmnx_matrix.py. Falls back to a Haversine approximation
(x1.35 circuity / 25 km/h) if the OSMnx download fails (~15% less accurate).
"""

import json
import math
import pathlib
import pickle

ARTIFACTS = pathlib.Path("backend/artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
GRAPH_PKL = ARTIFACTS / "nyc_graph.pkl"
NODES_PKL = ARTIFACTS / "zone_nodes.pkl"
MATRIX_PKL = ARTIFACTS / "drive_time_matrix.pkl"
STATIONS_JSON = pathlib.Path("data/ems_stations.json")

ZONE_CENTROIDS = {
    'B1': (-73.9101, 40.8116), 'B2': (-73.9196, 40.8448), 'B3': (-73.8784, 40.8189),
    'B4': (-73.8600, 40.8784), 'B5': (-73.9056, 40.8651),
    'K1': (-73.9857, 40.5995), 'K2': (-73.9442, 40.6501), 'K3': (-73.9075, 40.6929),
    'K4': (-73.9015, 40.6501), 'K5': (-73.9283, 40.6801), 'K6': (-73.9645, 40.6401),
    'K7': (-73.9573, 40.7201),
    'M1': (-74.0060, 40.7128), 'M2': (-74.0000, 40.7484), 'M3': (-73.9857, 40.7580),
    'M4': (-73.9784, 40.7484), 'M5': (-73.9584, 40.7701), 'M6': (-73.9484, 40.7884),
    'M7': (-73.9428, 40.8048), 'M8': (-73.9373, 40.8284), 'M9': (-73.9312, 40.8484),
    'Q1': (-73.7840, 40.6001), 'Q2': (-73.8284, 40.7501), 'Q3': (-73.8784, 40.7201),
    'Q4': (-73.9073, 40.7101), 'Q5': (-73.8073, 40.6901), 'Q6': (-73.9173, 40.7701),
    'Q7': (-73.8373, 40.7701),
    'S1': (-74.1115, 40.6401), 'S2': (-74.1515, 40.5901), 'S3': (-74.1915, 40.5301),
}
VALID_ZONES = list(ZONE_CENTROIDS.keys())


def _haversine_km(lon1, lat1, lon2, lat2):
    R, dlat, dlon = 6371, math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _haversine_sec(lon1, lat1, lon2, lat2):
    return int((_haversine_km(lon1, lat1, lon2, lat2) * 1.35 / 25.0) * 3600)


def haversine_matrix(stations):
    m = {}
    for oz, (olon, olat) in ZONE_CENTROIDS.items():
        for dz, (dlon, dlat) in ZONE_CENTROIDS.items():
            m[(oz, dz)] = _haversine_sec(olon, olat, dlon, dlat)
    for s in stations:
        for dz, (dlon, dlat) in ZONE_CENTROIDS.items():
            m[(s["station_id"], dz)] = _haversine_sec(s["lon"], s["lat"], dlon, dlat)
    return m


def main():
    stations = json.loads(STATIONS_JSON.read_text()) if STATIONS_JSON.exists() else []
    print(f"Loaded {len(stations)} EMS stations")

    matrix = None
    try:
        import networkx as nx
        import osmnx as ox

        if GRAPH_PKL.exists():
            G = pickle.loads(GRAPH_PKL.read_bytes())
        else:
            print("Downloading NYC road network (~400MB, 5-10 min)...")
            G = ox.graph_from_place("New York City, New York, USA", network_type="drive")
            G = ox.add_edge_travel_times(ox.add_edge_speeds(G))
            GRAPH_PKL.write_bytes(pickle.dumps(G))

        zone_nodes = {z: ox.nearest_nodes(G, lon, lat) for z, (lon, lat) in ZONE_CENTROIDS.items()}
        NODES_PKL.write_bytes(pickle.dumps(zone_nodes))
        station_nodes = {s["station_id"]: ox.nearest_nodes(G, s["lon"], s["lat"]) for s in stations}

        matrix = {}
        origins = {**zone_nodes, **station_nodes}
        for i, (okey, onode) in enumerate(origins.items()):
            lengths = nx.single_source_dijkstra_path_length(G, onode, weight="travel_time")
            for dz in VALID_ZONES:
                matrix[(okey, dz)] = int(lengths.get(zone_nodes.get(dz), 9999))
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{len(origins)} origins")
    except Exception as e:
        print(f"OSMnx unavailable ({e}) — using Haversine fallback (~15% less accurate)")
        matrix = haversine_matrix(stations)

    MATRIX_PKL.write_bytes(pickle.dumps(matrix))
    b1b2 = matrix.get(("B1", "B2"), 9999)
    print(f"drive_time_matrix.pkl saved: {len(matrix):,} pairs   B1->B2 = {b1b2}s")
    if b1b2 >= 9999:
        print("WARN: adjacent Bronx zones unreachable — check graph build")


if __name__ == "__main__":
    main()
