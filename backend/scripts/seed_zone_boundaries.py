"""
seed_zone_boundaries.py
Populates PostGIS dispatch_zone_boundaries table with Shapely-buffered
circular polygon approximations for each of the 31 NYC EMS dispatch zones.

Run once after starting the PostGIS container:
    python backend/scripts/seed_zone_boundaries.py
"""

import os
import sys
from pathlib import Path

# Allow running from repo root or backend/ directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import psycopg2
from shapely.geometry import Point, mapping
from shapely import to_wkb
import json

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pp_user:pp_pass@localhost:5432/firstwave")

# (longitude, latitude) — from CLAUDE.md
ZONE_CENTROIDS = {
    'B1': (-73.9101, 40.8116),
    'B2': (-73.9196, 40.8448),
    'B3': (-73.8784, 40.8189),
    'B4': (-73.8600, 40.8784),
    'B5': (-73.9056, 40.8651),
    'K1': (-73.9857, 40.5995),
    'K2': (-73.9442, 40.6501),
    'K3': (-73.9075, 40.6929),
    'K4': (-73.9015, 40.6501),
    'K5': (-73.9283, 40.6801),
    'K6': (-73.9645, 40.6401),
    'K7': (-73.9573, 40.7201),
    'M1': (-74.0060, 40.7128),
    'M2': (-74.0000, 40.7484),
    'M3': (-73.9857, 40.7580),
    'M4': (-73.9784, 40.7484),
    'M5': (-73.9584, 40.7701),
    'M6': (-73.9484, 40.7884),
    'M7': (-73.9428, 40.8048),
    'M8': (-73.9373, 40.8284),
    'M9': (-73.9312, 40.8484),
    'Q1': (-73.7840, 40.6001),
    'Q2': (-73.8284, 40.7501),
    'Q3': (-73.8784, 40.7201),
    'Q4': (-73.9073, 40.7101),
    'Q5': (-73.8073, 40.6901),
    'Q6': (-73.9173, 40.7701),
    'Q7': (-73.8373, 40.7701),
    'S1': (-74.1115, 40.6401),
    'S2': (-74.1515, 40.5901),
    'S3': (-74.1915, 40.5301),
}

ZONE_NAMES = {
    'B1': 'South Bronx', 'B2': 'West/Central Bronx', 'B3': 'East Bronx',
    'B4': 'North Bronx', 'B5': 'Riverdale',
    'K1': 'Southern Brooklyn', 'K2': 'Park Slope', 'K3': 'Bushwick',
    'K4': 'East New York', 'K5': 'Bed-Stuy', 'K6': 'Borough Park', 'K7': 'Williamsburg',
    'M1': 'Lower Manhattan', 'M2': 'Midtown South', 'M3': 'Midtown',
    'M4': 'Murray Hill', 'M5': 'Upper East Side S', 'M6': 'Upper East Side N',
    'M7': 'Harlem', 'M8': 'Washington Heights S', 'M9': 'Washington Heights N',
    'Q1': 'Far Rockaway', 'Q2': 'Flushing', 'Q3': 'Forest Hills',
    'Q4': 'Ridgewood', 'Q5': 'Jamaica', 'Q6': 'Astoria', 'Q7': 'Whitestone',
    'S1': 'North Shore SI', 'S2': 'Mid-Island SI', 'S3': 'South Shore SI',
}

