import React from 'react';
import TurbineRulDashboard from './components/TurbineRulDashboard';

export default function App() {
  return <TurbineRulDashboard />;
}


// import React, { useMemo, useState } from 'react';

// // ---------------------------------------------------------------------------
// // API integration — kept separate from the component so the fetch/parse/error
// // handling logic is easy to find, test, and swap out independently of the UI.
// // ---------------------------------------------------------------------------
// const SIMULATION_API_URL = 'http://localhost:8000/simulate-fresh-turbine';

// // max_hours is no longer a user input — it's just an upper bound so the
// // simulation has enough runway to reach failure. The backend still returns
// // its own effective max_hours in the response, which is what gets displayed.
// const DEFAULT_MAX_HOURS = 2000;

// async function runFailureSimulation({ rpm, stressMpa, signal }) {
//   const response = await fetch(SIMULATION_API_URL, {
//     method: 'POST',
//     headers: { 'Content-Type': 'application/json' },
//     body: JSON.stringify({
//       rpm: Number(rpm),
//       stress_mpa: Number(stressMpa),
//       max_hours: DEFAULT_MAX_HOURS,
//     }),
//     signal,
//   });

//   if (!response.ok) {
//     const text = await response.text().catch(() => '');
//     throw new Error(text || `Simulation request failed (${response.status})`);
//   }

//   const data = await response.json();

//   if (!data || !Array.isArray(data.degradation_curve)) {
//     throw new Error('Simulation response was missing a degradation curve');
//   }

//   return data;
// }

// // ---------------------------------------------------------------------------
// // UI
// // ---------------------------------------------------------------------------
// const initialState = {
//   rpm: 4000,
//   stress_mpa: 500,
// };

// const metricCards = [
//   { label: 'MODEL', value: 'RandomForest' },
//   { label: 'TEST MAE', value: '1.83 hrs' },
//   { label: 'TEST RMSE', value: '2.53 hrs' },
//   { label: 'R² SCORE', value: '0.9649' },
// ];

// const PAGE_SIZE = 8;

// function healthTone(score) {
//   if (score >= 70) return 'tone-healthy';
//   if (score >= 40) return 'tone-watch';
//   return 'tone-critical';
// }

// export default function App() {
//   const [form, setForm] = useState(initialState);
//   const [simulationResult, setSimulationResult] = useState(null);
//   const [isSimulationLoading, setIsSimulationLoading] = useState(false);
//   const [simulationError, setSimulationError] = useState('');
//   const [page, setPage] = useState(1);

//   const handleChange = (event) => {
//     const { name, value } = event.target;
//     setForm((prev) => ({ ...prev, [name]: value }));
//   };

//   const handleSimulation = async () => {
//     setIsSimulationLoading(true);
//     setSimulationError('');
//     setPage(1);

//     const controller = new AbortController();

//     try {
//       const data = await runFailureSimulation({
//         rpm: form.rpm,
//         stressMpa: form.stress_mpa,
//         signal: controller.signal,
//       });
//       setSimulationResult(data);
//     } catch (apiError) {
//       if (apiError.name !== 'AbortError') {
//         setSimulationError(apiError.message || 'Unable to reach the simulation API.');
//         setSimulationResult(null);
//       }
//     } finally {
//       setIsSimulationLoading(false);
//     }
//   };

//   // Prefer the values the backend actually simulated with over the raw form
//   // inputs, since the API response is the source of truth once a run completes.
//   const simulationRows = simulationResult?.degradation_curve ?? [];
//   const displayedRpm = simulationResult?.rpm ?? Number(form.rpm);
//   const displayedStress = simulationResult?.stress_mpa ?? Number(form.stress_mpa);
//   const displayedMaxHours = simulationResult?.max_hours ?? DEFAULT_MAX_HOURS;
//   const estimatedLifeHours = Number(simulationResult?.estimated_operating_life_hours ?? 0);

//   const totalPages = Math.max(1, Math.ceil(simulationRows.length / PAGE_SIZE));
//   const pagedRows = useMemo(
//     () => simulationRows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
//     [simulationRows, page]
//   );

//   const goToPage = (next) => {
//     setPage(Math.min(Math.max(1, next), totalPages));
//   };

//   return (
//     <div className="dashboard-shell">
//       <style>{`
//         @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

//         * { box-sizing: border-box; }

