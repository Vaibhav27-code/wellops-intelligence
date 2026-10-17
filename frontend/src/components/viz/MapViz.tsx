import React from 'react';
import type { VisualizationSpec } from '../../types';
import { MapPin } from 'lucide-react';

interface MapVizProps {
  spec: VisualizationSpec;
}

/**
 * Leaflet map showing well locations.
 * Dynamically imports react-leaflet to avoid SSR issues.
 * Falls back to a table if no lat/lon present.
 */
export function MapViz({ spec }: MapVizProps) {
  const hasCoords = spec.data.some(
    (r) =>
      (r.latitude !== undefined || r.lat !== undefined) &&
      (r.longitude !== undefined || r.lon !== undefined || r.lng !== undefined)
  );

  if (!hasCoords) {
    return (
      <div className="map-fallback">
        <MapPin size={20} className="map-fallback__icon" />
        <p>No coordinate data available — showing table instead.</p>
        <table className="data-table" style={{ marginTop: 12 }}>
          <thead>
            <tr>
              {Object.keys(spec.data[0] ?? {}).map((k) => (
                <th key={k} className="data-table__th">{k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {spec.data.map((row, i) => (
              <tr key={i}>
                {Object.values(row).map((v, j) => (
                  <td key={j} className="data-table__td">{String(v ?? '—')}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return <LeafletMap spec={spec} />;
}

/** Lazy-loaded Leaflet map to avoid window-is-not-defined issues */
const LeafletMap = React.lazy(() =>
  import('./LeafletMapInner').then((m) => ({ default: m.LeafletMapInner }))
);
