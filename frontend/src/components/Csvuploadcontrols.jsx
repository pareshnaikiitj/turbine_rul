import React from 'react';

export default function CsvUploadControls({
  selectedFile,
  handleFileSelect,
  runPrediction,
  reset,
  isLoading,
  error,
  result,
}) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <div>
          <div className="panel-title">Upload Turbine CSV</div>
          <div className="panel-subtitle">
            Requires columns: unit_id, cycle, rpm, loading, time_hours, vibration, pressure
            (rul optional)
          </div>
        </div>
      </div>

      <div className="sim-controls">
        <label>
          CSV file
          <input
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            disabled={isLoading}
          />
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
    </section>
  );
}