//         .dashboard-shell {
//           --bg: #050710;
//           --bg-glow-1: #0e2a3a;
//           --bg-glow-2: #1a0e3a;
//           --panel-bg: #0b0f1e;
//           --panel-border: rgba(125, 211, 252, 0.14);
//           --panel-border-hover: rgba(125, 211, 252, 0.32);
//           --text-primary: #eef1fb;
//           --text-muted: #8891ac;
//           --text-faint: #545e78;
//           --accent-cyan: #22d3ee;
//           --accent-violet: #a78bfa;
//           --accent-amber: #fbbf24;
//           --accent-rose: #fb7185;
//           --accent-green: #34d399;

//           min-height: 100vh;
//           padding: 28px;
//           background:
//             radial-gradient(1200px 600px at 10% -10%, var(--bg-glow-1), transparent 60%),
//             radial-gradient(1000px 500px at 110% 10%, var(--bg-glow-2), transparent 55%),
//             var(--bg);
//           color: var(--text-primary);
//           font-family: 'Inter', system-ui, sans-serif;
//           display: flex;
//           flex-direction: column;
//           gap: 22px;
//         }

//         .top-bar {
//           display: flex;
//           align-items: center;
//           justify-content: space-between;
//           padding: 12px 18px;
//           background: rgba(255,255,255,0.02);
//           border: 1px solid var(--panel-border);
//           border-radius: 12px;
//         }
//         .top-bar__left { display: flex; align-items: center; gap: 10px; }
//         .brand-icon {
//           display: inline-flex; align-items: center; justify-content: center;
//           width: 26px; height: 26px; border-radius: 8px;
//           background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
//           color: #051019; font-size: 14px;
//         }
//         .brand-label { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-muted); letter-spacing: 0.02em; }

//         .hero-panel {
//           padding: 30px 32px;
//           background: linear-gradient(160deg, rgba(34,211,238,0.06), rgba(167,139,250,0.05));
//           border: 1px solid var(--panel-border);
//           border-radius: 16px;
//           position: relative;
//           overflow: hidden;
//         }
//         .hero-panel::after {
//           content: '';
//           position: absolute; inset: 0;
//           background: radial-gradient(500px 220px at 85% 0%, rgba(34,211,238,0.12), transparent 70%);
//           pointer-events: none;
//         }
//         .level-badge {
//           display: inline-block;
//           font-family: 'JetBrains Mono', monospace;
//           font-size: 11px; letter-spacing: 0.1em;
//           color: var(--accent-cyan);
//           background: rgba(34,211,238,0.08);
//           border: 1px solid rgba(34,211,238,0.28);
//           padding: 5px 10px; border-radius: 999px;
//         }
//         .hero-panel h1 {
//           font-family: 'Space Grotesk', sans-serif;
//           font-size: 40px; font-weight: 700; letter-spacing: -0.01em;
//           margin: 14px 0 6px;
//           background: linear-gradient(90deg, #ffffff, #c7d2fe 70%);
//           -webkit-background-clip: text; background-clip: text; color: transparent;
//         }
//         .hero-panel p { color: var(--text-muted); font-size: 15px; margin: 0 0 20px; }
//         .cycle-pills { display: flex; gap: 8px; flex-wrap: wrap; }
//         .pill {
//           width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center;
//           border-radius: 8px; font-size: 12px; font-family: 'JetBrains Mono', monospace;
//           color: var(--text-faint); border: 1px solid var(--panel-border);
//         }
//         .pill.active {
//           color: #051019; font-weight: 700;
//           background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
//           border-color: transparent;
//         }

//         .stats-grid {
//           display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
//         }
//         .stat-card {
//           background: var(--panel-bg); border: 1px solid var(--panel-border);
//           border-radius: 14px; padding: 18px 20px;
//           transition: border-color 0.15s ease, transform 0.15s ease;
//         }
//         .stat-card:hover { border-color: var(--panel-border-hover); transform: translateY(-2px); }
//         .stat-card__label {
//           font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.08em;
//           color: var(--text-faint); margin-bottom: 8px;
//         }
//         .stat-card__value { font-family: 'Space Grotesk', sans-serif; font-size: 22px; font-weight: 600; }

//         .panel {
//           background: var(--panel-bg); border: 1px solid var(--panel-border);
//           border-radius: 16px; padding: 24px;
//         }
//         .panel-title-row { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 18px; flex-wrap: wrap; gap: 6px; }
//         .panel-title { font-family: 'Space Grotesk', sans-serif; font-size: 19px; font-weight: 700; }
//         .panel-subtitle { font-size: 13px; color: var(--text-muted); }

