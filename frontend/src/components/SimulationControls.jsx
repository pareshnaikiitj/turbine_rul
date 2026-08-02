import React from 'react';

export default function SimulationControls({ form, onChange, onSimulate, isLoading, error }) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <span className="panel-title">Simulation Controls</span>
        <span className="panel-subtitle">Fresh-turbine failure simulation inputs</span>
      </div>
      <div className="sim-controls">
        <label>
          RPM
          <input name="rpm" value={form.rpm} onChange={onChange} type="number" />
        </label>
        <label>
          Stress (MPa)
          <input name="stress_mpa" value={form.stress_mpa} onChange={onChange} step="0.1" type="number" />
        </label>
        <button type="button" disabled={isLoading} onClick={onSimulate}>
          {isLoading ? 'Simulating...' : 'Simulate Failure'}
        </button>
      </div>
      {error ? <p className="banner">{error}</p> : null}
    </section>
  );
}
