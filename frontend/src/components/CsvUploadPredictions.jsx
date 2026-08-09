import React from 'react';
import { useCsvRulPrediction } from '../hooks/useCsvRulPrediction';
import { useHealthThresholds } from '../hooks/useHealthThresholds';

const toneClass = {
  Healthy: 'tone-healthy',
  Warning: 'tone-watch',
  Critical: 'tone-critical',
};

export default function CsvUploadPredictions() {
  const {
    selectedFile,
    handleFileSelect,
    runPrediction,
    reset,
    isLoading,
    error,
    result,
    pagedRows,
    rows,
    page,
    totalPages,
    goToPage,
    pageSize,
  } = useCsvRulPrediction();

  const { thresholds } = useHealthThresholds();

  return (
    <section className="panel">
      <div className="panel-title-row">
        <div>
          <div className="panel-title">Predict RUL from CSV</div>
          <div className="panel-subtitle">
            Requires columns: unit_id, cycle, rpm, loading, time_hours, vibration, pressure
            (rul optional)
        </div>
        </div>
        {result ? <span className="panel-subtitle">Model: {result.model}</span> : null}
      </div>

      {thresholds ? (
        <div className="sim-controls" style={{ marginBottom: 6 }}>
          <span className="health-chip tone-critical">
            Critical · health ≤ {thresholds.health_threshold}
          </span>
          <span className="health-chip tone-watch">
            Warning · health ≤ {thresholds.warning_threshold}
          </span>
          <span className="health-chip tone-healthy">
            Healthy · health &gt; {thresholds.warning_threshold}
          </span>
        </div>
      ) : null}

      <div className="sim-controls">
        <label>
          CSV file
          <input type="file" accept=".csv" onChange={handleFileSelect} />
        </label>
        <button onClick={runPrediction} disabled={isLoading || !selectedFile}>
          {isLoading ? 'Predicting…' : 'Predict RUL'}
        </button>
        {result ? (
          <button onClick={reset} disabled={isLoading}>
            Clear
          </button>
        ) : null}
      </div>

      {selectedFile && !error ? (
        <div className="panel-subtitle" style={{ marginTop: 10 }}>
          Selected: {selectedFile.name}
        </div>
      ) : null}

      {error ? <div className="banner">{error}</div> : null}

      {result ? (
        <>
          <div className="table-wrapper" style={{ marginTop: 18 }}>
            <table>
              <thead>
                <tr>
                  <th>Unit</th>
                  <th>Cycle</th>
                  <th>RPM</th>
                  <th>Loading</th>
                  <th>Hours</th>
                  <th>Vibration</th>
                  <th>Pressure</th>
                  {result.predictions.some((r) => 'actual_rul_hours' in r) ? <th>Actual RUL</th> : null}
                  <th>Predicted RUL</th>
                  <th>Health</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {pagedRows.length ? (
                  pagedRows.map((row, i) => (
                    <tr key={`${row.unit_id}-${row.cycle}-${i}`}>
                      <td>{row.unit_id}</td>
                      <td>{row.cycle}</td>
                      <td>{row.rpm}</td>
                      <td>{row.loading}</td>
                      <td>{row.time_hours}</td>
                      <td>{row.vibration}</td>
                      <td>{row.pressure}</td>
                      {'actual_rul_hours' in row ? <td>{row.actual_rul_hours} hrs</td> : null}
                      <td>{row.predicted_rul_hours} hrs</td>
                      <td>{row.health_score}</td>
                      <td>
                        <span className={`health-chip ${toneClass[row.status] || ''}`}>{row.status}</span>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="empty-row" colSpan={11}>
                      No rows to show.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <span className="pagination__info">
              {rows.length} row{rows.length === 1 ? '' : 's'} · page {page} of {totalPages}
            </span>
            <div className="pagination__controls">
              <button className="page-button" onClick={() => goToPage(page - 1)} disabled={page <= 1}>
                ‹
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .slice(Math.max(0, page - 3), Math.max(0, page - 3) + 5)
                .map((p) => (
                  <button
                    key={p}
                    className={`page-button ${p === page ? 'active' : ''}`}
                    onClick={() => goToPage(p)}
                  >
                    {p}
                  </button>
                ))}
              <button className="page-button" onClick={() => goToPage(page + 1)} disabled={page >= totalPages}>
                ›
              </button>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}