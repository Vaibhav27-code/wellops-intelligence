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
  const { currentUser, histories, addMessage } = useStore();
  const messages = histories[currentUser.user_id] ?? [];

  const [input, setInput] = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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
      const errMsg = err instanceof Error ? err.message : 'Unknown error';
      // Add error as assistant message so it's in context
      addMessage(currentUser.user_id, {
        id: nextId(),
        role: 'assistant',
        content: `⚠️ Could not reach the backend: ${errMsg}. Make sure the server is running on port 8000.`,
        timestamp: new Date().toISOString(),
      });
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="chat-thread">
      {/* Message list */}
      <div className="chat-thread__messages">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <p className="chat-empty__headline">
              Ask anything about your wells.
            </p>
            <ExampleChips onSelect={(q) => { send(q); }} />
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
            placeholder="Ask about well downtime, spills, inspections, repairs…"
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
        <p className="chat-hint">Enter to send · Shift+Enter for newline</p>
      </div>
    </div>
  );
}
