import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const apiService = {
  // Health check
  async checkHealth() {
    const response = await api.get('/health');
    return response.data;
  },

  // Get all areas
  async getAreas() {
    const response = await api.get('/api/v1/areas');
    return response.data;
  },

  // Get specific area
  async getArea(areaId) {
    const response = await api.get(`/api/v1/areas/${areaId}`);
    return response.data;
  },

  // Plan a route
  async planRoute(params) {
    const response = await api.post('/api/v1/routes/plan', params);
    return response.data;
  },

  // Get route by ID
  async getRoute(routeId) {
    const response = await api.get(`/api/v1/routes/${routeId}`);
    return response.data;
  },

  // Export route
  async exportRoute(routeId, format = 'gpx') {
    const response = await api.get(`/api/v1/routes/${routeId}/export`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },
};

export default api;
