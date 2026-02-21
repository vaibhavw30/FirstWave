import numpy as np
from sklearn.cluster import KMeans

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
    def compute_staging(self, predicted_counts: dict, K: int) -> list:
        """
        Run weighted K-Means on zone centroids using predicted demand as weights.
        Returns list of dicts with staging point metadata.
        """
        zones = list(predicted_counts.keys())
        weights = np.array([max(predicted_counts.get(z, 0.01), 0.01) for z in zones])
        # coords as [lat, lon] for K-Means (geographic clustering)
        coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])

        kmeans = KMeans(n_clusters=K, random_state=42, n_init=10)
        kmeans.fit(coords, sample_weight=weights)

        labels = kmeans.labels_
        centers = kmeans.cluster_centers_  # [lat, lon]

        results = []
        for k in range(K):
            cluster_zone_indices = [i for i, lbl in enumerate(labels) if lbl == k]
            cluster_zones = [zones[i] for i in cluster_zone_indices]
            demand_coverage = sum(predicted_counts.get(z, 0) for z in cluster_zones)

            lat, lon = centers[k]
            results.append({
                "staging_index": k,
                "lat": float(lat),
                "lon": float(lon),
                "coverage_radius_m": COVERAGE_RADIUS_M,
                "predicted_demand_coverage": round(float(demand_coverage), 2),
                "cluster_zones": sorted(cluster_zones),
                "zone_count": len(cluster_zones),
            })

        # Sort by demand coverage descending
        results.sort(key=lambda x: x["predicted_demand_coverage"], reverse=True)
        for i, r in enumerate(results):
            r["staging_index"] = i

        return results
