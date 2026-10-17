import { create } from 'zustand';
import type { AppUser, ChatMessage, Correction } from '../types';

// ─── Color Palette for User Avatars ──────────────────────────────────────────
const AVATAR_COLORS = [
  '#4F7BE8', '#E8774F', '#4FBE80', '#A855F7', '#EC4899',
  '#06B6D4', '#EAB308', '#84CC16', '#F97316', '#6366F1',
  '#14B8A6', '#F43F5E', '#8B5CF6', '#10B981', '#3B82F6'
];

export function formatRole(role?: string): string {
  if (!role) return 'Operator';
  return role
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function buildAppUser(
  raw: { user_id: string; name: string; role: string; team_id?: string },
  idx = 0
): AppUser {
  return {
    user_id: raw.user_id,
    name: raw.name,
    role: raw.role,
    team_id: raw.team_id,
    display_name: `${raw.name} (${formatRole(raw.role)})`,
    avatar_color: AVATAR_COLORS[idx % AVATAR_COLORS.length],
  };
}

// 15 Default Users from fleet/users.json
export const DEFAULT_USERS: AppUser[] = [
  { user_id: 'U-101', name: 'Emily Carter', role: 'production_supervisor', team_id: 'TEAM-SW', display_name: 'Emily Carter (Production Supervisor)', avatar_color: AVATAR_COLORS[0] },
  { user_id: 'U-102', name: 'Jake Morales', role: 'field_operator', team_id: 'TEAM-SW', display_name: 'Jake Morales (Field Operator)', avatar_color: AVATAR_COLORS[1] },
  { user_id: 'U-103', name: 'Sarah Mitchell', role: 'field_inspector', team_id: 'TEAM-SW', display_name: 'Sarah Mitchell (Field Inspector)', avatar_color: AVATAR_COLORS[2] },
  { user_id: 'U-104', name: 'Ryan Brooks', role: 'field_inspector', team_id: 'TEAM-SW', display_name: 'Ryan Brooks (Field Inspector)', avatar_color: AVATAR_COLORS[3] },
  { user_id: 'U-201', name: 'Michael Turner', role: 'production_supervisor', team_id: 'TEAM-NE', display_name: 'Michael Turner (Production Supervisor)', avatar_color: AVATAR_COLORS[4] },
  { user_id: 'U-202', name: 'Jessica Reed', role: 'field_inspector', team_id: 'TEAM-NE', display_name: 'Jessica Reed (Field Inspector)', avatar_color: AVATAR_COLORS[5] },
  { user_id: 'U-203', name: 'Ashley Bennett', role: 'field_inspector', team_id: 'TEAM-NE', display_name: 'Ashley Bennett (Field Inspector)', avatar_color: AVATAR_COLORS[6] },
  { user_id: 'U-204', name: 'Tyler Hughes', role: 'field_operator', team_id: 'TEAM-NE', display_name: 'Tyler Hughes (Field Operator)', avatar_color: AVATAR_COLORS[7] },
  { user_id: 'U-301', name: 'Robert Hayes', role: 'maintenance_lead', team_id: 'TEAM-MX', display_name: 'Robert Hayes (Maintenance Lead)', avatar_color: AVATAR_COLORS[8] },
  { user_id: 'U-302', name: 'Daniel Foster', role: 'maintenance_technician', team_id: 'TEAM-MX', display_name: 'Daniel Foster (Maintenance Technician)', avatar_color: AVATAR_COLORS[9] },
  { user_id: 'U-303', name: 'Kevin Price', role: 'maintenance_technician', team_id: 'TEAM-MX', display_name: 'Kevin Price (Maintenance Technician)', avatar_color: AVATAR_COLORS[10] },
  { user_id: 'U-304', name: 'Brian Coleman', role: 'maintenance_technician', team_id: 'TEAM-MX', display_name: 'Brian Coleman (Maintenance Technician)', avatar_color: AVATAR_COLORS[11] },
  { user_id: 'U-305', name: 'Megan Ward', role: 'maintenance_technician', team_id: 'TEAM-MX', display_name: 'Megan Ward (Maintenance Technician)', avatar_color: AVATAR_COLORS[12] },
  { user_id: 'U-401', name: 'Laura Simmons', role: 'hse_officer', team_id: 'TEAM-HSE', display_name: 'Laura Simmons (Hse Officer)', avatar_color: AVATAR_COLORS[13] },
  { user_id: 'U-402', name: 'Chris Dalton', role: 'hse_officer', team_id: 'TEAM-HSE', display_name: 'Chris Dalton (Hse Officer)', avatar_color: AVATAR_COLORS[14] },
];

export interface GroupedQuestion {
  id: string;
  label: string;
  question: string;
  group: 'single_well' | 'area_analysis' | 'compliance' | 'memory_corrections';
  suggestedUser?: string;
  suggestedUserId?: string;
}

export const ALL_18_QUESTIONS: GroupedQuestion[] = [
  // ── Single Well ──
  {
    id: 'Q1',
    label: 'Q1: Status Card',
    question: 'Is WELL-0001 producing oil right now? When was it last inspected, and by whom? Show me its status card.',
    group: 'single_well',
  },
  {
    id: 'Q3',
    label: 'Q3: Temp Trend',
    question: "Show a line chart of WELL-0001's wellhead temperature against air temperature for the last 13 weeks.",
    group: 'single_well',
  },
  {
    id: 'Q4',
    label: 'Q4: 4-Yr Spills',
    question: 'How many oil spills has WELL-0001 had in the last 4 years, and how much oil in total?',
    group: 'single_well',
  },
  {
    id: 'Q5',
    label: 'Q5: 2025 Downtime',
    question: 'How many days was WELL-0001 down in 2025?',
    group: 'single_well',
  },

  // ── Area Analysis ──
  {
    id: 'Q2',
    label: 'Q2: Non-Producing',
    question: 'Which wells in Northeast Block 8 are not producing oil right now, and why? Show them in a table.',
    group: 'area_analysis',
  },
  {
    id: 'Q6',
    label: 'Q6: Top Downtime',
    question: 'Which 3 wells in Northeast Block 7 had the most downtime in the last 4 months?',
    group: 'area_analysis',
  },
  {
    id: 'Q7',
    label: 'Q7: 90-Day Map',
    question: 'Show on a map every well in Northeast Block 8 with a real spill in the last 90 days.',
    group: 'area_analysis',
  },
  {
    id: 'Q8',
    label: 'Q8: Spills Heatmap',
    question: 'Show a heatmap of 2026 spills by geographic area and month.',
    group: 'area_analysis',
  },

  // ── Compliance ──
  {
    id: 'Q9',
    label: 'Q9: Compliance',
    question: 'Which rules has WELL-0001 broken in the last 12 months, and what is still open?',
    group: 'compliance',
  },
  {
    id: 'Q10',
    label: 'Q10: Containment',
    question: 'In Southwest Block 24, which spills in the last 90 days were not contained within the SOP time limit?',
    group: 'compliance',
  },

  // ── Memory & Corrections ──
  {
    id: 'Q11',
    label: 'Q11: Prior Chat Costs',
    question: 'For the three wells we discussed yesterday, what have repairs cost this year?',
    group: 'memory_corrections',
    suggestedUser: 'Michael Turner',
    suggestedUserId: 'U-201',
  },
  {
    id: 'Q12',
    label: 'Q12: Temp Correction',
    question: 'The 15 Oct reading for WELL-0164 is wrong; the field crew re-measured the wellhead at 41.0 °C.',
    group: 'memory_corrections',
    suggestedUser: 'Michael Turner',
    suggestedUserId: 'U-201',
  },
  {
    id: 'Q13',
    label: 'Q13: Spill Correction',
    question: 'The spill at WELL-0151 was measured by field crew at 5.4 bbl, not the 4.5 bbl AI estimate.',
    group: 'memory_corrections',
    suggestedUser: 'Michael Turner',
    suggestedUserId: 'U-201',
  },
  {
    id: 'Q14',
    label: 'Q14: Rule Override',
    question: 'Team now wants root-cause investigations on T350 wells after 2 pump jack repairs in a year, instead of 3. Which wells in Northeast Block 7 qualify now?',
    group: 'memory_corrections',
    suggestedUser: 'Michael Turner',
    suggestedUserId: 'U-201',
  },
  {
    id: 'Q15',
    label: 'Q15: Shared Truth',
    question: 'Is WELL-0164 producing oil right now? Show status card.',
    group: 'memory_corrections',
    suggestedUser: 'Jessica Reed',
    suggestedUserId: 'U-202',
  },
  {
    id: 'Q16',
    label: 'Q16: Isolated Recall',
    question: 'For the three wells we discussed yesterday, what have repairs cost this year?',
    group: 'memory_corrections',
    suggestedUser: 'Jessica Reed',
    suggestedUserId: 'U-202',
  },
  {
    id: 'Q17',
    label: 'Q17: Unconfirmed Note',
    question: 'Tyler Hughes says WELL-0175 is running fine and not shut in. Is that correct?',
    group: 'memory_corrections',
    suggestedUser: 'Tyler Hughes',
    suggestedUserId: 'U-204',
  },
  {
    id: 'Q18',
    label: 'Q18: Dispute Check',
    question: 'Did WELL-0101 have a confirmed crude oil spill on 20 Aug 2026?',
    group: 'memory_corrections',
    suggestedUser: 'Chris Dalton',
    suggestedUserId: 'U-402',
  },
];

// ─── Zustand Store ────────────────────────────────────────────────────────────

interface Store {
  // Auth & users
  users: AppUser[];
  setUsers: (users: AppUser[]) => void;
  currentUser: AppUser;
  setUser: (user: AppUser) => void;

  // Per-user private chat histories (key = user_id)
  histories: Record<string, ChatMessage[]>;
  addMessage: (userId: string, msg: ChatMessage) => void;
  updateMessage: (userId: string, messageId: string, updates: Partial<ChatMessage>) => void;
  clearHistory: (userId: string) => void;

  // Shared corrections
  corrections: Correction[];
  setCorrections: (corrections: Correction[]) => void;
  addCorrection: (c: Correction) => void;

  // UI state
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  activeCitationMsgId: string | null;
  setActiveCitationMsgId: (id: string | null) => void;
}

export const useStore = create<Store>((set) => ({
  users: DEFAULT_USERS,
  setUsers: (users) => set({ users, currentUser: users[0] ?? DEFAULT_USERS[0] }),
  currentUser: DEFAULT_USERS[4], // Michael Turner default for operational scenarios
  setUser: (user) => set({ currentUser: user }),

  histories: {},
  addMessage: (userId, msg) =>
    set((s) => ({
      histories: {
        ...s.histories,
        [userId]: [...(s.histories[userId] ?? []), msg],
      },
    })),
  updateMessage: (userId, messageId, updates) =>
    set((s) => ({
      histories: {
        ...s.histories,
        [userId]: (s.histories[userId] ?? []).map((message) =>
          message.id === messageId ? { ...message, ...updates } : message
        ),
      },
    })),
  clearHistory: (userId) =>
    set((s) => {
      const { [userId]: _, ...rest } = s.histories;
      return { histories: rest };
    }),

  corrections: [],
  setCorrections: (corrections) => set({ corrections }),
  addCorrection: (c) =>
    set((s) => ({ corrections: [...s.corrections, c] })),

  isSidebarOpen: false,
  toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
  activeCitationMsgId: null,
  setActiveCitationMsgId: (id) => set({ activeCitationMsgId: id }),
}));
