import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import mockData from '../../../data/mock_api_responses.json';
import { API_BASE_URL, USE_MOCK_DATA } from '../constants';

export function useCounterfactual({ hour, dow, month, temperature, precipitation, windspeed, ambulances }) {
  return useQuery({
    queryKey: ['counterfactual', hour, dow, month, temperature, precipitation, windspeed, ambulances],
    queryFn: async () => {
      if (USE_MOCK_DATA) return mockData.counterfactual;
      try {
        const { data } = await axios.get(`${API_BASE_URL}/api/counterfactual`, {
          params: { hour, dow, month, temperature, precipitation, windspeed, ambulances },
        });
        return data;
      } catch (err) {
        console.warn('API error, falling back to mock:', err.message);
        return mockData.counterfactual;
      }
    },
  });
}
