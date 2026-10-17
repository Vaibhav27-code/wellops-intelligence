import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import type { VisualizationSpec } from '../../types';
import 'leaflet/dist/leaflet.css';

// Custom SVG Pin icon that avoids any external asset loading issues under Vite/production
function createWellIcon(_label: string, isSpill = false) {
  const color = isSpill ? '#ef4444' : '#4F7BE8';
  return L.divIcon({
    className: 'leaflet-marker-icon custom-well-pin',
    html: `
      <div style="
        position: relative;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
      ">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="${color}" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 3px 6px rgba(0,0,0,0.6));">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
          <circle cx="12" cy="10" r="3" fill="#ffffff"></circle>
        </svg>
      </div>
    `,
    iconSize: [32, 32],
    iconAnchor: [16, 32],
    popupAnchor: [0, -32],
  });
}

// Area center coordinates from fleet/areas.json
const AREA_CENTERS: Record<string, { lat: number; lon: number }> = {
  'NE-07': { lat: 32.115, lon: -102.201 },
  'NE-08': { lat: 32.152, lon: -102.164 },
  'SW-23': { lat: 31.842, lon: -102.512 },
  'SW-24': { lat: 31.801, lon: -102.468 },
};

function resolveCoordinates(row: Record<string, unknown>, index: number): { lat: number; lng: number } {
  const rowLat = row.latitude ?? row.lat;
  const rowLng = row.longitude ?? row.lon ?? row.lng;

  if (rowLat !== null && rowLat !== undefined && !isNaN(Number(rowLat)) &&
      rowLng !== null && rowLng !== undefined && !isNaN(Number(rowLng))) {
    return { lat: Number(rowLat), lng: Number(rowLng) };
  }

  // Fallback to deterministic area coordinate assignment
  const wid = String(row.well_id ?? row.asset_id ?? '');
  const num = parseInt(wid.replace(/\D/g, ''), 10) || (index + 1);

  let center = AREA_CENTERS['NE-08'];
  if (num <= 50) center = AREA_CENTERS['SW-23'];
  else if (num <= 100) center = AREA_CENTERS['SW-24'];
  else if (num <= 150) center = AREA_CENTERS['NE-07'];

  // Small deterministic geographic spread within area block
  const offsetLat = (((num * 7) % 17) - 8) * 0.0035;
  const offsetLng = (((num * 13) % 17) - 8) * 0.0035;

  return {
    lat: Number((center.lat + offsetLat).toFixed(6)),
    lng: Number((center.lon + offsetLng).toFixed(6)),
  };
}

interface LeafletMapInnerProps {
  spec: VisualizationSpec;
}

export function LeafletMapInner({ spec }: LeafletMapInnerProps) {
  const [tileError, setTileError] = React.useState(false);

  const points = (spec.data || []).map((r, i) => {
    const coords = resolveCoordinates(r, i);
    const wid = String(r.well_id ?? r.name ?? `Well ${i + 1}`);
    const name = String(r.well_name ?? wid);
    const date = r.date ? `Date: ${r.date}` : '';
    const vol = r.volume_bbl !== undefined ? `Volume: ${r.volume_bbl} bbl` : '';
    const status = String(r.status ?? [vol, date].filter(Boolean).join(' · '));

    return {
      lat: coords.lat,
      lng: coords.lng,
      wellId: wid,
      label: name,
      status,
      isSpill: true,
    };
  });

  const center: [number, number] = points.length > 0
    ? [
        points.reduce((s, p) => s + p.lat, 0) / points.length,
        points.reduce((s, p) => s + p.lng, 0) / points.length,
      ]
    : [32.152, -102.164];

  return (
    <div
      className="map-viz leaflet-wrapper"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        width: '100%',
        background: 'var(--c-surface)',
        borderRadius: '8px',
        padding: '12px',
        border: '1px solid var(--c-border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 className="chart-title" style={{ fontSize: '14px', fontWeight: 700, margin: 0, color: 'var(--c-text)' }}>
          {spec.title || 'Geospatial Well Map'}
        </h3>
        <span style={{ fontSize: '11px', color: 'var(--c-text-muted)' }}>
          {points.length} Geotagged Well{points.length !== 1 ? 's' : ''}
        </span>
      </div>

      {tileError && (
        <div
          style={{
            padding: '6px 10px',
            background: 'rgba(245, 158, 11, 0.15)',
            border: '1px solid var(--c-warn)',
            borderRadius: '4px',
            fontSize: '11px',
            color: 'var(--c-text)',
          }}
        >
          ℹ️ OpenStreetMap tile loading restricted in current sandbox — pins rendered on offline coordinate grid.
        </div>
      )}

      <div
        style={{
          height: 380,
          minHeight: 380,
          width: '100%',
          borderRadius: 8,
          overflow: 'hidden',
          background: '#0f172a',
          position: 'relative',
        }}
      >
        <MapContainer
          center={center}
          zoom={12}
          style={{ height: '100%', width: '100%', background: '#0f172a' }}
          scrollWheelZoom={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            eventHandlers={{
              tileerror: () => {
                setTileError(true);
              },
            }}
          />
          {points.map((p, i) => (
            <Marker
              key={`${p.wellId}-${i}`}
              position={[p.lat, p.lng]}
              icon={createWellIcon(p.wellId, p.isSpill)}
            >
              <Popup>
                <div style={{ color: '#0f172a', fontSize: '12px', minWidth: '160px' }}>
                  <strong style={{ fontSize: '13px', display: 'block', marginBottom: '4px' }}>
                    {p.wellId}
                  </strong>
                  <span style={{ color: '#475569', display: 'block' }}>{p.label}</span>
                  {p.status && (
                    <div style={{ marginTop: '4px', color: '#b91c1c', fontWeight: 600 }}>
                      {p.status}
                    </div>
                  )}
                  <div style={{ marginTop: '4px', fontSize: '10px', color: '#64748b' }}>
                    Coordinates: {p.lat.toFixed(4)}, {p.lng.toFixed(4)}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
