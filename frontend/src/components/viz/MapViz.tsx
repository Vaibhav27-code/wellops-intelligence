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
      ((r.latitude !== undefined && r.latitude !== null) || (r.lat !== undefined && r.lat !== null)) &&
      ((r.longitude !== undefined && r.longitude !== null) || (r.lon !== undefined && r.lon !== null) || (r.lng !== undefined && r.lng !== null))
  );

  if (!hasCoords) {
    return (
      <div className="map-viz map-fallback" style={{ padding: '16px', background: 'var(--c-surface)', borderRadius: '8px', border: '1px solid var(--c-border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--c-accent-h)', fontWeight: 600 }}>
          <MapPin size={18} />
          <span>Geospatial Map View (Coordinate Fallback)</span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--c-text-muted)', margin: '6px 0 12px 0' }}>
          Latitude/Longitude coordinates are null in this area dataset — rendering verified tabular geo-records:
        </p>
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
