import React from 'react';
import type { ChatMessage, FeedbackRating } from '../types';
import { api } from '../api/client';
import { VizRenderer } from './viz/VizRenderer';
import { CitationsDrawer } from './CitationsDrawer';
import { CorrectionModal } from './CorrectionModal';
import { useStore } from '../store';
import { BookOpen, AlertTriangle, Edit3, ChevronDown, ChevronRight, User, Bot, Copy, Check, ThumbsUp, ThumbsDown, Send, Loader2, X } from 'lucide-react';

interface MessageBubbleProps {
  message: ChatMessage;
}

function renderInlineFormatting(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function renderMessageText(text: string): React.ReactNode {
  return text.split('\n').map((line, index, lines) => (
    <React.Fragment key={index}>
      {line ? renderInlineFormatting(line) : <br />}
      {index < lines.length - 1 && line ? <br /> : null}
    </React.Fragment>
  ));
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const { currentUser, histories, activeCitationMsgId, setActiveCitationMsgId, updateMessage } = useStore();
  const [showCorrection, setShowCorrection] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [feedbackRating, setFeedbackRating] = React.useState<FeedbackRating | null>(message.feedback?.rating ?? null);
  const [feedbackComment, setFeedbackComment] = React.useState(message.feedback?.comment ?? '');
  const [showFeedback, setShowFeedback] = React.useState(false);
  const [feedbackSubmitting, setFeedbackSubmitting] = React.useState(false);
  const [feedbackError, setFeedbackError] = React.useState<string | null>(null);

  const messages = histories[currentUser.user_id] ?? [];
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

  const handleCopyMarkdown = async () => {
    // Find preceding user question if available
    const myIndex = messages.findIndex((m) => m.id === message.id);
    let questionText = '';
    if (myIndex > 0) {
      for (let i = myIndex - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          questionText = messages[i].content;
          break;
        }
      }
    }

    const lines: string[] = [];
    if (questionText) {
      lines.push(`### Question\n${questionText}\n`);
    }
    lines.push(`### Answer\n${message.content}\n`);

    if (message.calculation_explanation) {
      lines.push(`### Calculation Rule\n${message.calculation_explanation}\n`);
    }

    if (message.conflict || (message.conflicts && message.conflicts.length > 0)) {
      lines.push('### Discrepancies & Conflicts');
      if (message.conflict_message) {
        lines.push(`- ${message.conflict_message}`);
      }
      if (message.conflicts) {
        message.conflicts.forEach((c) => lines.push(`- ${c}`));
      }
      lines.push('');
    }

    // Include table / data if visualization has tabular rows
    if (message.visualization && Array.isArray(message.visualization.data) && message.visualization.data.length > 0) {
      const data = message.visualization.data;
      const cols = message.visualization.columns || Object.keys(data[0]);
      lines.push(`### Data: ${message.visualization.title || 'Table'}`);
      lines.push(`| ${cols.join(' | ')} |`);
      lines.push(`| ${cols.map(() => '---').join(' | ')} |`);
      for (const row of data) {
        lines.push(`| ${cols.map((col) => String(row[col] ?? '—')).join(' | ')} |`);
      }
      lines.push('');
    }

    if (message.citations && message.citations.length > 0) {
      lines.push('### Citations');
      message.citations.forEach((c) => {
        const file = c.source_file || c.filename || 'Source Document';
        const sec = c.section ? ` · ${c.section}` : '';
        const rec = c.record_id || c.id ? ` · ID: ${c.record_id || c.id}` : '';
        const dt = c.date ? ` · Date: ${c.date}` : '';
        lines.push(`- **[${c.source_type}]** \`${file}\`${sec}${rec}${dt}`);
        if (c.excerpt) {
          lines.push(`  > "${c.excerpt}"`);
        }
      });
      lines.push('');
    }

    if (message.data_as_of) {
      lines.push(`*Data evaluated as of: ${message.data_as_of}*\n`);
    }

    const md = lines.join('\n');
    try {
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.warn('Clipboard write failed:', e);
    }
  };

  const openFeedback = (rating: FeedbackRating) => {
    setFeedbackRating(rating);
    setFeedbackError(null);
    setShowFeedback(true);
  };

  const cancelFeedback = () => {
    setFeedbackRating(message.feedback?.rating ?? null);
    setFeedbackComment(message.feedback?.comment ?? '');
    setFeedbackError(null);
    setShowFeedback(false);
  };

  const submitFeedback = async () => {
    if (!feedbackRating || feedbackSubmitting) return;
    setFeedbackSubmitting(true);
    setFeedbackError(null);
    const comment = feedbackComment.trim();
    try {
      await api.postFeedback({
        user_id: currentUser.user_id,
        message_id: message.id,
        rating: feedbackRating,
        comment: comment || null,
      });
      updateMessage(currentUser.user_id, message.id, {
        feedback: { rating: feedbackRating, ...(comment ? { comment } : {}) },
      });
      setFeedbackComment(comment);
      setShowFeedback(false);
    } catch (err) {
      setFeedbackError(err instanceof Error ? err.message : 'Feedback could not be saved.');
    } finally {
      setFeedbackSubmitting(false);
    }
  };

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
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid var(--c-warn)',
              borderRadius: '8px',
              padding: '12px 14px',
              marginBottom: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--c-warn)', fontWeight: 700, fontSize: '13px' }}>
              <AlertTriangle size={17} />
              <span>Evidence Discrepancy & Source Conflict Detected</span>
            </div>

            {/* Summary description */}
            <p style={{ margin: 0, fontSize: '12px', color: 'var(--c-text)', lineHeight: 1.5 }}>
              {message.conflict_message || (message.conflicts && message.conflicts[0]) ||
                'Telemetry readings, operational corrections, and operator field notes report conflicting production states. Both records are preserved for engineering verification.'}
            </p>

            {/* Side-by-side comparison of conflicting sources */}
            {message.citations && message.citations.filter((c) => c.source_type === 'note' || c.source_type === 'inspection').length >= 2 && (
              <div
                className="conflict-sources-grid"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '8px',
                  marginTop: '4px',
                }}
              >
                {message.citations
                  .filter((c) => c.source_type === 'note' || c.source_type === 'inspection')
                  .slice(0, 2)
                  .map((c, idx) => (
                    <div
                      key={c.id || idx}
                      style={{
                        background: 'var(--c-surface)',
                        border: '1px solid var(--c-border)',
                        borderRadius: '6px',
                        padding: '8px 10px',
                        fontSize: '11px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '4px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--c-accent-h)', fontWeight: 600 }}>
                        <span>Source {idx + 1}: {c.source_type === 'note' ? 'Human Note' : 'Inspection Record'}</span>
                        {c.date && <span style={{ color: 'var(--c-text-muted)' }}>{c.date}</span>}
                      </div>
                      <div style={{ color: 'var(--c-text)', fontStyle: 'italic', lineHeight: 1.4 }}>
                        "{c.excerpt}"
                      </div>
                      <div style={{ color: 'var(--c-text-muted)', fontSize: '10px' }}>
                        File: {c.source_file || c.filename} {c.record_id ? `· ID: ${c.record_id}` : ''}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        )}

        {/* Text content */}
        <div className="message-bubble__text" style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {renderMessageText(message.content)}
        </div>

        {/* Calculation explanation */}
        {message.calculation_explanation && (
          <details
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
            <summary style={{ cursor: 'pointer', color: 'var(--c-accent-h)', fontWeight: 700 }}>
              Calculation Rule
            </summary>
            <div style={{ marginTop: '6px' }}>{message.calculation_explanation}</div>
          </details>
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
              className="msg-btn msg-btn--copy"
              onClick={handleCopyMarkdown}
              title="Copy answer, data, and citations as Markdown"
            >
              {copied ? <Check size={12} color="var(--c-ok)" /> : <Copy size={12} />}
              {copied ? 'Copied!' : 'Copy as Markdown'}
            </button>
          )}

          {!isUser && (
            <>
              <span className="feedback-prompt" aria-live="polite">
                {message.feedback ? 'Feedback saved' : 'Helpful?'}
              </span>
              <button
                className={`msg-btn msg-btn--feedback ${feedbackRating === 'positive' ? 'is-selected' : ''}`}
                onClick={() => openFeedback('positive')}
                aria-label="Rate this answer helpful"
                aria-pressed={feedbackRating === 'positive'}
                title="This answer was helpful"
              >
                <ThumbsUp size={12} /> Yes
              </button>
              <button
                className={`msg-btn msg-btn--feedback ${feedbackRating === 'negative' ? 'is-selected' : ''}`}
                onClick={() => openFeedback('negative')}
                aria-label="Rate this answer as needing improvement"
                aria-pressed={feedbackRating === 'negative'}
                title="This answer needs improvement"
              >
                <ThumbsDown size={12} /> No
              </button>
            </>
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

        {!isUser && showFeedback && (
          <div className="feedback-panel">
            <label htmlFor={`feedback-comment-${message.id}`}>
              {feedbackRating === 'positive' ? 'What worked well?' : 'What should be improved?'}
              <span> Optional</span>
            </label>
            <textarea
              id={`feedback-comment-${message.id}`}
              value={feedbackComment}
              onChange={(event) => setFeedbackComment(event.target.value)}
              maxLength={2000}
              rows={2}
              placeholder="Share a short note; avoid sensitive information."
              disabled={feedbackSubmitting}
            />
            {feedbackError && <p className="feedback-panel__error" role="alert">{feedbackError}</p>}
            <div className="feedback-panel__actions">
              <button
                className="msg-btn"
                onClick={cancelFeedback}
                disabled={feedbackSubmitting}
              >
                <X size={12} /> Cancel
              </button>
              <button
                className="msg-btn msg-btn--feedback-submit"
                onClick={submitFeedback}
                disabled={feedbackSubmitting || !feedbackRating}
              >
                {feedbackSubmitting ? <Loader2 size={12} className="spin" /> : <Send size={12} />}
                {feedbackSubmitting ? 'Saving…' : 'Send feedback'}
              </button>
            </div>
          </div>
        )}

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