//         .sim-controls {
//           display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap;
//         }
//         .sim-controls label {
//           display: flex; flex-direction: column; gap: 6px;
//           font-size: 12px; color: var(--text-muted); min-width: 160px;
//         }
//         .sim-controls input {
//           background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border);
//           border-radius: 9px; padding: 10px 12px; color: var(--text-primary);
//           font-size: 14px; outline: none; transition: border-color 0.15s ease;
//         }
//         .sim-controls input:focus { border-color: var(--accent-cyan); }
//         .sim-controls button {
//           background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
//           color: #051019; border: none; border-radius: 9px;
//           padding: 11px 22px; font-weight: 700; font-size: 14px; cursor: pointer;
//           transition: filter 0.15s ease, transform 0.15s ease;
//         }
//         .sim-controls button:hover:not(:disabled) { filter: brightness(1.08); transform: translateY(-1px); }
//         .sim-controls button:disabled { opacity: 0.55; cursor: not-allowed; }

//         .banner {
//           margin-top: 14px; font-size: 13px; padding: 10px 14px; border-radius: 9px;
//           background: rgba(251, 113, 133, 0.08); border: 1px solid rgba(251, 113, 133, 0.28);
//           color: #fecdd3;
//         }

//         .live-metrics {
//           display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 20px 0;
//         }
//         .live-metrics > div {
//           background: rgba(255,255,255,0.02); border: 1px solid var(--panel-border);
//           border-radius: 12px; padding: 16px;
//         }
//         .live-metrics span { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
//         .live-metrics strong { font-family: 'Space Grotesk', sans-serif; font-size: 22px; font-weight: 700; color: var(--accent-cyan); }

//         .table-wrapper { overflow-x: auto; border: 1px solid var(--panel-border); border-radius: 12px; }
//         table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
//         thead tr { background: rgba(255,255,255,0.03); }
//         th {
//           text-align: left; padding: 12px 16px; font-family: 'JetBrains Mono', monospace;
//           font-size: 11px; letter-spacing: 0.06em; color: var(--text-faint); font-weight: 500;
//         }
//         td { padding: 12px 16px; border-top: 1px solid rgba(255,255,255,0.04); color: var(--text-primary); }
//         tbody tr:hover { background: rgba(34,211,238,0.03); }

//         .health-chip {
//           display: inline-flex; align-items: center; gap: 6px;
//           padding: 3px 10px; border-radius: 999px; font-weight: 600; font-size: 12.5px;
//         }
//         .health-chip::before { content: ''; width: 6px; height: 6px; border-radius: 50%; }
//         .tone-healthy { color: var(--accent-green); background: rgba(52,211,153,0.1); }
//         .tone-healthy::before { background: var(--accent-green); }
//         .tone-watch { color: var(--accent-amber); background: rgba(251,191,36,0.1); }
//         .tone-watch::before { background: var(--accent-amber); }
//         .tone-critical { color: var(--accent-rose); background: rgba(251,113,133,0.1); }
//         .tone-critical::before { background: var(--accent-rose); }

//         .empty-row { text-align: center; color: var(--text-faint); padding: 28px 0 !important; }

//         .pagination {
//           display: flex; align-items: center; justify-content: space-between;
//           margin-top: 16px; flex-wrap: wrap; gap: 10px;
//         }
//         .pagination__info { font-size: 12.5px; color: var(--text-muted); }
//         .pagination__controls { display: flex; align-items: center; gap: 6px; }
//         .page-button {
//           min-width: 32px; height: 32px; padding: 0 8px;
//           border-radius: 8px; border: 1px solid var(--panel-border);
//           background: transparent; color: var(--text-muted);
//           font-size: 13px; font-family: 'JetBrains Mono', monospace; cursor: pointer;
//           transition: all 0.15s ease;
//         }
//         .page-button:hover:not(:disabled) { color: var(--text-primary); border-color: var(--panel-border-hover); }
//         .page-button:disabled { opacity: 0.35; cursor: not-allowed; }
//         .page-button.active {
//           color: #051019; font-weight: 700; border-color: transparent;
//           background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
//         }

//         @media (max-width: 900px) {
//           .stats-grid { grid-template-columns: repeat(2, 1fr); }
//           .live-metrics { grid-template-columns: repeat(1, 1fr); }
//         }
//       `}</style>

//       <header className="top-bar">
//         <div className="top-bar__left">
//           <span className="brand-icon">◌</span>
//           <span className="brand-label">Turbine RUL Dashboard</span>
//         </div>
//       </header>

//       <section className="hero-panel">
//         <div className="hero-panel__title-row">
//           <span className="level-badge">M25DE2039 TURBINE BLADE RUL</span>
//         </div>
//         <h1>Remaining Useful Life Console</h1>
//         <p>ML predictions, SLMTA15 fatigue model &amp; degradation trajectory</p>
//         <div className="cycle-pills">
//           {[1, 2, 3, 4, 5, 6, 7, 8].map((item) => (
//             <span key={item} className={item === 1 ? 'pill active' : 'pill'}>
//               {item}
//             </span>
//           ))}
//         </div>
//       </section>

