import React from 'react';
import { useStore } from '../store';
import { api } from '../api/client';
import type { ChatMessage } from '../types';
import { MessageBubble } from './MessageBubble';
import { ExampleChips } from './ExampleChips';
import { Send, Loader2 } from 'lucide-react';

let msgIdCounter = 0;
const nextId = () => `msg-${++msgIdCounter}-${Date.now()}`;

export function ChatThread() {
  const { currentUser, histories, addMessage, clearHistory } = useStore();
  const messages = histories[currentUser.user_id] ?? [];

  const [input, setInput] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showChips, setShowChips] = React.useState(false);

  const bottomRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, loading]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setInput('');
    setError(null);

    // Optimistically add user message
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: q,
      timestamp: new Date().toISOString(),
    };
    addMessage(currentUser.user_id, userMsg);

    setLoading(true);
    try {
      const res = await api.chat({
        question: q,
        user_id: currentUser.user_id,
      });

      const assistantMsg: ChatMessage = {
        id: nextId(),
        role: 'assistant',
        content: res.answer_text || res.answer,
        citations: res.citations,
        visualization: res.visualization,
        conflict: res.conflict,
        conflicts: res.conflicts,
        conflict_message: res.conflict_message,
        calculation_explanation: res.calculation_explanation,
        data_as_of: res.data_as_of,
        timestamp: new Date().toISOString(),
      };
      addMessage(currentUser.user_id, assistantMsg);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Unknown network/server error';
      // Add readable error as assistant message so it is preserved in context
      addMessage(currentUser.user_id, {
        id: nextId(),
        role: 'assistant',
        content: `⚠️ Error from Copilot Backend (${errMsg}). Please check if the server is running on http://localhost:8000.`,
        timestamp: new Date().toISOString(),
      });
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleChipSelect = (q: string) => {
    setInput(q);
    send(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="chat-thread">
      {/* Header bar with quick access to benchmark chips */}
      <div
        className="chat-thread__topbar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 16px',
          background: 'var(--c-surface)',
          borderBottom: '1px solid var(--c-border)',
          fontSize: '12px',
        }}
      >
        <span style={{ color: 'var(--c-text-muted)' }}>
          Active User: <strong style={{ color: 'var(--c-accent-h)' }}>{currentUser.display_name}</strong>
          {' '}(Private Thread)
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => clearHistory(currentUser.user_id)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px',
              padding: '3px 8px',
              borderRadius: '4px',
              background: 'var(--c-surface2)',
              border: '1px solid var(--c-border)',
              color: 'var(--c-text)',
              fontWeight: 600,
              fontSize: '11px',
              cursor: 'pointer',
            }}
            title="Start a fresh chat session for this user"
          >
            + New session
          </button>
          <button
            onClick={() => setShowChips((s) => !s)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 10px',
              borderRadius: '4px',
              background: showChips ? 'var(--c-accent)' : 'var(--c-surface2)',
              color: '#fff',
              fontWeight: 600,
              fontSize: '11px',
            }}
            title="Toggle 18 benchmark question chips"
          >
            {showChips ? 'Hide Benchmark Questions' : '⚡ Benchmark Questions (Q1–Q18)'}
          </button>
        </div>
      </div>

      {/* Expandable chips drawer if toggled */}
      {showChips && (
        <div
          style={{
            padding: '12px 16px',
            background: 'var(--c-surface2)',
            borderBottom: '1px solid var(--c-border)',
            maxHeight: '260px',
            overflowY: 'auto',
          }}
        >
          <ExampleChips onSelect={handleChipSelect} />
        </div>
      )}

      {/* Message list */}
      <div className="chat-thread__messages">
        {messages.length === 0 && !loading && !showChips && (
          <div className="chat-empty">
            <p className="chat-empty__headline">
              Asset Intelligence Copilot
            </p>
            <p style={{ color: 'var(--c-text-muted)', fontSize: '13px', marginBottom: '16px' }}>
              Ask plain-English questions about well operations, downtime calculations, oil spills, and regulatory compliance.
            </p>
            <ExampleChips onSelect={handleChipSelect} />
          </div>
        )}

        {messages.map((msg: ChatMessage) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {loading && (
          <div className="message-bubble message-bubble--assistant">
            <div className="message-bubble__avatar" style={{ background: '#334155' }}>
              <Loader2 size={14} className="spin" color="#94a3b8" />
            </div>
            <div className="message-bubble__main">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="chat-thread__input-area">
        {error && <p className="chat-input-error">{error}</p>}
        <div className="chat-input-row">
          <textarea
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about well downtime, spills, inspections, repairs… or pick a question above"
            rows={2}
            disabled={loading}
            aria-label="Chat input"
          />
          <button
            className="chat-send-btn"
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            aria-label="Send"
          >
            {loading ? <Loader2 size={18} className="spin" /> : <Send size={18} />}
          </button>
        </div>
        <p className="chat-hint">Enter to send · Shift+Enter for newline · Queries execute as {currentUser.name}</p>
      </div>
    </div>
  );
}
