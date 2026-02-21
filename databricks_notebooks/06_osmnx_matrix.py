# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 06 — OSMnx Drive-Time Matrix
# MAGIC **FirstWave | GT Hacklytics 2026**
# MAGIC
# MAGIC ⚠️ START THIS FIRST — takes 30–60 minutes to compute.
# MAGIC Run it immediately when the hackathon starts and let it run in background.
# MAGIC
# MAGIC Output: `dbfs:/firstwave/artifacts/drive_time_matrix.pkl`
# MAGIC         `dbfs:/firstwave/artifacts/nyc_graph.pkl`
# MAGIC         `dbfs:/firstwave/artifacts/zone_nodes.pkl`

# COMMAND ----------

# MAGIC %md ## Install OSMnx (restart kernel after)

# COMMAND ----------

# MAGIC %pip install osmnx

# COMMAND ----------

# NOTE: dbutils.library.restartPython() is NOT supported on Databricks Serverless.
# On Serverless, %pip install takes effect immediately — no restart needed.
# If you are on a Classic cluster, uncomment the line below:
# dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md ## Setup

# COMMAND ----------

import osmnx as ox
import networkx as nx
import pickle
import json
import os
import math
import numpy as np

# Serverless: no /dbfs/ local mount — use /tmp/ for Python file I/O, dbutils.fs to persist
DBFS_ARTIFACTS = "dbfs:/firstwave/artifacts"
DBFS_DATA      = "dbfs:/firstwave/data"
TMP_ARTIFACTS  = "/tmp/firstwave/artifacts"
TMP_DATA       = "/tmp/firstwave/data"

os.makedirs(TMP_ARTIFACTS, exist_ok=True)
os.makedirs(TMP_DATA, exist_ok=True)
dbutils.fs.mkdirs(DBFS_ARTIFACTS)

# COMMAND ----------

# MAGIC %md ## Constants

# COMMAND ----------

ZONE_CENTROIDS = {
    # Bronx
    'B1': (-73.9101, 40.8116),  # South Bronx, Hunts Point
    'B2': (-73.9196, 40.8448),  # West/Central Bronx
    'B3': (-73.8784, 40.8189),  # East Bronx, Soundview
    'B4': (-73.8600, 40.8784),  # North Bronx, Pelham
    'B5': (-73.9056, 40.8651),  # Riverdale, Fordham
    # Brooklyn
    'K1': (-73.9857, 40.5995),  # Southern Brooklyn, Coney Island
    'K2': (-73.9442, 40.6501),  # Park Slope, Crown Heights
    'K3': (-73.9075, 40.6929),  # Bushwick, Brownsville
    'K4': (-73.9015, 40.6501),  # East New York, Flatbush
    'K5': (-73.9283, 40.6801),  # Bed-Stuy, Ocean Hill
    'K6': (-73.9645, 40.6401),  # Borough Park, Flatbush
    'K7': (-73.9573, 40.7201),  # North Brooklyn, Williamsburg
    # Manhattan
    'M1': (-74.0060, 40.7128),  # Lower Manhattan, Financial District
    'M2': (-74.0000, 40.7484),  # Midtown South, Chelsea
    'M3': (-73.9857, 40.7580),  # Midtown, Hell's Kitchen
    'M4': (-73.9784, 40.7484),  # Murray Hill, Gramercy
    'M5': (-73.9584, 40.7701),  # Upper East Side South
    'M6': (-73.9484, 40.7884),  # Upper East Side North
    'M7': (-73.9428, 40.8048),  # Harlem, East Harlem
    'M8': (-73.9373, 40.8284),  # Washington Heights South
    'M9': (-73.9312, 40.8484),  # Washington Heights North, Inwood
    # Queens
    'Q1': (-73.7840, 40.6001),  # Far Rockaway, Jamaica
    'Q2': (-73.8284, 40.7501),  # Flushing, Bayside
    'Q3': (-73.8784, 40.7201),  # Forest Hills, Rego Park
    'Q4': (-73.9073, 40.7101),  # Ridgewood, Maspeth
    'Q5': (-73.8073, 40.6901),  # Jamaica, Hollis
    'Q6': (-73.9173, 40.7701),  # Astoria, Long Island City
    'Q7': (-73.8373, 40.7701),  # Flushing North, Whitestone
    # Staten Island
    'S1': (-74.1115, 40.6401),  # North Shore
    'S2': (-74.1515, 40.5901),  # Mid-Island
    'S3': (-74.1915, 40.5301),  # South Shore
}

VALID_ZONES = list(ZONE_CENTROIDS.keys())
print(f"ZONE_CENTROIDS loaded: {len(ZONE_CENTROIDS)} zones")

# COMMAND ----------

# MAGIC %md ## Haversine Fallback (used if OSMnx fails)

# COMMAND ----------

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
    hours = road_km / 25.0          # 25 km/h average urban speed
    return int(hours * 3600)

def build_haversine_matrix(stations=None) -> dict:
    """Build drive-time matrix using Haversine approximation as fallback."""
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

# COMMAND ----------

