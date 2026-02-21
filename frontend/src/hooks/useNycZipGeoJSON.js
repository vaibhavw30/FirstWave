import { useQuery } from '@tanstack/react-query';

const NYC_ZIP_URLS = [
  'https://data.cityofnewyork.us/api/geospatial/i8iw-xf4u?method=export&type=GeoJSON',
  'https://raw.githubusercontent.com/fedhere/PUI2015_EC/master/mam1612_EC/nyc-zip-code-tabulation-areas-polygons.geojson',
];

async function fetchZipGeoJSON() {
  for (const url of NYC_ZIP_URLS) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const geojson = await res.json();
      if (geojson?.type === 'FeatureCollection' && geojson.features?.length > 0) {
        return geojson;
      }
    } catch {
      // try next URL
    }
  }
  return null;
}

export function useNycZipGeoJSON() {
  return useQuery({
    queryKey: ['nyc-zip-geojson'],
    queryFn: fetchZipGeoJSON,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  });
}
