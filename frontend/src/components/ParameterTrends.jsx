import React, { useMemo, useState } from 'react';
import LineChart from './charts/LineChart';

const PARAMETERS = [
  { key: 'rpm', label: 'RPM', unitSuffix: '', yLabel: 'RPM' },
  { key: 'stress_mpa', label: 'Stress', unitSuffix: ' MPa', yLabel: 'MPa' },
  { key: 'loading', label: 'Loading', unitSuffix: '', yLabel: 'ratio' },
  { key: 'vibration', label: 'Vibration', unitSuffix: '', yLabel: 'ratio' },
  { key: 'pressure', label: 'Pressure', unitSuffix: '', yLabel: 'ratio' },
];

// Validated 8-hue categorical palette (dark surface) — fixed slot order,
// never cycled/reassigned per filter, so a unit keeps its color everywhere.
const PALETTE = [
  '#3987e5', // blue
  '#d95926', // orange
  '#199e70', // aqua
  '#c98500', // yellow
  '#d55181', // magenta
  '#008300', // green
  '#9085e9', // violet
  '#e66767', // red
];

/**
 * Sensor-trend panel: RPM, stress, loading, vibration, and pressure across
 * cycles for one turbine unit at a time. Reads straight from the CSV
 * prediction rows so it fills in the moment a CSV is scored.
 */
export default function ParameterTrends({ rows }) {
  const unitIds = useMemo(
    () => [...new Set((rows || []).map((r) => r.unit_id))].sort((a, b) => a - b),
    [rows]
  );

  const colorForUnit = (unitId) => PALETTE[unitIds.indexOf(unitId) % PALETTE.length];

  const [selectedUnit, setSelectedUnit] = useState(null);
  const activeUnit = selectedUnit ?? unitIds[0] ?? null;

  const unitRows = useMemo(() => {
    if (activeUnit === null) return [];
    return (rows || [])
      .filter((r) => r.unit_id === activeUnit)
      .sort((a, b) => a.cycle - b.cycle);
  }, [rows, activeUnit]);

  const activeSeries = activeUnit === null ? [] : [{
    id: activeUnit,
    label: `Unit ${activeUnit}`,
    color: colorForUnit(activeUnit),
    data: unitRows,
  }];

  return (
    <section className="panel">
      <div className="panel-title-row">
        <div>
          <div className="panel-title">Parameter Trends</div>
          <div className="panel-subtitle">RPM, stress, loading, vibration &amp; pressure across cycles</div>
        </div>
        {unitIds.length > 1 ? (
          <label className="chart-unit-select">
            Unit
            <select value={activeUnit ?? ''} onChange={(e) => setSelectedUnit(Number(e.target.value))}>
              {unitIds.map((id) => (
                <option key={id} value={id}>Unit {id}</option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      {unitRows.length ? (
        <div className="chart-grid">
          {PARAMETERS.map((param) => (
            <div key={param.key} className="chart-card">
              <div className="chart-card__title">{param.label}</div>
              <LineChart
                series={activeSeries}
                xKey="cycle"
                yKey={param.key}
                xLabel="Cycle"
                yLabel={param.yLabel}
                unitSuffix={param.unitSuffix}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="panel-subtitle">Upload and predict a CSV above to see sensor trends here.</div>
      )}
    </section>
  );
}