# MAGIC %md ## Step 1: Load EMS Stations

# COMMAND ----------

stations = []

try:
    # Copy from DBFS to /tmp/ first (Serverless has no /dbfs/ local mount)
    _stations_tmp = f"{TMP_DATA}/ems_stations.json"
    dbutils.fs.cp(f"{DBFS_DATA}/ems_stations.json", f"file:{_stations_tmp}")
    with open(_stations_tmp) as f:
        stations = json.load(f)
    print(f"Loaded {len(stations)} EMS stations from {stations_path}")
    for s in stations[:5]:
        print(f"  {s.get('station_id','?')}: {s.get('name','?')} at ({s.get('lon','?')}, {s.get('lat','?')})")
except FileNotFoundError:
    print(f"⚠️  WARNING: {stations_path} not found — using empty station list")
    print("   Ask Ansh to upload ems_stations.json to DBFS before running Notebook 08")

station_ids = [s["station_id"] for s in stations]
print(f"\n{len(stations)} EMS stations, {len(VALID_ZONES)} destination zones")
print(f"Total origins: {len(VALID_ZONES)} zones + {len(stations)} stations = {len(VALID_ZONES) + len(stations)}")

# COMMAND ----------

# MAGIC %md ## Step 2: Download NYC Road Network

# COMMAND ----------

USE_OSMNX = True  # Set to False if graph download fails repeatedly

if USE_OSMNX:
    try:
        print("Downloading NYC road network (~400MB, 5–10 min)...")
        print("This is the longest step — please wait...")

        G = ox.graph_from_place("New York City, New York, USA", network_type="drive")
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)

        print(f"\n✓ Graph downloaded!")
        print(f"  Nodes: {len(G.nodes):,}")
        print(f"  Edges: {len(G.edges):,}")

        # Save graph: write to /tmp/ then copy to DBFS (Serverless has no /dbfs/ mount)
        print("\nSaving graph to DBFS...")
        _graph_tmp = f"{TMP_ARTIFACTS}/nyc_graph.pkl"
        with open(_graph_tmp, "wb") as f:
            pickle.dump(G, f)
        dbutils.fs.cp(f"file:{_graph_tmp}", f"{DBFS_ARTIFACTS}/nyc_graph.pkl")
        print("  ✓ nyc_graph.pkl saved")

    except Exception as e:
        print(f"⚠️  OSMnx graph download failed: {e}")
        print("Falling back to Haversine approximation")
        USE_OSMNX = False
else:
    # Try to load existing graph from DBFS via /tmp/
    _graph_tmp = f"{TMP_ARTIFACTS}/nyc_graph.pkl"
    try:
        dbutils.fs.cp(f"{DBFS_ARTIFACTS}/nyc_graph.pkl", f"file:{_graph_tmp}")
        print("Loading existing graph from DBFS...")
        with open(_graph_tmp, "rb") as f:
            G = pickle.load(f)
        USE_OSMNX = True
        print(f"  ✓ Loaded: {len(G.nodes):,} nodes, {len(G.edges):,} edges")
    except Exception:
        print("No existing graph found — using Haversine fallback")

# COMMAND ----------

# MAGIC %md ## Step 3: Map Zone Centroids and EMS Stations to Road Nodes

# COMMAND ----------

if USE_OSMNX:
    print("Mapping zone centroids to nearest road nodes...")
    zone_nodes = {}
    for zone, (lon, lat) in ZONE_CENTROIDS.items():
        try:
            node_id, dist = ox.nearest_nodes(G, lon, lat, return_dist=True)
            zone_nodes[zone] = node_id
            if dist > 500:
                print(f"  ⚠️  {zone}: centroid {dist:.0f}m from nearest node (may be in water/park)")
            else:
                print(f"  {zone}: node {node_id} ({dist:.0f}m away)")
        except Exception as e:
            print(f"  ⚠️  {zone}: failed to find nearest node — {e}")

    print(f"\n✓ Mapped {len(zone_nodes)}/{len(ZONE_CENTROIDS)} zones")

    _zn_tmp = f"{TMP_ARTIFACTS}/zone_nodes.pkl"
    with open(_zn_tmp, "wb") as f:
        pickle.dump(zone_nodes, f)
    dbutils.fs.cp(f"file:{_zn_tmp}", f"{DBFS_ARTIFACTS}/zone_nodes.pkl")
    print("  zone_nodes.pkl saved")

    # Map EMS stations
    station_nodes = {}
    print(f"\nMapping {len(stations)} EMS stations to road nodes...")
    for s in stations:
        try:
            node_id = ox.nearest_nodes(G, s["lon"], s["lat"])
            station_nodes[s["station_id"]] = node_id
        except Exception as e:
            print(f"  ⚠️  {s['station_id']}: {e}")

    _sn_tmp = f"{TMP_ARTIFACTS}/station_nodes.pkl"
    with open(_sn_tmp, "wb") as f:
        pickle.dump(station_nodes, f)
    dbutils.fs.cp(f"file:{_sn_tmp}", f"{DBFS_ARTIFACTS}/station_nodes.pkl")
    print(f"  ✓ Mapped {len(station_nodes)}/{len(stations)} stations")

