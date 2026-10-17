
import type { VisualizationSpec } from '../../types';

interface HeatmapVizProps {
  spec: VisualizationSpec;
}

/**
 * Area × Month heatmap.
 * Expects spec.data as array of {area, month, value} objects.
 * spec.x = 'month', spec.y = 'area', spec.units e.g. 'days'.
 */
export function HeatmapViz({ spec }: HeatmapVizProps) {
  const xKey = spec.x ?? 'month';
  const yKey = Array.isArray(spec.y) ? spec.y[0] : (spec.y ?? 'area');
  const valueKey = spec.data.length > 0
    ? Object.keys(spec.data[0]).find((k) => k !== xKey && k !== yKey) ?? 'value'
    : 'value';

  const xLabels = [...new Set(spec.data.map((r) => String(r[xKey])))];
  const yLabels = [...new Set(spec.data.map((r) => String(r[yKey])))];

  // Build lookup: area -> month -> value
  const lookup = new Map<string, Map<string, number>>();
  for (const row of spec.data) {
    const y = String(row[yKey]);
    const x = String(row[xKey]);
    const v = Number(row[valueKey] ?? 0);
    if (!lookup.has(y)) lookup.set(y, new Map());
    lookup.get(y)!.set(x, v);
  }

  const allValues = spec.data.map((r) => Number(r[valueKey] ?? 0)).filter(isFinite);
  const maxVal = Math.max(...allValues, 1);

  const cellColor = (v: number) => {
    const ratio = Math.min(v / maxVal, 1);
    // Dark blue → bright amber
    const r = Math.round(25 + ratio * 220);
    const g = Math.round(130 + ratio * 60);
    const b = Math.round(180 - ratio * 150);
    return `rgb(${r},${g},${b})`;
  };

  return (
    <div className="heatmap-viz heatmap-wrapper">
      <h3 className="chart-title">{spec.title}</h3>
      <div className="heatmap-scroll">
        <table className="heatmap">
          <thead>
            <tr>
              <th className="heatmap__corner" />
              {xLabels.map((x) => (
                <th key={x} className="heatmap__col-header">{x}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {yLabels.map((y) => (
              <tr key={y}>
                <th className="heatmap__row-header">{y}</th>
                {xLabels.map((x) => {
                  const v = lookup.get(y)?.get(x) ?? 0;
                  return (
                    <td
                      key={x}
                      className="heatmap__cell"
                      style={{ background: cellColor(v) }}
                      title={`${y} / ${x}: ${v}${spec.units ? ' ' + spec.units : ''}`}
                    >
                      {v > 0 ? v : ''}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="heatmap-legend">
        <span>0</span>
        <div className="heatmap-legend__bar" />
        <span>{maxVal}{spec.units ? ' ' + spec.units : ''}</span>
      </div>
    </div>
  );
}
