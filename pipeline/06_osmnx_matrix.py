"""
Script 06 — OSMnx Drive-Time Matrix
FirstWave | GT Hacklytics 2026

START THIS FIRST -- takes 30-60 minutes. Run in a background terminal.

Output: backend/artifacts/drive_time_matrix.pkl
        backend/artifacts/nyc_graph.pkl      (cached road network)
        backend/artifacts/zone_nodes.pkl     (zone -> road node mapping)

Run: python pipeline/06_osmnx_matrix.py [--stations data/ems_stations.json]
"""

import argparse
import json
import math
import pathlib
import pickle
import sys

import osmnx as ox
import networkx as nx

# ── Paths ──────────────────────────────────────────────────────────────────────
ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

GRAPH_PKL  = ARTIFACTS_DIR / "nyc_graph.pkl"
NODES_PKL  = ARTIFACTS_DIR / "zone_nodes.pkl"
MATRIX_PKL = ARTIFACTS_DIR / "drive_time_matrix.pkl"

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--stations", default="data/ems_stations.json",
                    help="Path to ems_stations.json (optional)")
args = parser.parse_args()

# ── Constants ──────────────────────────────────────────────────────────────────
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
print(f"ZONE_CENTROIDS: {len(ZONE_CENTROIDS)} zones")


