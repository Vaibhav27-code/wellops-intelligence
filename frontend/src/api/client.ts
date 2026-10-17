import type { ChatRequest, ChatResponse, FeedbackRequest, FeedbackRating } from '../types';

const localApiOverride = import.meta.env.DEV && typeof window !== 'undefined'
  ? new URLSearchParams(window.location.search).get('api')
  : null;
const BASE_URL = localApiOverride ?? import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  chat: (body: ChatRequest) =>
    request<ChatResponse>('/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  postFeedback: (body: FeedbackRequest) =>
    request<{ feedback_id: string; rating: FeedbackRating; status: string }>('/feedback', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getUsers: () =>
    request<{ users: Array<{ user_id: string; name: string; role: string; team_id?: string }> }>('/users'),

  getWell: (wellId: string) =>
    request<Record<string, unknown>>(`/wells/${encodeURIComponent(wellId)}`),

  searchWells: (q: string) =>
    request<{ wells: Record<string, unknown>[] }>(`/wells/search?q=${encodeURIComponent(q)}`),

  getCorrections: () =>
    request<{ corrections: Record<string, unknown>[] }>('/corrections'),

  postCorrection: (body: Record<string, unknown>) =>
    request<{ correction_id: string }>('/corrections', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  getPrivateHistory: (userId: string) =>
    request<{ messages: Record<string, unknown>[] }>(
      `/memory/private/${encodeURIComponent(userId)}`
    ),
};
