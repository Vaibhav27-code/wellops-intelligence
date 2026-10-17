import { create } from 'zustand';
import { AppUser, ChatMessage, Correction } from '../types';

// ─── Users ────────────────────────────────────────────────────────────────────

export const USERS: AppUser[] = [
  { user_id: 'alice', display_name: 'Alice (Engineer)', avatar_color: '#4F7BE8' },
  { user_id: 'bob', display_name: 'Bob (Supervisor)', avatar_color: '#E8774F' },
  { user_id: 'carol', display_name: 'Carol (Regulator)', avatar_color: '#4FBE80' },
];

export const EXAMPLE_QUESTIONS = [
  'Which wells were down the longest this summer, and why?',
  'Show me all wells with unresolved spill violations.',
  'What is the downtime for well W-101 this year?',
  'Which wells missed their inspection last week?',
  'Show a trend of inspections for area North over the past 6 months.',
  'Are there any spills >= 5 bbl that were not reported within 24 hours?',
  'Compare downtime across well types.',
  'What does the SOP say about shut-in procedures?',
  'List the top 5 wells by number of repairs in the last year.',
  'Which wells have both a spill and a failed inspection in the same month?',
];

// ─── Zustand Store ────────────────────────────────────────────────────────────

interface Store {
  // Auth
  currentUser: AppUser;
  setUser: (user: AppUser) => void;

  // Per-user private chat histories (key = user_id)
  histories: Record<string, ChatMessage[]>;
  addMessage: (userId: string, msg: ChatMessage) => void;
  clearHistory: (userId: string) => void;

  // Shared corrections
  corrections: Correction[];
  addCorrection: (c: Correction) => void;

  // UI state
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  activeCitationMsgId: string | null;
  setActiveCitationMsgId: (id: string | null) => void;
}

export const useStore = create<Store>((set) => ({
  currentUser: USERS[0],
  setUser: (user) => set({ currentUser: user }),

  histories: {},
  addMessage: (userId, msg) =>
    set((s) => ({
      histories: {
        ...s.histories,
        [userId]: [...(s.histories[userId] ?? []), msg],
      },
    })),
  clearHistory: (userId) =>
    set((s) => {
      const { [userId]: _, ...rest } = s.histories;
      return { histories: rest };
    }),

  corrections: [],
  addCorrection: (c) =>
    set((s) => ({ corrections: [...s.corrections, c] })),

  isSidebarOpen: false,
  toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
  activeCitationMsgId: null,
  setActiveCitationMsgId: (id) => set({ activeCitationMsgId: id }),
}));
