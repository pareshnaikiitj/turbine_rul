// ---------------------------------------------------------------------------
// Turbine simulation API client.
// ---------------------------------------------------------------------------

// Vite exposes env vars prefixed with VITE_ via import.meta.env at build time.
// Falls back to localhost so local dev still works if the .env file is missing.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// max_hours is an upper bound so the simulation has enough runway to reach
// failure — the backend returns its own effective max_hours in the response,
// which is what should be displayed.
export const DEFAULT_MAX_HOURS = 2000;

/**
 * Run a fresh-turbine failure simulation.
 *
 * @param {Object} params
 * @param {number|string} params.rpm
 * @param {number|string} params.stressMpa
 * @param {number} [params.maxHours]
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<{
 *   rpm: number,
 *   stress_mpa: number,
 *   max_hours: number,
 *   estimated_operating_life_hours: number,
 *   degradation_curve: Array<{
 *     hour: number,
 *     rpm: number,
 *     stress_mpa: number,
 *     damage_increment: number,
 *     health_score: number
 *   }>
 * }>}
 */
export async function runFailureSimulation({
  rpm,
  stressMpa,
  maxHours = DEFAULT_MAX_HOURS,
  signal,
} = {}) {
  const response = await fetch(`${API_BASE_URL}/simulate-fresh-turbine`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      rpm: Number(rpm),
      stress_mpa: Number(stressMpa),
      max_hours: maxHours,
    }),
    signal,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => '');
    throw new Error(text || `Simulation request failed (${response.status})`);
  }

  const data = await response.json();

  if (!data || !Array.isArray(data.degradation_curve)) {
    throw new Error('Simulation response was missing a degradation curve');
  }

  return data;
}