import React, { useMemo, useState } from 'react';

const WIDTH = 400;
const HEIGHT = 220;
const PAD = { top: 14, right: 16, bottom: 42, left: 66 };
const RING = '#0b0f1e';

/**
 * Dependency-free SVG line chart. Plots one or more `series` (each its own
 * color) against a shared xKey/yKey domain, with a crosshair that reads
 * every series at once. No charting library required.
 */
export default function LineChart({ series, xKey, yKey, xLabel = 'Cycle', yLabel = '', unitSuffix = '' }) {
  const [hoverX, setHoverX] = useState(null);

  const { plotted, xMin, xMax, yMin, yMax } = useMemo(() => {
    const nonEmpty = (series || []).filter((s) => s.data && s.data.length);
    if (!nonEmpty.length) {
      return { plotted: [], xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    }

    const allXs = nonEmpty.flatMap((s) => s.data.map((d) => Number(d[xKey])));
    const allYs = nonEmpty.flatMap((s) => s.data.map((d) => Number(d[yKey])));
    let xMin = Math.min(...allXs);
    let xMax = Math.max(...allXs);
    let yMin = Math.min(...allYs);
    let yMax = Math.max(...allYs);

    if (xMin === xMax) { xMin -= 1; xMax += 1; }
    if (yMin === yMax) {
      const pad = Math.abs(yMin) * 0.1 || 1;
      yMin -= pad;
      yMax += pad;
    } else {
      const pad = (yMax - yMin) * 0.08;
      yMin -= pad;
      yMax += pad;
    }

    const innerW = WIDTH - PAD.left - PAD.right;
    const innerH = HEIGHT - PAD.top - PAD.bottom;
    const scaleX = (x) => PAD.left + ((x - xMin) / (xMax - xMin)) * innerW;
    const scaleY = (y) => PAD.top + innerH - ((y - yMin) / (yMax - yMin)) * innerH;

    const plotted = nonEmpty.map((s) => ({
      ...s,
      points: s.data.map((d) => ({
        x: scaleX(Number(d[xKey])),
        y: scaleY(Number(d[yKey])),
        rawX: Number(d[xKey]),
        rawY: Number(d[yKey]),
      })),
    }));

    return { plotted, xMin, xMax, yMin, yMax };
  }, [series, xKey, yKey]);

  if (!plotted.length) {
    return (
      <div className="chart-empty" style={{ width: WIDTH, height: HEIGHT }}>
        No data
      </div>
    );
  }

  const showArea = plotted.length === 1;

  const handleMove = (event) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const relX = ((event.clientX - rect.left) / rect.width) * WIDTH;
    setHoverX(Math.min(Math.max(relX, PAD.left), WIDTH - PAD.right));
  };

  // Nearest point per series to the hovered pixel-X — series don't all
  // share the same cycle set (units run to failure at different lengths),
  // so each line snaps independently.
  const hoveredRows = hoverX === null
    ? []
    : plotted.map((s) => {
      let nearest = s.points[0];
      let best = Infinity;
      for (const p of s.points) {
        const d = Math.abs(p.x - hoverX);
        if (d < best) { best = d; nearest = p; }
      }
      return { ...s, point: nearest };
    });

  const tooltipRows = hoveredRows.length;
  const tooltipW = 160;
  const tooltipH = 18 + tooltipRows * 15 + 6;
  const tooltipAnchorX = hoverX === null ? 0 : hoverX;
  const tooltipX = Math.min(tooltipAnchorX + 10, WIDTH - tooltipW - 4);
  const topmostY = hoveredRows.length ? Math.min(...hoveredRows.map((r) => r.point.y)) : PAD.top;
  const tooltipY = Math.max(topmostY - tooltipH - 8, PAD.top);

  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      width="100%"
      height={HEIGHT}
      className="chart-svg"
      onMouseMove={handleMove}
      onMouseLeave={() => setHoverX(null)}
    >
      <defs>
        {showArea ? (
          <linearGradient id={`lc-grad-${yKey}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={plotted[0].color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={plotted[0].color} stopOpacity="0" />
          </linearGradient>
        ) : null}
      </defs>

      {[0, 0.5, 1].map((t) => (
        <line
          key={t}
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={PAD.top + t * (HEIGHT - PAD.top - PAD.bottom)}
          y2={PAD.top + t * (HEIGHT - PAD.top - PAD.bottom)}
          stroke="rgba(148,163,184,0.14)"
          strokeWidth="1"
        />
      ))}

      {showArea ? (
        <path
          d={`${linePath(plotted[0].points)} L${plotted[0].points[plotted[0].points.length - 1].x.toFixed(2)},${(HEIGHT - PAD.bottom).toFixed(2)} L${plotted[0].points[0].x.toFixed(2)},${(HEIGHT - PAD.bottom).toFixed(2)} Z`}
          fill={`url(#lc-grad-${yKey})`}
          stroke="none"
        />
      ) : null}

      {plotted.map((s) => (
        <path
          key={s.id}
          d={linePath(s.points)}
          fill="none"
          stroke={s.color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          opacity={hoverX === null ? 0.95 : 0.55}
        />
      ))}

      <text x={PAD.left} y={HEIGHT - PAD.bottom + 18} className="chart-axis-label">{xMin.toFixed(0)}</text>
      <text x={WIDTH - PAD.right} y={HEIGHT - PAD.bottom + 18} className="chart-axis-label" textAnchor="end">{xMax.toFixed(0)}</text>
      <text x={PAD.left - 8} y={PAD.top + 5} className="chart-axis-label" textAnchor="end">{yMax.toFixed(1)}</text>
      <text x={PAD.left - 8} y={HEIGHT - PAD.bottom} className="chart-axis-label" textAnchor="end">{yMin.toFixed(1)}</text>

      <text
        x={PAD.left + (WIDTH - PAD.left - PAD.right) / 2}
        y={HEIGHT - 6}
        className="chart-axis-title"
        textAnchor="middle"
      >
        {xLabel}
      </text>
      {yLabel ? (
        <g transform={`translate(14, ${PAD.top + (HEIGHT - PAD.top - PAD.bottom) / 2}) rotate(-90)`}>
          <text className="chart-axis-title" textAnchor="middle">{yLabel}</text>
        </g>
      ) : null}

      {hoveredRows.length ? (
        <>
          <line
            x1={hoverX}
            x2={hoverX}
            y1={PAD.top}
            y2={HEIGHT - PAD.bottom}
            stroke="rgba(148,163,184,0.35)"
            strokeDasharray="3,3"
          />
          {hoveredRows.map((r) => (
            <circle key={r.id} cx={r.point.x} cy={r.point.y} r="4.5" fill={r.color} stroke={RING} strokeWidth="2" />
          ))}
          <g transform={`translate(${tooltipX.toFixed(2)}, ${tooltipY.toFixed(2)})`}>
            <rect width={tooltipW} height={tooltipH} rx="7" fill="#111827" stroke="rgba(148,163,184,0.3)" />
            <text x="10" y="14" className="chart-tooltip-label">cycle {hoveredRows[0].point.rawX}</text>
            {hoveredRows.map((r, i) => (
              <g key={r.id} transform={`translate(10, ${28 + i * 15})`}>
                <line x1="0" y1="-4" x2="12" y2="-4" stroke={r.color} strokeWidth="2.5" strokeLinecap="round" />
                <text x="17" y="0" className="chart-tooltip-value">
                  {r.point.rawY.toFixed(2)}{unitSuffix}
                  <tspan className="chart-tooltip-series"> {r.label}</tspan>
                </text>
              </g>
            ))}
          </g>
        </>
      ) : null}
    </svg>
  );
}

function linePath(points) {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
}
