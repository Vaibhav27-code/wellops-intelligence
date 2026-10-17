import React from 'react';
import type { VisualizationSpec, VizType } from '../../types';
import { StatusCard } from './StatusCard';
import { DataTable } from './DataTable';
import { LineChartViz } from './LineChartViz';
import { BarChartViz } from './BarChartViz';
import { HeatmapViz } from './HeatmapViz';
import { MapViz } from './MapViz';
import { Table2, LineChart, BarChart2, MapPin, Grid } from 'lucide-react';

import { resolveChartConfig } from './chartUtils';

interface VizRendererProps {
  spec: VisualizationSpec;
}

/** Checks whether data is compatible with specific chart types */
function checkCompatibility(spec: VisualizationSpec): Record<VizType, boolean> {
  const data = spec.data;
  if (!Array.isArray(data) || data.length === 0) {
    return { card: false, table: false, line: false, bar: false, map: false, heatmap: false };
  }

  const first = data[0];
  const keys = Object.keys(first);

  const lineCfg = resolveChartConfig(spec, 'line');
  const barCfg = resolveChartConfig(spec, 'bar');

  // Map enabled when spec is a map or data contains coordinates/well IDs
  const hasGeo =
    spec.type === 'map' ||
    (('latitude' in first || 'lat' in first) && ('longitude' in first || 'lon' in first)) ||
    ('well_id' in first && /WELL-/i.test(String(first.well_id)));

  // Heatmap requires month/date and area/location and numeric count/value
  const hasHeatmap =
    ('month' in first || 'month_str' in first || 'date' in first) &&
    ('area' in first || 'area_name' in first || 'area_id' in first);

  // Line requires numeric y and date/time/numeric x
  const hasLine =
    lineCfg.hasNumeric &&
    lineCfg.yKeys.length > 0 &&
    (!!spec.x || keys.some((k) => /date|week|time|day|period|month|year|timestamp/i.test(k)));

  // Bar requires categorical x and numeric y
  const hasBar = barCfg.hasNumeric && barCfg.yKeys.length > 0 && keys.length >= 2;

  // Status card: typically 1 row with status attributes
  const hasCard =
    data.length === 1 &&
    ('Well ID' in first || 'well_id' in first || 'Production Status' in first);

  return {
    table: true, // Table is always valid
    card: hasCard,
    line: hasLine,
    bar: hasBar,
    map: hasGeo,
    heatmap: hasHeatmap,
  };
}

/** Renders visualization with interactive view selector (Table | Line | Bar | Map | Heatmap) */
export function VizRenderer({ spec }: VizRendererProps) {
  const [activeType, setActiveType] = React.useState<VizType>(spec.type || 'table');

  // Synchronize when spec prop changes
  React.useEffect(() => {
    setActiveType(spec.type || 'table');
  }, [spec.type]);

  if (!spec.data || !Array.isArray(spec.data) || spec.data.length === 0) {
    return <p className="viz-empty">No records to display.</p>;
  }

  const compat = checkCompatibility(spec);

  const viewOptions: Array<{ type: VizType; label: string; icon: React.ReactNode }> = [
    ...(compat.card ? [{ type: 'card' as VizType, label: 'Card', icon: <Table2 size={13} /> }] : []),
    { type: 'table', label: 'Table', icon: <Table2 size={13} /> },
    { type: 'line', label: 'Line', icon: <LineChart size={13} /> },
    { type: 'bar', label: 'Bar', icon: <BarChart2 size={13} /> },
    { type: 'map', label: 'Map', icon: <MapPin size={13} /> },
    { type: 'heatmap', label: 'Heatmap', icon: <Grid size={13} /> },
  ];

  return (
    <div className="viz-renderer" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {/* View Selector Controls */}
      <div
        className="viz-view-selector"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          background: 'var(--c-surface2)',
          padding: '3px 6px',
          borderRadius: '6px',
          alignSelf: 'flex-start',
        }}
      >
        <span style={{ fontSize: '11px', color: 'var(--c-text-muted)', marginRight: '4px', fontWeight: 600 }}>
          View:
        </span>
        {viewOptions.map((opt) => {
          const enabled = compat[opt.type];
          const isSelected = activeType === opt.type;
          return (
            <button
              key={opt.type}
              disabled={!enabled}
              onClick={() => setActiveType(opt.type)}
              title={enabled ? `Show as ${opt.label}` : `${opt.label} view not compatible with this data shape`}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                padding: '2px 8px',
                borderRadius: '4px',
                background: isSelected ? 'var(--c-accent)' : 'transparent',
                color: isSelected ? '#fff' : enabled ? 'var(--c-text)' : 'var(--c-border)',
                cursor: enabled ? 'pointer' : 'not-allowed',
                opacity: enabled ? 1 : 0.4,
                fontWeight: isSelected ? 600 : 400,
                transition: 'background 0.15s',
              }}
            >
              {opt.icon}
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Render Component */}
      <div className="viz-content">
        <Inner type={activeType} spec={spec} />
      </div>
    </div>
  );
}

function Inner({ type, spec }: { type: VizType; spec: VisualizationSpec }) {
  try {
    switch (type) {
      case 'card':
        return <StatusCard spec={spec} />;
      case 'table':
        return <DataTable spec={spec} />;
      case 'line':
        return <LineChartViz spec={spec} />;
      case 'bar':
        return <BarChartViz spec={spec} />;
      case 'heatmap':
        return <HeatmapViz spec={spec} />;
      case 'map':
        return (
          <React.Suspense fallback={<p className="viz-loading">Loading map…</p>}>
            <MapViz spec={spec} />
          </React.Suspense>
        );
      default:
        return <DataTable spec={spec} />;
    }
  } catch (err) {
    console.warn('Viz render failed, falling back to table:', err);
    return <DataTable spec={spec} />;
  }
}

