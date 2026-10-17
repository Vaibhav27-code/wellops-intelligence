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
        {message.conflict && (
          <div className="conflict-banner">
            <AlertTriangle size={14} />
            Conflicting data detected — answer may be uncertain.
          </div>
        )}

        {/* Text content */}
        <div className="message-bubble__text">
          {message.content}
        </div>

        {/* Visualization */}
        {hasViz && message.visualization && (
          <div className="message-bubble__viz">
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
