import React from 'react';
import type { VisualizationSpec, VizType } from '../../types';
import { StatusCard } from './StatusCard';
import { DataTable } from './DataTable';
import { LineChartViz } from './LineChartViz';
import { BarChartViz } from './BarChartViz';
import { HeatmapViz } from './HeatmapViz';
import { MapViz } from './MapViz';
import { LayoutGrid, Table2 } from 'lucide-react';

interface VizRendererProps {
  spec: VisualizationSpec;
}

/** Renders the correct visualization based on spec.type. Always has a table fallback. */
export function VizRenderer({ spec }: VizRendererProps) {
  const [view, setView] = React.useState<'viz' | 'table'>('viz');

  if (!spec.data || spec.data.length === 0) {
    return <p className="viz-empty">No data to display.</p>;
  }

  const canToggle = spec.type !== 'card' && spec.type !== 'table';

  return (
    <div className="viz-renderer">
      {canToggle && (
        <div className="viz-toggle">
          <button
            className={`viz-toggle__btn ${view === 'viz' ? 'active' : ''}`}
            onClick={() => setView('viz')}
            title="Chart view"
          >
            <LayoutGrid size={14} />
          </button>
          <button
            className={`viz-toggle__btn ${view === 'table' ? 'active' : ''}`}
            onClick={() => setView('table')}
            title="Table view"
          >
            <Table2 size={14} />
          </button>
        </div>
      )}

      {view === 'table' && spec.type !== 'table' ? (
        <DataTable spec={spec} />
      ) : (
        <Inner type={spec.type} spec={spec} />
      )}
    </div>
  );
}

function Inner({ type, spec }: { type: VizType; spec: VisualizationSpec }) {
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
}
