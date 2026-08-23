// ---------------------------------------------------------------------------
// Turbine health-threshold config API client.
// ---------------------------------------------------------------------------

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * @returns {Promise<{
 *   health_threshold: number,
 *   warning_threshold: number,
 *   failure_threshold: number,
 *   life_scale_hours: number
 * }>}
 */
export async function fetchHealthThresholds({ signal } = {}) {
  const response = await fetch(`${API_BASE_URL}/config/thresholds`, { signal });
  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(text || `Thresholds request failed (${response.status})`);
  }
  return response.json();
}