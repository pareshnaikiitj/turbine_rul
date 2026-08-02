import React from 'react';
import { healthTone } from '../utils/health';

export default function SimulationResults({
  pagedRows,
  rowsCount,
  page,
  totalPages,
  goToPage,
  pageSize,
  estimatedLifeHours,
  displayedRpm,
  displayedStress,
  displayedMaxHours,
}) {
  return (
    <section className="panel">
      <div className="panel-title-row">
        <span className="panel-title">Simulation Dashboard</span>
        <span className="panel-subtitle">Fresh-turbine failure simulation</span>
      </div>

      <div className="live-metrics">
        <div>
          <span>Estimated Operating Life</span>
          <strong>{estimatedLifeHours.toFixed(2)} hrs</strong>
        </div>
        <div>
          <span>Simulated RPM</span>
          <strong>{Number(displayedRpm).toFixed(0)}</strong>
        </div>
        <div>
          <span>Stress (MPa)</span>
          <strong>{Number(displayedStress).toFixed(1)}</strong>
        </div>
      </div>

      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>HOUR</th>
              <th>RPM</th>
              <th>STRESS (MPa)</th>
              <th>DAMAGE INCREMENT</th>
              <th>HEALTH SCORE</th>
            </tr>
          </thead>
          <tbody>
            {pagedRows.length ? (
              pagedRows.map((row, index) => {
                const score = Number(row.health_score ?? 0);
                return (
                  <tr key={`${row.hour ?? index}-${index}`}>
                    <td>{row.hour ?? index + 1}</td>
                    <td>{Number(row.rpm ?? 0).toFixed(2)}</td>
                    <td>{Number(row.stress_mpa ?? 0).toFixed(2)}</td>
                    <td>{Number(row.damage_increment ?? 0).toFixed(4)}</td>
                    <td>
                      <span className={`health-chip ${healthTone(score)}`}>{score.toFixed(1)}%</span>
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={5} className="empty-row">No degradation curve returned for this run.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {rowsCount > pageSize ? (
        <div className="pagination">
          <span className="pagination__info">
            Showing {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, rowsCount)} of {rowsCount} hours
            {' · '}max {displayedMaxHours} hrs modeled
          </span>
          <div className="pagination__controls">
            <button className="page-button" onClick={() => goToPage(page - 1)} disabled={page === 1}>‹</button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
              .reduce((acc, p, i, arr) => {
                if (i > 0 && p - arr[i - 1] > 1) acc.push('…');
                acc.push(p);
                return acc;
              }, [])
              .map((p, i) =>
                p === '…' ? (
                  <span key={`ellipsis-${i}`} className="pagination__info">…</span>
                ) : (
                  <button
                    key={p}
                    className={`page-button ${p === page ? 'active' : ''}`}
                    onClick={() => goToPage(p)}
                  >
                    {p}
                  </button>
                )
              )}
            <button className="page-button" onClick={() => goToPage(page + 1)} disabled={page === totalPages}>›</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