//       <section className="stats-grid">
//         {metricCards.map((card) => (
//           <article key={card.label} className="stat-card">
//             <div className="stat-card__label">{card.label}</div>
//             <div className="stat-card__value">{card.value}</div>
//           </article>
//         ))}
//       </section>

//       <section className="panel">
//         <div className="panel-title-row">
//           <span className="panel-title">Simulation Controls</span>
//           <span className="panel-subtitle">Fresh-turbine failure simulation inputs</span>
//         </div>
//         <div className="sim-controls">
//           <label>
//             RPM
//             <input name="rpm" value={form.rpm} onChange={handleChange} type="number" />
//           </label>
//           <label>
//             Stress (MPa)
//             <input name="stress_mpa" value={form.stress_mpa} onChange={handleChange} step="0.1" type="number" />
//           </label>
//           <button type="button" disabled={isSimulationLoading} onClick={handleSimulation}>
//             {isSimulationLoading ? 'Simulating...' : 'Simulate Failure'}
//           </button>
//         </div>
//         {simulationError ? <p className="banner">{simulationError}</p> : null}
//       </section>

//       {simulationResult ? (
//         <section className="panel">
//           <div className="panel-title-row">
//             <span className="panel-title">Simulation Dashboard</span>
//             <span className="panel-subtitle">Fresh-turbine failure simulation</span>
//           </div>

//           <div className="live-metrics">
//             <div>
//               <span>Estimated Operating Life</span>
//               <strong>{estimatedLifeHours.toFixed(2)} hrs</strong>
//             </div>
//             <div>
//               <span>Simulated RPM</span>
//               <strong>{Number(displayedRpm).toFixed(0)}</strong>
//             </div>
//             <div>
//               <span>Stress (MPa)</span>
//               <strong>{Number(displayedStress).toFixed(1)}</strong>
//             </div>
//           </div>

//           <div className="table-wrapper">
//             <table>
//               <thead>
//                 <tr>
//                   <th>HOUR</th>
//                   <th>RPM</th>
//                   <th>STRESS (MPa)</th>
//                   <th>DAMAGE INCREMENT</th>
//                   <th>HEALTH SCORE</th>
//                 </tr>
//               </thead>
//               <tbody>
//                 {pagedRows.length ? (
//                   pagedRows.map((row, index) => {
//                     const score = Number(row.health_score ?? 0);
//                     return (
//                       <tr key={`${row.hour ?? index}-${index}`}>
//                         <td>{row.hour ?? index + 1}</td>
//                         <td>{Number(row.rpm ?? 0).toFixed(2)}</td>
//                         <td>{Number(row.stress_mpa ?? 0).toFixed(2)}</td>
//                         <td>{Number(row.damage_increment ?? 0).toFixed(4)}</td>
//                         <td><span className={`health-chip ${healthTone(score)}`}>{score.toFixed(1)}%</span></td>
//                       </tr>
//                     );
//                   })
//                 ) : (
//                   <tr>
//                     <td colSpan={5} className="empty-row">No degradation curve returned for this run.</td>
//                   </tr>
//                 )}
//               </tbody>
//             </table>
//           </div>

//           {simulationRows.length > PAGE_SIZE ? (
//             <div className="pagination">
//               <span className="pagination__info">
//                 Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, simulationRows.length)} of {simulationRows.length} hours
//                 {' · '}max {displayedMaxHours} hrs modeled
//               </span>
//               <div className="pagination__controls">
//                 <button className="page-button" onClick={() => goToPage(page - 1)} disabled={page === 1}>‹</button>
//                 {Array.from({ length: totalPages }, (_, i) => i + 1)
//                   .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
//                   .reduce((acc, p, i, arr) => {
//                     if (i > 0 && p - arr[i - 1] > 1) acc.push('…');
//                     acc.push(p);
//                     return acc;
//                   }, [])
//                   .map((p, i) =>
//                     p === '…' ? (
//                       <span key={`ellipsis-${i}`} className="pagination__info">…</span>
//                     ) : (
//                       <button
//                         key={p}
//                         className={`page-button ${p === page ? 'active' : ''}`}
//                         onClick={() => goToPage(p)}
//                       >
//                         {p}
//                       </button>
//                     )
//                   )}
//                 <button className="page-button" onClick={() => goToPage(page + 1)} disabled={page === totalPages}>›</button>
//               </div>
//             </div>
//           ) : null}
//         </section>
//       ) : null}
//     </div>
//   );
// }