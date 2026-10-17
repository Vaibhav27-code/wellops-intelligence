
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import type { VisualizationSpec } from '../../types';
import 'leaflet/dist/leaflet.css';

// Fix missing marker icons in Vite
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface LeafletMapInnerProps {
  spec: VisualizationSpec;
}

export function LeafletMapInner({ spec }: LeafletMapInnerProps) {
  const points = spec.data.map((r) => ({
    lat: Number(r.latitude ?? r.lat),
    lng: Number(r.longitude ?? r.lon ?? r.lng),
    label: String(r.well_name ?? r.well_id ?? r.name ?? ''),
    status: String(r.status ?? ''),
  }));

  const center: [number, number] = [
    points.reduce((s, p) => s + p.lat, 0) / points.length,
    points.reduce((s, p) => s + p.lng, 0) / points.length,
  ];

  return (
    <div className="leaflet-wrapper">
      <h3 className="chart-title">{spec.title}</h3>
      <MapContainer
        center={center}
        zoom={8}
        style={{ height: 340, width: '100%', borderRadius: 8 }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {points.map((p, i) => (
          <Marker key={i} position={[p.lat, p.lng]}>
            <Popup>
              <strong>{p.label}</strong>
              {p.status && <><br />Status: {p.status}</>}
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
