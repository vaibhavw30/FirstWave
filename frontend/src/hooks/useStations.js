import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { API_BASE_URL, USE_MOCK_DATA } from '../constants';

const EMPTY_FC = { type: 'FeatureCollection', features: [] };

export function useStations() {
  return useQuery({
    queryKey: ['stations'],
    queryFn: async () => {
      if (USE_MOCK_DATA) return EMPTY_FC;
      const { data } = await axios.get(`${API_BASE_URL}/api/stations`);
      return data;
    },
    staleTime: 5 * 60 * 1000,
    retry: 3,
    retryDelay: 1000,
  });
}
