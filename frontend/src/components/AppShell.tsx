import { useStore } from '../store';
import { UserPicker } from './UserPicker';
import { ChatThread } from './ChatThread';
import { Activity, FlaskConical, Menu, X } from 'lucide-react';

export function AppShell() {
  const { corrections, isSidebarOpen, toggleSidebar } = useStore();

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
            <div className="corrections-sidebar__header">
              <FlaskConical size={16} />
              Shared Corrections
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
