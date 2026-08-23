import React from 'react';
import { useTurbineSimulation } from '../hooks/useTurbineSimulation';
import { useModelMetrics } from '../hooks/useModelMetrics';
import { useCsvRulPrediction } from '../hooks/useCsvRulPrediction';
import SimulationControls from './SimulationControls';
import SimulationResults from './SimulationResults';
import CsvUploadControls from './CsvUploadcontrols';
import CsvUploadPredictions from './CsvUploadPredictions';
import ParameterTrends from './ParameterTrends';

export default function TurbineRulDashboard() {
  const sim = useTurbineSimulation();
  const { metricCards, error: metricsError } = useModelMetrics();
  const csv = useCsvRulPrediction();

  return (
    <div className="dashboard-shell">
      <header className="top-bar">
        <div className="top-bar__left">
          <span className="brand-icon">◌</span>
          <span className="brand-label">Turbine RUL Dashboard</span>
        </div>
      </header>

      <section className="hero-panel">
        <div className="hero-panel__title-row">
          <span className="level-badge">M25DE2039 TURBINE BLADE RUL</span>
        </div>
        <h1>Remaining Useful Life Console</h1>
        <p>ML predictions, SLMTA15 fatigue model &amp; degradation trajectory</p>
        <div className="cycle-pills">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((item) => (
            <span key={item} className={item === 1 ? 'pill active' : 'pill'}>
              {item}
            </span>
          ))}
        </div>
      </section>

      <section className="stats-grid">
        {metricCards.map((card) => (
          <article key={card.label} className="stat-card">
            <div className="stat-card__label">{card.label}</div>
            <div className="stat-card__value">{card.value}</div>
          </article>
        ))}
      </section>

      {metricsError ? (
        <div className="banner">Couldn't load model metrics: {metricsError}</div>
      ) : null}

      <SimulationControls
        form={sim.form}
        onChange={sim.handleChange}
        onSimulate={sim.runSimulation}
        isLoading={sim.isLoading}
        error={sim.error}
      />

      {sim.result ? (
        <SimulationResults
          pagedRows={sim.pagedRows}
          rowsCount={sim.rows.length}
          page={sim.page}
          totalPages={sim.totalPages}
          goToPage={sim.goToPage}
          pageSize={sim.pageSize}
          estimatedLifeHours={sim.estimatedLifeHours}
          displayedRpm={sim.displayedRpm}
          displayedStress={sim.displayedStress}
          displayedMaxHours={sim.displayedMaxHours}
        />
      ) : null}

      <CsvUploadControls
        selectedFile={csv.selectedFile}
        handleFileSelect={csv.handleFileSelect}
        runPrediction={csv.runPrediction}
        reset={csv.reset}
        isLoading={csv.isLoading}
        error={csv.error}
        result={csv.result}
      />

      <ParameterTrends rows={csv.rows} />

      <CsvUploadPredictions
        result={csv.result}
        pagedRows={csv.pagedRows}
        rows={csv.rows}
        page={csv.page}
        totalPages={csv.totalPages}
        goToPage={csv.goToPage}
      />
    </div>
  );
}