import React from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import { UserPicker } from './UserPicker';
import { ChatThread } from './ChatThread';
import { Activity, FlaskConical, Menu, X, RefreshCw } from 'lucide-react';
import type { Correction } from '../types';

export function AppShell() {
  const { corrections, setCorrections, isSidebarOpen, toggleSidebar } = useStore();

  const fetchCorrections = React.useCallback(() => {
    api
      .getCorrections()
      .then((res) => {
        if (res.corrections) {
          const mapped: Correction[] = res.corrections.map((raw: any) => ({
            correction_id: raw.correction_id || `corr-${Math.random()}`,
            scope: raw.scope || 'well',
            well_id: raw.well_id,
            well_type: raw.well_type,
            field: raw.field,
            original_value: raw.original_value,
            corrected_value: raw.corrected_value,
            author: raw.author,
            created_at: raw.created_at || new Date().toISOString(),
            reason: raw.reason,
            evidence: raw.evidence,
          }));
          setCorrections(mapped);
        }
      })
      .catch((err) => console.warn('Could not fetch shared corrections:', err));
  }, [setCorrections]);

  React.useEffect(() => {
    fetchCorrections();
  }, [fetchCorrections]);

  return (
    <div className="app-shell">
      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <header className="topbar">
        <div className="topbar__brand">
          <Activity size={20} className="topbar__logo-icon" />
          <span className="topbar__title">Asset Intelligence Copilot</span>
          <span className="topbar__sub">FlytBase · Hacktoberfest 2026</span>
        </div>

        <div className="topbar__right">
          <UserPicker />
          <button
            className="topbar__sidebar-toggle"
            onClick={toggleSidebar}
            aria-label="Toggle corrections sidebar"
            title="Corrections log"
          >
            {isSidebarOpen ? <X size={18} /> : <Menu size={18} />}
            {corrections.length > 0 && (
              <span className="topbar__badge">{corrections.length}</span>
            )}
          </button>
        </div>
      </header>

      {/* ── Main content ────────────────────────────────────────────── */}
      <div className="app-shell__body">
        {/* Chat */}
        <main className="app-shell__chat">
          <ChatThread />
        </main>

        {/* Corrections sidebar */}
        {isSidebarOpen && (
          <aside className="corrections-sidebar" aria-label="Corrections log">
            <div className="corrections-sidebar__header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FlaskConical size={16} />
                <span>Audited Corrections Log</span>
              </div>
              <button
                onClick={fetchCorrections}
                style={{ padding: '4px', borderRadius: '4px', color: 'var(--c-text-muted)', display: 'flex', alignItems: 'center' }}
                title="Refresh audit log"
              >
                <RefreshCw size={13} />
              </button>
            </div>
            {corrections.length === 0 ? (
              <p className="corrections-sidebar__empty">No corrections recorded yet.</p>
            ) : (
              <ul className="corrections-sidebar__list">
                {[...corrections].reverse().map((c) => (
                  <li key={c.correction_id} className="correction-item">
                    <div className="correction-item__scope">
                      {c.scope === 'well' ? `Well ${c.well_id}` : `Type: ${c.well_type}`}
                    </div>
                    <div className="correction-item__field">{c.field}</div>
                    <div className="correction-item__values">
                      <span className="correction-item__original">{String(c.original_value)}</span>
                      <span> → </span>
                      <span className="correction-item__corrected">{String(c.corrected_value)}</span>
                    </div>
                    <div className="correction-item__meta">
                      By {c.author} · {new Date(c.created_at).toLocaleString()}
                    </div>
                    <div className="correction-item__reason">{c.reason}</div>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
