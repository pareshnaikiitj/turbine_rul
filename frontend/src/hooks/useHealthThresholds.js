import { useEffect, useState } from 'react';
import { fetchHealthThresholds } from '../api/turbineConfigApi';

export function useHealthThresholds() {
  const [thresholds, setThresholds] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const data = await fetchHealthThresholds({ signal: controller.signal });
        setThresholds(data);
      } catch (apiError) {
        if (apiError.name !== 'AbortError') setError(apiError.message || 'Unable to load thresholds.');
      }
    })();
    return () => controller.abort();
  }, []);

  return { thresholds, error };
}