ZONE_BOROUGH = {
    'B1': 'BRONX', 'B2': 'BRONX', 'B3': 'BRONX', 'B4': 'BRONX', 'B5': 'BRONX',
    'K1': 'BROOKLYN', 'K2': 'BROOKLYN', 'K3': 'BROOKLYN', 'K4': 'BROOKLYN',
    'K5': 'BROOKLYN', 'K6': 'BROOKLYN', 'K7': 'BROOKLYN',
    'M1': 'MANHATTAN', 'M2': 'MANHATTAN', 'M3': 'MANHATTAN', 'M4': 'MANHATTAN',
    'M5': 'MANHATTAN', 'M6': 'MANHATTAN', 'M7': 'MANHATTAN', 'M8': 'MANHATTAN', 'M9': 'MANHATTAN',
    'Q1': 'QUEENS', 'Q2': 'QUEENS', 'Q3': 'QUEENS', 'Q4': 'QUEENS',
    'Q5': 'QUEENS', 'Q6': 'QUEENS', 'Q7': 'QUEENS',
    'S1': 'RICHMOND / STATEN ISLAND', 'S2': 'RICHMOND / STATEN ISLAND', 'S3': 'RICHMOND / STATEN ISLAND',
}

SVI_SCORES = {
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79, 'K6': 0.60, 'K7': 0.45,
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67, 'Q6': 0.48, 'Q7': 0.41,
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28,
}

# Buffer radius in degrees (~2km for most boroughs, smaller for dense Manhattan)
BUFFER_RADIUS = {
    'B': 0.022,  # Bronx
    'K': 0.020,  # Brooklyn
    'M': 0.015,  # Manhattan (denser)
    'Q': 0.022,  # Queens
    'S': 0.025,  # Staten Island (larger, less dense)
}

CREATE_TABLE_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS dispatch_zone_boundaries (
    zone_code VARCHAR(3) PRIMARY KEY,
    zone_name VARCHAR(100),
    borough VARCHAR(50),
    svi_score FLOAT,
    centroid_lat FLOAT,
    centroid_lon FLOAT,
    geom GEOMETRY(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS idx_dzb_geom ON dispatch_zone_boundaries USING GIST (geom);
"""

INSERT_SQL = """
INSERT INTO dispatch_zone_boundaries
    (zone_code, zone_name, borough, svi_score, centroid_lat, centroid_lon, geom)
VALUES
    (%s, %s, %s, %s, %s, %s, ST_Multi(ST_GeomFromText(%s, 4326)))
ON CONFLICT (zone_code) DO UPDATE SET
    zone_name = EXCLUDED.zone_name,
    borough = EXCLUDED.borough,
    svi_score = EXCLUDED.svi_score,
    centroid_lat = EXCLUDED.centroid_lat,
    centroid_lon = EXCLUDED.centroid_lon,
    geom = EXCLUDED.geom;
"""


def make_polygon_wkt(lon: float, lat: float, radius: float) -> str:
    """Create a circular polygon approximation as WKT around the given centroid."""
    point = Point(lon, lat)
    poly = point.buffer(radius, resolution=32)
    coords = list(poly.exterior.coords)
    coord_str = ", ".join(f"{x} {y}" for x, y in coords)
    return f"POLYGON(({coord_str}))"


def main():
    print(f"Connecting to {DATABASE_URL}...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        print("Make sure PostGIS container is running:")
        print("  docker run --name firstwave-db -e POSTGRES_DB=firstwave -e POSTGRES_USER=pp_user -e POSTGRES_PASSWORD=pp_pass -p 5432:5432 -d postgis/postgis:15-3.4")
        sys.exit(1)

    cur = conn.cursor()

    print("Creating table and index...")
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    print(f"Seeding {len(ZONE_CENTROIDS)} zone boundaries...")
    inserted = 0
    for zone_code, (lon, lat) in ZONE_CENTROIDS.items():
        prefix = zone_code[0]
        radius = BUFFER_RADIUS.get(prefix, 0.022)
        wkt = make_polygon_wkt(lon, lat, radius)

        cur.execute(INSERT_SQL, (
            zone_code,
            ZONE_NAMES[zone_code],
            ZONE_BOROUGH[zone_code],
            SVI_SCORES[zone_code],
            lat,
            lon,
            wkt,
        ))
        inserted += 1
        print(f"  ✓ {zone_code} ({ZONE_NAMES[zone_code]})")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nDone. Inserted/updated {inserted} zone boundaries.")


if __name__ == "__main__":
    main()