# ── Haversine fallback ─────────────────────────────────────────────────────────
def haversine_km(lon1, lat1, lon2, lat2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def haversine_drive_seconds(lon1, lat1, lon2, lat2) -> int:
    straight_km = haversine_km(lon1, lat1, lon2, lat2)
    road_km = straight_km * 1.35   # NYC urban circuity factor
    hours   = road_km / 25.0       # 25 km/h average urban speed
    return int(hours * 3600)


def build_haversine_matrix(stations=None) -> dict:
    print("Building Haversine fallback matrix...")
    fallback = {}
    for origin_zone, (olon, olat) in ZONE_CENTROIDS.items():
        for dest_zone, (dlon, dlat) in ZONE_CENTROIDS.items():
            fallback[(origin_zone, dest_zone)] = haversine_drive_seconds(olon, olat, dlon, dlat)
    if stations:
        for s in stations:
            for dest_zone, (dlon, dlat) in ZONE_CENTROIDS.items():
                fallback[(s["station_id"], dest_zone)] = haversine_drive_seconds(
                    s["lon"], s["lat"], dlon, dlat
                )
    print(f"Haversine matrix: {len(fallback):,} pairs")
    return fallback


# ── Step 1: Load EMS stations ─────────────────────────────────────────────────
stations = []
stations_path = pathlib.Path(args.stations)
if stations_path.exists():
    with open(stations_path) as f:
        stations = json.load(f)
    print(f"Loaded {len(stations)} EMS stations from {stations_path}")
    for s in stations[:3]:
        print(f"  {s.get('station_id','?')}: ({s.get('lon','?')}, {s.get('lat','?')})")
else:
    print(f"WARNING: {stations_path} not found -- using empty station list")
    print("  Ask Ansh to commit data/ems_stations.json before running Script 08")

# ── Step 2: Download NYC road network (or load cached) ────────────────────────
USE_OSMNX = True
G = None

if GRAPH_PKL.exists():
    print(f"\nLoading cached road network from {GRAPH_PKL}...")
    try:
        with open(GRAPH_PKL, "rb") as f:
            G = pickle.load(f)
        print(f"  Loaded: {len(G.nodes):,} nodes, {len(G.edges):,} edges")
    except Exception as e:
        print(f"  Failed to load cache: {e}")
        G = None

if G is None:
    try:
        print("\nDownloading NYC road network (~400MB, 5-10 min)...")
        print("This is the longest step -- please wait...")
        G = ox.graph_from_place("New York City, New York, USA", network_type="drive")
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        print(f"\nGraph downloaded! Nodes: {len(G.nodes):,}, Edges: {len(G.edges):,}")

        print(f"Saving graph to {GRAPH_PKL}...")
        with open(GRAPH_PKL, "wb") as f:
            pickle.dump(G, f)
        print("  nyc_graph.pkl saved")
    except Exception as e:
        print(f"WARNING: OSMnx graph download failed: {e}")
        print("Falling back to Haversine approximation")
        USE_OSMNX = False

# ── Step 3: Map zone centroids and EMS stations to road nodes ─────────────────
zone_nodes = {}
station_nodes = {}

if USE_OSMNX and G is not None:
    print("\nMapping zone centroids to nearest road nodes...")
    for zone, (lon, lat) in ZONE_CENTROIDS.items():
        try:
            node_id, dist = ox.nearest_nodes(G, lon, lat, return_dist=True)
            zone_nodes[zone] = node_id
            if dist > 500:
                print(f"  WARNING {zone}: centroid {dist:.0f}m from nearest node")
        except Exception as e:
            print(f"  WARNING {zone}: failed to find node -- {e}")
    print(f"  Mapped {len(zone_nodes)}/{len(ZONE_CENTROIDS)} zones")

    with open(NODES_PKL, "wb") as f:
        pickle.dump(zone_nodes, f)

    print(f"\nMapping {len(stations)} EMS stations to road nodes...")
    for s in stations:
        try:
            node_id = ox.nearest_nodes(G, s["lon"], s["lat"])
            station_nodes[s["station_id"]] = node_id
        except Exception as e:
            print(f"  WARNING {s['station_id']}: {e}")
    print(f"  Mapped {len(station_nodes)}/{len(stations)} stations")

# ── Step 4: Compute drive-time matrix ─────────────────────────────────────────
if USE_OSMNX and G is not None and len(zone_nodes) > 0:
    all_origins = {**zone_nodes, **station_nodes}
    n_origins = len(all_origins)
    print(f"\nComputing drive times: {n_origins} origins x {len(VALID_ZONES)} destinations")
    print("This takes 20-40 minutes -- progress logged every 10 origins...\n")

    drive_time_matrix = {}
    failed = []

    for i, (origin_key, origin_node) in enumerate(all_origins.items()):
        try:
            lengths = nx.single_source_dijkstra_path_length(
                G, origin_node, weight="travel_time"
            )
            for dest_zone in VALID_ZONES:
                dest_node = zone_nodes.get(dest_zone)
                if dest_node is None:
                    drive_time_matrix[(origin_key, dest_zone)] = 9999
                else:
                    drive_time_matrix[(origin_key, dest_zone)] = int(
                        lengths.get(dest_node, 9999)
                    )
        except Exception as e:
            failed.append(origin_key)
            for dest_zone in VALID_ZONES:
                drive_time_matrix[(origin_key, dest_zone)] = 9999

        if (i + 1) % 10 == 0:
            pct = (i + 1) / n_origins * 100
            print(f"  Progress: {i+1}/{n_origins} ({pct:.0f}%) origins done")

    print(f"\nMatrix complete: {len(drive_time_matrix):,} pairs")

    if failed:
        print(f"  Failed origins: {failed}")
        print("  Filling failed entries with Haversine fallback...")
        for origin_key in failed:
            if origin_key in ZONE_CENTROIDS:
                olon, olat = ZONE_CENTROIDS[origin_key]
            else:
                station = next((s for s in stations if s["station_id"] == origin_key), None)
                if not station:
                    continue
                olon, olat = station["lon"], station["lat"]
            for dest_zone, (dlon, dlat) in ZONE_CENTROIDS.items():
                drive_time_matrix[(origin_key, dest_zone)] = haversine_drive_seconds(
                    olon, olat, dlon, dlat
                )
else:
    print("\nUsing Haversine fallback matrix (OSMnx not available)")
    drive_time_matrix = build_haversine_matrix(stations)
    print("NOTE: Tell the team -- counterfactual numbers ~15% less accurate with Haversine")

# ── Step 5: Save matrix ────────────────────────────────────────────────────────
with open(MATRIX_PKL, "wb") as f:
    pickle.dump(drive_time_matrix, f)
print(f"\ndrive_time_matrix.pkl saved: {MATRIX_PKL}")
print(f"  Pairs: {len(drive_time_matrix):,}")

# ── Validation ─────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print("  SCRIPT 06 -- VALIDATION")
print("=" * 55)
print(f"  Matrix size: {len(drive_time_matrix):,} pairs")
print()

# Sample drive times
sample = [
    ('B1', 'B2'),  # Adjacent Bronx -- expect 300-500s
    ('B1', 'M7'),  # Bronx to Harlem -- expect 600-1000s
    ('M3', 'K4'),  # Midtown to East Brooklyn -- expect 1200-2000s
    ('S1', 'B1'),  # Staten Island to South Bronx -- expect 2000-4000s
    ('Q2', 'M7'),  # Flushing to Harlem -- expect 1500-2500s
]

print("  Sample drive times:")
for o, d in sample:
    t = drive_time_matrix.get((o, d))
    if t is not None and t < 9999:
        print(f"    {o} -> {d}: {t:4d}s ({t/60:.1f} min)")
    else:
        print(f"    {o} -> {d}: NOT FOUND (9999)")

unreachable = sum(1 for v in drive_time_matrix.values() if v >= 9999)
reachable_pct = (len(drive_time_matrix) - unreachable) / len(drive_time_matrix) * 100
print()
print(f"  Reachable pairs:    {len(drive_time_matrix) - unreachable:,} ({reachable_pct:.1f}%)")
print(f"  Unreachable (9999): {unreachable:,}")

b1_b2 = drive_time_matrix.get(('B1', 'B2'), 9999)
if 180 <= b1_b2 <= 900:
    print(f"  OK: B1->B2 = {b1_b2}s -- reasonable adjacent-zone drive time")
elif b1_b2 >= 9999:
    print("  ERROR: B1->B2 = 9999 -- critical: adjacent Bronx zones unreachable")
else:
    print(f"  WARNING: B1->B2 = {b1_b2}s -- outside expected range [180-900s]")

print()
print("  Artifact written:")
print(f"    {MATRIX_PKL}")
print()
print("=" * 55)
print("  Next: python pipeline/07_staging_optimizer.py  (after Script 05 done)")
print("=" * 55)
