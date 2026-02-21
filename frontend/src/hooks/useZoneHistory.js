import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import mockData from '../../../data/mock_api_responses.json';
import { API_BASE_URL, USE_MOCK_DATA, ZONE_NAMES, ZONE_SVI, ZONE_BOROUGH } from '../constants';

export function useZoneHistory(zone) {
  return useQuery({
    queryKey: ['historical', zone],
    queryFn: async () => {
      const withZoneInfo = (base) => ({
        ...base,
        zone,
        zone_name: ZONE_NAMES[zone] || base.zone_name,
        borough: ZONE_BOROUGH[zone] || base.borough,
        svi_score: ZONE_SVI[zone] ?? base.svi_score,
      });
      if (USE_MOCK_DATA) return withZoneInfo(mockData.historical_zone);
      try {
        const { data } = await axios.get(`${API_BASE_URL}/api/historical/${zone}`);
        return data;
      } catch (err) {
        console.warn('API error, falling back to mock:', err.message);
        return withZoneInfo(mockData.historical_zone);
      }
    },
    enabled: !!zone,
  });
}
