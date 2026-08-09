import { useEffect, useRef, useState } from 'react';
import { fetchModelMetrics } from '../api/turbineMetricsApi';

/**
 * Fetches the trained model's headline metrics on mount and exposes them
 * as ready-to-render stat cards. Import this hook anywhere you want the
 * dashboard's MODEL / TEST MAE / TEST RMSE / R² cards without re-wiring
 * the API call.
 */
export function useModelMetrics() {
  const [metrics, setMetrics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const abortRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      setIsLoading(true);
      setError('');
      try {
        const data = await fetchModelMetrics({ signal: controller.signal });
        setMetrics(data);
      } catch (apiError) {
        if (apiError.name !== 'AbortError') {
          setError(apiError.message || 'Unable to reach the metrics API.');
          setMetrics(null);
        }
      } finally {
        if (!controller.signal.aborted) setIsLoading(false);
      }
    })();

    // Cancel any in-flight request if the component using this hook unmounts.
    return () => controller.abort();
  }, []);

  const metricCards = metrics
    ? [
        { label: 'MODEL', value: metrics.model },
        { label: 'TEST MAE', value: `${metrics.test_mae_hours} hrs` },
        { label: 'TEST RMSE', value: `${metrics.test_rmse_hours} hrs` },
        { label: 'R² SCORE', value: metrics.r2_score.toFixed(4) },
      ]
    : [
        { label: 'MODEL', value: isLoading ? '…' : '—' },
        { label: 'TEST MAE', value: isLoading ? '…' : '—' },
        { label: 'TEST RMSE', value: isLoading ? '…' : '—' },
        { label: 'R² SCORE', value: isLoading ? '…' : '—' },
      ];

  return { metrics, metricCards, isLoading, error };
}