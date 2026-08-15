import { useState, useEffect, useCallback } from 'react';
import { healthApi } from '../api/health';
import type { HealthResponse } from '../types/api';

export function useHealthCheck(intervalMs = 30000) {
  const [healthStatus, setHealthStatus] = useState<HealthResponse['status']>('checking');

  const checkHealth = useCallback(async () => {
    try {
      const response = await healthApi.checkHealth();
      setHealthStatus(response.status);
    } catch {
      setHealthStatus('down');
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, intervalMs);
    return () => clearInterval(interval);
  }, [checkHealth, intervalMs]);

  return { healthStatus, checkHealth };
}