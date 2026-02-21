import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import mockData from '../../../data/mock_api_responses.json';
import { API_BASE_URL, USE_MOCK_DATA, STAGING_ZONE_COUNT } from '../constants';

export function useStaging(params) {
  return useQuery({
    queryKey: ['staging', { ...params, ambulances: STAGING_ZONE_COUNT }],
    queryFn: async () => {
      if (USE_MOCK_DATA) return mockData.staging;
      try {
        const { data } = await axios.get(`${API_BASE_URL}/api/staging`, {
          params: { ...params, ambulances: STAGING_ZONE_COUNT },
        });
        return data;
      } catch (err) {
        console.warn('API error, falling back to mock:', err.message);
        return mockData.staging;
      }
    },
    enabled: params.hour !== undefined,
  });
}
