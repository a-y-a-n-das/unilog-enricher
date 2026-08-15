import { apiClient, ApiError, isApiError } from './client';
import type { HealthResponse } from '../types/api';

export const healthApi = {
  async checkHealth(): Promise<HealthResponse> {
    try {
      return await apiClient.get<HealthResponse>('/health');
    } catch (error) {
      if (isApiError(error)) {
        return {
          status: 'down',
          timestamp: new Date().toISOString(),
        };
      }
      return {
        status: 'down',
        timestamp: new Date().toISOString(),
      };
    }
  },
};

export { ApiError, isApiError };