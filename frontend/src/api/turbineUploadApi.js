// ---------------------------------------------------------------------------
// Turbine CSV upload → RUL prediction API client.
// ---------------------------------------------------------------------------

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Upload a CSV of turbine readings and get a predicted RUL per row.
 *
 * @param {Object} params
 * @param {File} params.file
 * @param {AbortSignal} [params.signal]
 * @returns {Promise<{
 *   filename: string,
 *   model: string,
 *   row_count: number,
 *   predictions: Array<{
 *     unit_id: number, cycle: number, rpm: number, temperature: number,
 *     loading: number, time_hours: number, vibration: number, pressure: number,
 *     actual_rul_hours?: number, predicted_rul_hours: number,
 *     health_score: number, status: 'Healthy'|'Watch'|'Critical'
 *   }>
 * }>}
 */
export async function uploadCsvForPrediction({ file, signal } = {}) {
  if (!file) {
    throw new Error('No file selected.');
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE_URL}/predict-csv`, {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    let detail = '';
    try {
      const body = await response.json();
      detail = body?.detail || '';
    } catch {
      detail = await response.text().catch(() => '');
    }
    throw new Error(detail || `Upload failed (${response.status})`);
  }

  const data = await response.json();
  if (!data || !Array.isArray(data.predictions)) {
    throw new Error('Prediction response was missing results.');
  }
  return data;
}