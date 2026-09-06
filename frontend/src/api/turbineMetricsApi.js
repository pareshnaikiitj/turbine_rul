// ---------------------------------------------------------------------------
// Turbine model metrics API client.
// ---------------------------------------------------------------------------

// Vite exposes env vars prefixed with VITE_ via import.meta.env at build time.
// Falls back to localhost so local dev still works if the .env file is missing.
import { API_BASE_URL } from './apiBaseUrl';

/**
 * Fetch the trained model's headline metrics (model name, test MAE, test
 * RMSE, R² score) for the dashboard's stat cards.
 *
 * @param {Object} [params]
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<{
 *   model: string,
 *   test_mae_hours: number,
 *   test_rmse_hours: number,
 *   r2_score: number
 * }>}
 */
export async function fetchModelMetrics({ signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/metrics`, { signal });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(text || `Metrics request failed (${response.status})`);
  }

  const data = await response.json();

  if (!data || typeof data.model !== 'string') {
    throw new Error('Metrics response was missing expected fields');
  }

  return data;
}