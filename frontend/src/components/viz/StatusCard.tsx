import type { VisualizationSpec } from '../../types';
import { Activity, AlertTriangle, CheckCircle2, Clock } from 'lucide-react';

interface StatusCardProps {
  spec: VisualizationSpec;
}

/** Renders a spec with type='card' — used for single-well status snapshots. */
export function StatusCard({ spec }: StatusCardProps) {
  const row = spec.data[0] ?? {};

  const status = String(row.status ?? row.Status ?? 'Unknown');
  const isWarn = /inspect|warn|pending/i.test(status);
  const isErr = /down|shut.in|spill|violation|fail/i.test(status);

  const icon = isErr ? (
    <AlertTriangle size={24} className="status-card__icon status-card__icon--err" />
  ) : isWarn ? (
    <Clock size={24} className="status-card__icon status-card__icon--warn" />
  ) : (
    <CheckCircle2 size={24} className="status-card__icon status-card__icon--ok" />
  );

  return (
    <div className={`status-card ${isErr ? 'status-card--err' : isWarn ? 'status-card--warn' : 'status-card--ok'}`}>
      <div className="status-card__header">
        {icon}
        <h3 className="status-card__title">{spec.title}</h3>
      </div>

      <dl className="status-card__fields">
        {Object.entries(row).map(([k, v]) => (
          <div key={k} className="status-card__field">
            <dt className="status-card__key">{k.replace(/_/g, ' ')}</dt>
            <dd className="status-card__val">{String(v ?? '—')}</dd>
          </div>
        ))}
      </dl>

      {spec.units && (
        <p className="status-card__units">
          <Activity size={12} /> Units: {spec.units}
        </p>
      )}
    </div>
  );
}