# COMMAND ----------

# MAGIC %md ## Step 4: Compute Drive-Time Matrix

# COMMAND ----------

if USE_OSMNX:
    all_origins = {**zone_nodes, **station_nodes}
    n_origins = len(all_origins)

    print(f"Computing drive times: {n_origins} origins × {len(VALID_ZONES)} destinations")
    print(f"Expected pairs: {n_origins * len(VALID_ZONES):,}")
    print("This takes 20–40 minutes — progress every 10 origins...\n")

    drive_time_matrix = {}
    failed = []

    for i, (origin_key, origin_node) in enumerate(all_origins.items()):
        try:
            # Single-source Dijkstra: much faster than per-pair calls
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
            print(f"  WARN: {origin_key} failed: {e}")
            for dest_zone in VALID_ZONES:
                drive_time_matrix[(origin_key, dest_zone)] = 9999

        if (i + 1) % 10 == 0:
            pct = (i + 1) / n_origins * 100
            print(f"  Progress: {i+1}/{n_origins} ({pct:.0f}%) origins complete")

    print(f"\n✓ Matrix complete: {len(drive_time_matrix):,} pairs")
    if failed:
        print(f"  ⚠️  Failed origins: {failed}")
        # Fill failed OSMnx entries with Haversine approximations
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
    print("Using Haversine fallback matrix (OSMnx not available)")
    drive_time_matrix = build_haversine_matrix(stations)
    print("⚠️  Note: Tell the team — counterfactual numbers will be ~15% less accurate")

# COMMAND ----------

# MAGIC %md ## Step 5: Save Matrix to DBFS

# COMMAND ----------

_matrix_tmp = f"{TMP_ARTIFACTS}/drive_time_matrix.pkl"
with open(_matrix_tmp, "wb") as f:
    pickle.dump(drive_time_matrix, f)
dbutils.fs.cp(f"file:{_matrix_tmp}", f"{DBFS_ARTIFACTS}/drive_time_matrix.pkl")

print(f"✓ drive_time_matrix.pkl saved to {DBFS_ARTIFACTS}/drive_time_matrix.pkl")
print(f"  Pairs: {len(drive_time_matrix):,}")

# COMMAND ----------

# MAGIC %md ## Step 6: Validation

# COMMAND ----------

print("=" * 55)
print("  NOTEBOOK 06 — VALIDATION")
print("=" * 55)
print(f"  Matrix size: {len(drive_time_matrix):,} pairs")
print()

# Sample drive times
sample = [
    ('B1', 'B2'),  # Adjacent Bronx — expect 300–500s
    ('B1', 'M7'),  # Bronx to Harlem — expect 600–1000s
    ('M3', 'K4'),  # Midtown to East Brooklyn — expect 1200–2000s
    ('S1', 'B1'),  # Staten Island to South Bronx — expect 2000–4000s
    ('Q2', 'M7'),  # Flushing to Harlem — expect 1500–2500s
]

print("  Sample drive times (OSMnx/Haversine):")
for o, d in sample:
    t = drive_time_matrix.get((o, d), None)
    if t is not None and t < 9999:
        print(f"  {o} → {d}: {t:4d} sec ({t/60:.1f} min)")
    else:
        print(f"  {o} → {d}: ⚠️  NOT FOUND (9999)")

print()

# Reachability check
unreachable = sum(1 for v in drive_time_matrix.values() if v >= 9999)
reachable_pct = (len(drive_time_matrix) - unreachable) / len(drive_time_matrix) * 100
print(f"  Reachable pairs:   {len(drive_time_matrix) - unreachable:,} ({reachable_pct:.1f}%)")
print(f"  Unreachable (9999): {unreachable:,}")

if reachable_pct < 90:
    print("  ⚠️  WARNING: < 90% reachable — OSMnx graph may have disconnected components")
    print("  ⚠️  Consider: run Haversine fallback for the full matrix")
else:
    print("  ✓ Reachability OK")

# B1→B2 sanity check
b1_b2 = drive_time_matrix.get(('B1','B2'), 9999)
if 180 <= b1_b2 <= 900:
    print(f"  ✓ B1→B2 = {b1_b2}s — reasonable adjacent-zone drive time")
elif b1_b2 >= 9999:
    print("  ⚠️  B1→B2 = 9999 — critical error: adjacent Bronx zones unreachable")
else:
    print(f"  ⚠️  B1→B2 = {b1_b2}s — outside expected range [180–900s]")

# Station coverage check
if stations:
    station_coverage = sum(
        1 for s in stations
        if any(drive_time_matrix.get((s["station_id"], z), 9999) < 9999 for z in VALID_ZONES)
    )
    print(f"\n  Station coverage: {station_coverage}/{len(stations)} stations reach at least 1 zone")

print()
print(f"  Matrix file: {matrix_path}")
print()
print("  → Download drive_time_matrix.pkl and commit to backend/artifacts/")
print("  → Post in group chat: drive_time_matrix.pkl AVAILABLE")
print("=" * 55)
