"""
Gap-free (zone × local hour) grid with past-only lag features, built in DuckDB.

The grid has exactly one row per zone per naive local hour (24 per day, DST days
included), so a window-function row offset of N equals exactly N hours. The
backend recomputes the same lags by timestamp arithmetic in
backend/models/lag_features.py; pipeline/tests/test_lag_parity.py pins them equal.
"""
import datetime as dt

# feature name -> hour offsets averaged (a single offset is a plain lag)
LAG_SPECS = {
    "lag_1h": [1],
    "lag_2h": [2],
    "lag_3h": [3],
    "lag_24h": [24],
    "lag_168h": [168],
    "roll_7d_same_hour": [24 * k for k in range(1, 8)],
    "roll_4w_same_hour_dow": [168 * k for k in range(1, 5)],
}


def _lag_expr(offsets: list[int]) -> str:
    terms = [f"LAG(incident_count, {h}) OVER w" for h in offsets]
    if len(terms) == 1:
        return terms[0]
    return f"({' + '.join(terms)}) / {float(len(terms))}"


def create_counts(conn, cleaned_path: str) -> None:
    conn.execute(f"""
        CREATE OR REPLACE TABLE counts AS
        SELECT INCIDENT_DISPATCH_AREA, date_hour, COUNT(*)::INTEGER AS incident_count
        FROM read_parquet('{cleaned_path}')
        GROUP BY INCIDENT_DISPATCH_AREA, date_hour
    """)


def create_grid(conn, zones: list[str], start: dt.date, end: dt.date) -> int:
    zone_list = ", ".join(f"'{z}'" for z in zones)
    conn.execute(f"""
        CREATE OR REPLACE TABLE grid AS
        SELECT z.INCIDENT_DISPATCH_AREA, h.date_hour,
               COALESCE(c.incident_count, 0) AS incident_count
        FROM (SELECT UNNEST([{zone_list}]) AS INCIDENT_DISPATCH_AREA) z
        CROSS JOIN (
            SELECT generate_series AS date_hour
            FROM generate_series(TIMESTAMP '{start} 00:00:00',
                                 TIMESTAMP '{end} 23:00:00', INTERVAL 1 HOUR)
        ) h
        LEFT JOIN counts c
          ON c.INCIDENT_DISPATCH_AREA = z.INCIDENT_DISPATCH_AREA
         AND c.date_hour = h.date_hour
    """)
    expected = len(zones) * ((end - start).days + 1) * 24
    n = conn.execute("SELECT COUNT(*) FROM grid").fetchone()[0]
    n_distinct = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT INCIDENT_DISPATCH_AREA, date_hour FROM grid)"
    ).fetchone()[0]
    if n != expected or n_distinct != expected:
        raise AssertionError(f"grid not gap-free: {n} rows, {n_distinct} distinct, expected {expected}")
    return n


def add_lags(conn) -> None:
    lag_cols = ",\n            ".join(f"{_lag_expr(offs)} AS {name}" for name, offs in LAG_SPECS.items())
    conn.execute(f"""
        CREATE OR REPLACE TABLE grid_lags AS
        SELECT *,
            {lag_cols}
        FROM grid
        WINDOW w AS (PARTITION BY INCIDENT_DISPATCH_AREA ORDER BY date_hour)
    """)
