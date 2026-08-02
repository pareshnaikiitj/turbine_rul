export const dashboardStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  * { box-sizing: border-box; }

  .dashboard-shell {
    --bg: #050710;
    --bg-glow-1: #0e2a3a;
    --bg-glow-2: #1a0e3a;
    --panel-bg: #0b0f1e;
    --panel-border: rgba(125, 211, 252, 0.14);
    --panel-border-hover: rgba(125, 211, 252, 0.32);
    --text-primary: #eef1fb;
    --text-muted: #8891ac;
    --text-faint: #545e78;
    --accent-cyan: #22d3ee;
    --accent-violet: #a78bfa;
    --accent-amber: #fbbf24;
    --accent-rose: #fb7185;
    --accent-green: #34d399;

    min-height: 100vh;
    padding: 28px;
    background:
      radial-gradient(1200px 600px at 10% -10%, var(--bg-glow-1), transparent 60%),
      radial-gradient(1000px 500px at 110% 10%, var(--bg-glow-2), transparent 55%),
      var(--bg);
    color: var(--text-primary);
    font-family: 'Inter', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
    gap: 22px;
  }

  .top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 18px;
    background: rgba(255,255,255,0.02);
    border: 1px solid var(--panel-border);
    border-radius: 12px;
  }
  .top-bar__left { display: flex; align-items: center; gap: 10px; }
  .brand-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; border-radius: 8px;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
    color: #051019; font-size: 14px;
  }
  .brand-label { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-muted); letter-spacing: 0.02em; }

  .hero-panel {
    padding: 30px 32px;
    background: linear-gradient(160deg, rgba(34,211,238,0.06), rgba(167,139,250,0.05));
    border: 1px solid var(--panel-border);
    border-radius: 16px;
    position: relative;
    overflow: hidden;
  }
  .hero-panel::after {
    content: '';
    position: absolute; inset: 0;
    background: radial-gradient(500px 220px at 85% 0%, rgba(34,211,238,0.12), transparent 70%);
    pointer-events: none;
  }
  .level-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: 0.1em;
    color: var(--accent-cyan);
    background: rgba(34,211,238,0.08);
    border: 1px solid rgba(34,211,238,0.28);
    padding: 5px 10px; border-radius: 999px;
  }
  .hero-panel h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 40px; font-weight: 700; letter-spacing: -0.01em;
    margin: 14px 0 6px;
    background: linear-gradient(90deg, #ffffff, #c7d2fe 70%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  }
  .hero-panel p { color: var(--text-muted); font-size: 15px; margin: 0 0 20px; }
  .cycle-pills { display: flex; gap: 8px; flex-wrap: wrap; }
  .pill {
    width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center;
    border-radius: 8px; font-size: 12px; font-family: 'JetBrains Mono', monospace;
    color: var(--text-faint); border: 1px solid var(--panel-border);
  }
  .pill.active {
    color: #051019; font-weight: 700;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
    border-color: transparent;
  }

  .stats-grid {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
  }
  .stat-card {
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 14px; padding: 18px 20px;
    transition: border-color 0.15s ease, transform 0.15s ease;
  }
  .stat-card:hover { border-color: var(--panel-border-hover); transform: translateY(-2px); }
  .stat-card__label {
    font-family: 'JetBrains Mono', monospace; font-size: 11px; letter-spacing: 0.08em;
    color: var(--text-faint); margin-bottom: 8px;
  }
  .stat-card__value { font-family: 'Space Grotesk', sans-serif; font-size: 22px; font-weight: 600; }

  .panel {
    background: var(--panel-bg); border: 1px solid var(--panel-border);
    border-radius: 16px; padding: 24px;
  }
  .panel-title-row { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 18px; flex-wrap: wrap; gap: 6px; }
  .panel-title { font-family: 'Space Grotesk', sans-serif; font-size: 19px; font-weight: 700; }
  .panel-subtitle { font-size: 13px; color: var(--text-muted); }

  .sim-controls {
    display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap;
  }
  .sim-controls label {
    display: flex; flex-direction: column; gap: 6px;
    font-size: 12px; color: var(--text-muted); min-width: 160px;
  }
  .sim-controls input {
    background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border);
    border-radius: 9px; padding: 10px 12px; color: var(--text-primary);
    font-size: 14px; outline: none; transition: border-color 0.15s ease;
  }
  .sim-controls input:focus { border-color: var(--accent-cyan); }
  .sim-controls button {
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
    color: #051019; border: none; border-radius: 9px;
    padding: 11px 22px; font-weight: 700; font-size: 14px; cursor: pointer;
    transition: filter 0.15s ease, transform 0.15s ease;
  }
  .sim-controls button:hover:not(:disabled) { filter: brightness(1.08); transform: translateY(-1px); }
  .sim-controls button:disabled { opacity: 0.55; cursor: not-allowed; }

  .banner {
    margin-top: 14px; font-size: 13px; padding: 10px 14px; border-radius: 9px;
    background: rgba(251, 113, 133, 0.08); border: 1px solid rgba(251, 113, 133, 0.28);
    color: #fecdd3;
  }

  .live-metrics {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 20px 0;
  }
  .live-metrics > div {
    background: rgba(255,255,255,0.02); border: 1px solid var(--panel-border);
    border-radius: 12px; padding: 16px;
  }
  .live-metrics span { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
  .live-metrics strong { font-family: 'Space Grotesk', sans-serif; font-size: 22px; font-weight: 700; color: var(--accent-cyan); }

  .table-wrapper { overflow-x: auto; border: 1px solid var(--panel-border); border-radius: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  thead tr { background: rgba(255,255,255,0.03); }
  th {
    text-align: left; padding: 12px 16px; font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: 0.06em; color: var(--text-faint); font-weight: 500;
  }
  td { padding: 12px 16px; border-top: 1px solid rgba(255,255,255,0.04); color: var(--text-primary); }
  tbody tr:hover { background: rgba(34,211,238,0.03); }

  .health-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: 999px; font-weight: 600; font-size: 12.5px;
  }
  .health-chip::before { content: ''; width: 6px; height: 6px; border-radius: 50%; }
  .tone-healthy { color: var(--accent-green); background: rgba(52,211,153,0.1); }
  .tone-healthy::before { background: var(--accent-green); }
  .tone-watch { color: var(--accent-amber); background: rgba(251,191,36,0.1); }
  .tone-watch::before { background: var(--accent-amber); }
  .tone-critical { color: var(--accent-rose); background: rgba(251,113,133,0.1); }
  .tone-critical::before { background: var(--accent-rose); }

  .empty-row { text-align: center; color: var(--text-faint); padding: 28px 0 !important; }

  .pagination {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 16px; flex-wrap: wrap; gap: 10px;
  }
  .pagination__info { font-size: 12.5px; color: var(--text-muted); }
  .pagination__controls { display: flex; align-items: center; gap: 6px; }
  .page-button {
    min-width: 32px; height: 32px; padding: 0 8px;
    border-radius: 8px; border: 1px solid var(--panel-border);
    background: transparent; color: var(--text-muted);
    font-size: 13px; font-family: 'JetBrains Mono', monospace; cursor: pointer;
    transition: all 0.15s ease;
  }
  .page-button:hover:not(:disabled) { color: var(--text-primary); border-color: var(--panel-border-hover); }
  .page-button:disabled { opacity: 0.35; cursor: not-allowed; }
  .page-button.active {
    color: #051019; font-weight: 700; border-color: transparent;
    background: linear-gradient(135deg, var(--accent-cyan), var(--accent-violet));
  }

  @media (max-width: 900px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .live-metrics { grid-template-columns: repeat(1, 1fr); }
  }
`;
