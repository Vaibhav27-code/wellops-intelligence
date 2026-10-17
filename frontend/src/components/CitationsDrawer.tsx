import type { Citation } from '../types';
import { FileText, AlertTriangle, Wrench, BookOpen, StickyNote, CheckCircle2, X } from 'lucide-react';

interface CitationsDrawerProps {
  citations: Citation[];
  onClose: () => void;
}

const iconFor = (type: Citation['source_type']) => {
  switch (type) {
    case 'inspection': return <FileText size={14} />;
    case 'repair': return <Wrench size={14} />;
    case 'regulatory': return <AlertTriangle size={14} />;
    case 'manual': return <BookOpen size={14} />;
    case 'note': return <StickyNote size={14} />;
    case 'correction': return <CheckCircle2 size={14} />;
    default: return <FileText size={14} />;
  }
};

const labelFor = (type?: string) => {
  if (!type) return 'Source Document';
  const map: Record<string, string> = {
    well: 'Well Record',
    inspection: 'Inspection',
    repair: 'Repair Report',
    regulatory: 'Regulatory Event',
    note: 'Human Note',
    manual: 'Manual / SOP',
    correction: 'Correction Log',
  };
  return map[type] ?? type;
};

export function CitationsDrawer({ citations, onClose }: CitationsDrawerProps) {
  if (!citations.length) return null;

  return (
    <aside className="citations-drawer" role="complementary" aria-label="Evidence Citations">
      <div className="citations-drawer__header">
        <span className="citations-drawer__title">
          {citations.length} Source{citations.length !== 1 ? 's' : ''}
        </span>
        <button className="citations-drawer__close" onClick={onClose} aria-label="Close citations">
          <X size={16} />
        </button>
      </div>
      <ul className="citations-drawer__list">
        {citations.map((c) => (
          <li key={c.id} className="citations-drawer__item">
            <div className="citations-drawer__item-header">
              <span className={`citation-badge citation-badge--${c.source_type}`}>
                {iconFor(c.source_type)}
                {labelFor(c.source_type)}
              </span>
              {c.well_id && (
                <span className="citations-drawer__well-id">
                  Well: {c.well_id}
                </span>
              )}
            </div>
            {(c.source_file || c.filename) && (
              <div className="citations-drawer__file">
                📄 {c.source_file || c.filename}
                {c.section && <> · {c.section}</>}
                {(c.record_id || c.id) && <> · ID {c.record_id || c.id}</>}
              </div>
            )}
            {c.date && (
              <div className="citations-drawer__date">🗓 {c.date}</div>
            )}
            {c.excerpt && (
              <blockquote className="citations-drawer__excerpt">
                "{c.excerpt}"
              </blockquote>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
