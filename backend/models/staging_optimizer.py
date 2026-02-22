import numpy as np
from sklearn.cluster import KMeans

ZONE_BOROUGH_PREFIX = {
    'B': 'BRONX',
    'K': 'BROOKLYN',
    'M': 'MANHATTAN',
    'Q': 'QUEENS',
    'S': 'RICHMOND / STATEN ISLAND',
}

ZONE_CENTROIDS = {
    # Bronx — (longitude, latitude)
    'B1': (-73.9101, 40.8116),
    'B2': (-73.9196, 40.8448),
    'B3': (-73.8784, 40.8189),
    'B4': (-73.8600, 40.8784),
    'B5': (-73.9056, 40.8651),
    # Brooklyn
    'K1': (-73.9857, 40.5995),
    'K2': (-73.9442, 40.6501),
    'K3': (-73.9075, 40.6929),
    'K4': (-73.9015, 40.6501),
    'K5': (-73.9283, 40.6801),
    'K6': (-73.9645, 40.6401),
    'K7': (-73.9573, 40.7201),
    # Manhattan
    'M1': (-74.0060, 40.7128),
    'M2': (-74.0000, 40.7484),
    'M3': (-73.9857, 40.7580),
    'M4': (-73.9784, 40.7484),
    'M5': (-73.9584, 40.7701),
    'M6': (-73.9484, 40.7884),
    'M7': (-73.9428, 40.8048),
    'M8': (-73.9373, 40.8284),
    'M9': (-73.9312, 40.8484),
    # Queens
    'Q1': (-73.7840, 40.6001),
    'Q2': (-73.8284, 40.7501),
    'Q3': (-73.8784, 40.7201),
    'Q4': (-73.9073, 40.7101),
    'Q5': (-73.8073, 40.6901),
    'Q6': (-73.9173, 40.7701),
    'Q7': (-73.8373, 40.7701),
    # Staten Island
    'S1': (-74.1115, 40.6401),
    'S2': (-74.1515, 40.5901),
    'S3': (-74.1915, 40.5301),
}

COVERAGE_RADIUS_M = 3500


class StagingOptimizer:
    def _borough_of(self, zone: str) -> str:
        return ZONE_BOROUGH_PREFIX.get(zone[0], 'UNKNOWN')

    def _demand_weighted_centroid(self, zones: list, predicted_counts: dict):
        """Compute demand-weighted centroid for a list of zones. Returns (lat, lon)."""
        weights = np.array([max(predicted_counts.get(z, 0.01), 0.01) for z in zones])
        coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])
        total_w = weights.sum()
        lat = np.dot(weights, coords[:, 0]) / total_w
        lon = np.dot(weights, coords[:, 1]) / total_w
        return float(lat), float(lon)

    def _build_result(self, idx, lat, lon, cluster_zones, predicted_counts):
        demand_coverage = sum(predicted_counts.get(z, 0) for z in cluster_zones)
        return {
            "staging_index": idx,
            "lat": lat,
            "lon": lon,
            "coverage_radius_m": COVERAGE_RADIUS_M,
            "predicted_demand_coverage": round(float(demand_coverage), 2),
            "cluster_zones": sorted(cluster_zones),
            "zone_count": len(cluster_zones),
        }

    def compute_staging(self, predicted_counts: dict, K: int) -> list:
        """
        Borough-fair staging: guarantees each borough gets at least 1 staging
        point before any borough gets 2+, then extras split by demand.
        """
        # Group zones by borough
        borough_zones = {}
        for z in predicted_counts:
            b = self._borough_of(z)
            borough_zones.setdefault(b, []).append(z)

        borough_demand = {
            b: sum(predicted_counts.get(z, 0) for z in zs)
            for b, zs in borough_zones.items()
        }
        # Boroughs ranked by demand descending
        ranked_boroughs = sorted(borough_demand, key=borough_demand.get, reverse=True)
        num_boroughs = len(ranked_boroughs)

        if K < num_boroughs:
            # Fewer ambulances than boroughs: pick top K boroughs by demand
            selected = ranked_boroughs[:K]
            results = []
            for i, b in enumerate(selected):
                lat, lon = self._demand_weighted_centroid(borough_zones[b], predicted_counts)
                results.append(self._build_result(i, lat, lon, borough_zones[b], predicted_counts))
        else:
            # Phase 1: one staging point per borough (guaranteed)
            results = []
            borough_clusters = {}  # borough -> number of clusters allocated
            for b in ranked_boroughs:
                borough_clusters[b] = 1

            # Phase 2: distribute K - num_boroughs extras by demand
            extras = K - num_boroughs
            for _ in range(extras):
                # Give next extra to borough with highest demand-per-cluster ratio
                best_b = max(
                    ranked_boroughs,
                    key=lambda b: borough_demand[b] / borough_clusters[b]
                )
                borough_clusters[best_b] += 1

            # Build staging points: for boroughs with 1 cluster use weighted centroid,
            # for boroughs with >1 cluster run K-Means within that borough
            idx = 0
            for b in ranked_boroughs:
                n_clusters = borough_clusters[b]
                zones_in_borough = borough_zones[b]

                if n_clusters == 1 or len(zones_in_borough) <= 1:
                    lat, lon = self._demand_weighted_centroid(zones_in_borough, predicted_counts)
                    results.append(self._build_result(idx, lat, lon, zones_in_borough, predicted_counts))
                    idx += 1
                else:
                    # K-Means within this borough
                    n_clusters = min(n_clusters, len(zones_in_borough))
                    weights = np.array([max(predicted_counts.get(z, 0.01), 0.01) for z in zones_in_borough])
                    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones_in_borough])

                    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    km.fit(coords, sample_weight=weights)

                    for k in range(n_clusters):
                        cluster_zone_indices = [i for i, lbl in enumerate(km.labels_) if lbl == k]
                        cluster_zones = [zones_in_borough[i] for i in cluster_zone_indices]
                        lat, lon = km.cluster_centers_[k]
                        results.append(self._build_result(idx, lat, lon, cluster_zones, predicted_counts))
                        idx += 1

        # Sort by demand coverage descending
        results.sort(key=lambda x: x["predicted_demand_coverage"], reverse=True)
        for i, r in enumerate(results):
            r["staging_index"] = i

        return results
