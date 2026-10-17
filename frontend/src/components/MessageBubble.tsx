import React from 'react';
import type { ChatMessage } from '../types';
import { VizRenderer } from './viz/VizRenderer';
import { CitationsDrawer } from './CitationsDrawer';
import { CorrectionModal } from './CorrectionModal';
import { useStore } from '../store';
import { BookOpen, AlertTriangle, Edit3, ChevronDown, ChevronRight, User, Bot } from 'lucide-react';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const { currentUser, activeCitationMsgId, setActiveCitationMsgId } = useStore();
  const [showCorrection, setShowCorrection] = React.useState(false);

  const isUser = message.role === 'user';
  const citationsOpen = activeCitationMsgId === message.id;
  const hasCitations = (message.citations ?? []).length > 0;
  const hasViz = !!message.visualization;

  const toggleCitations = () => {
    setActiveCitationMsgId(citationsOpen ? null : message.id);
  };

  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className={`message-bubble ${isUser ? 'message-bubble--user' : 'message-bubble--assistant'}`}>
      {/* Avatar */}
      <div
        className="message-bubble__avatar"
        style={isUser ? { background: currentUser.avatar_color } : { background: '#334155' }}
      >
        {isUser ? <User size={14} color="#fff" /> : <Bot size={14} color="#94a3b8" />}
      </div>

      <div className="message-bubble__main">
        {/* Conflict banner */}
        {(message.conflict || (message.conflicts && message.conflicts.length > 0)) && (
          <div
            className="conflict-banner"
            style={{
              background: 'rgba(245, 158, 11, 0.15)',
              border: '1px solid var(--c-warn)',
              borderRadius: '6px',
              padding: '10px 12px',
              marginBottom: '10px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--c-warn)', fontWeight: 600 }}>
              <AlertTriangle size={16} />
              <span>Evidence Discrepancy / Note Conflict Detected</span>
            </div>
            {message.conflicts && message.conflicts.length > 0 ? (
              <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '12px', color: 'var(--c-text)' }}>
                {message.conflicts.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            ) : message.conflict_message ? (
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--c-text)' }}>{message.conflict_message}</p>
            ) : (
              <p style={{ margin: 0, fontSize: '12px', color: 'var(--c-text)' }}>
                Telemetry readings and operator field notes report conflicting production states. Both sources are preserved for engineering verification.
              </p>
            )}
          </div>
        )}

        {/* Text content */}
        <div className="message-bubble__text" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {message.content}
        </div>

        {/* Calculation explanation */}
        {message.calculation_explanation && (
          <div
            className="calculation-explanation"
            style={{
              marginTop: '8px',
              padding: '8px 12px',
              background: 'rgba(79, 123, 232, 0.1)',
              borderLeft: '3px solid var(--c-accent)',
              borderRadius: '0 4px 4px 0',
              fontSize: '12px',
              color: 'var(--c-text-muted)',
            }}
          >
            <strong style={{ color: 'var(--c-accent-h)' }}>Calculation Rule: </strong>
            {message.calculation_explanation}
          </div>
        )}

        {/* Data Freshness Tag */}
        {message.data_as_of && (
          <div style={{ fontSize: '11px', color: 'var(--c-text-muted)', marginTop: '4px' }}>
            📅 Data evaluated as of: <strong>{message.data_as_of}</strong>
          </div>
        )}

        {/* Visualization */}
        {hasViz && message.visualization && (
          <div className="message-bubble__viz" style={{ marginTop: '12px' }}>
            <VizRenderer spec={message.visualization} />
          </div>
        )}

        {/* Footer: time + action buttons */}
        <div className="message-bubble__footer">
          <span className="message-bubble__time">{time}</span>

          {!isUser && hasCitations && (
            <button
              className="msg-btn msg-btn--citations"
              onClick={toggleCitations}
              aria-expanded={citationsOpen}
            >
              <BookOpen size={12} />
              {(message.citations ?? []).length} source{(message.citations ?? []).length !== 1 ? 's' : ''}
              {citationsOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
            </button>
          )}

          {!isUser && (
            <button
              className="msg-btn msg-btn--correct"
              onClick={() => setShowCorrection(true)}
              title="Record a correction"
            >
              <Edit3 size={12} />
              Correct
            </button>
          )}
        </div>

        {/* Citations drawer (inline below message) */}
        {citationsOpen && hasCitations && (
          <CitationsDrawer
            citations={message.citations ?? []}
            onClose={() => setActiveCitationMsgId(null)}
          />
        )}
      </div>

      {/* Correction modal */}
      {showCorrection && (
        <CorrectionModal
          onClose={() => setShowCorrection(false)}
        />
      )}
    </div>
  );
}
