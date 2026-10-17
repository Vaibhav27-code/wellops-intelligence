// ─── Core Domain Types ────────────────────────────────────────────────────────

export interface Well {
  well_id: string;
  well_name: string;
  well_type: string;
  location?: string;
  operator?: string;
  status?: string;
  latitude?: number;
  longitude?: number;
  api_number?: string;
  field?: string;
  county?: string;
  state?: string;
  spud_date?: string;
  production_start_date?: string;
  total_depth_ft?: number;
  [key: string]: unknown;
}

export interface Inspection {
  inspection_id: string;
  well_id: string;
  inspection_date: string;
  inspector?: string;
  result?: string;
  producing: boolean;
  notes?: string;
}

export interface Repair {
  repair_id: string;
  well_id: string;
  start_date: string;
  end_date?: string;
  description?: string;
  cost?: number;
  planned: boolean;
}

export interface RegulatoryEvent {
  event_id: string;
  well_id: string;
  event_date: string;
  event_type: string;
  volume_bbl?: number;
  reported_within_24h?: boolean;
  description?: string;
}

export interface HumanNote {
  note_id: string;
  well_id: string;
  author: string;
  created_at: string;
  content: string;
}

// ─── Chat & Pipeline ──────────────────────────────────────────────────────────

export interface Citation {
  id: string;
  source_type: 'well' | 'inspection' | 'repair' | 'regulatory' | 'note' | 'manual' | 'correction';
  source_file?: string;
  record_id?: string;
  section?: string;
  excerpt?: string;
  well_id?: string;
  date?: string;
}

export type VizType = 'card' | 'table' | 'line' | 'bar' | 'map' | 'heatmap';

export interface VisualizationSpec {
  type: VizType;
  title: string;
  data: Record<string, unknown>[];
  x?: string;
  y?: string | string[];
  units?: string;
  columns?: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  visualization?: VisualizationSpec;
  timestamp: string;
  conflict?: boolean;
}

// ─── Users & Memory ───────────────────────────────────────────────────────────

export interface AppUser {
  user_id: string;
  display_name: string;
  avatar_color: string;
}

export interface Correction {
  correction_id: string;
  scope: 'well' | 'well_type';
  well_id?: string;
  well_type?: string;
  field: string;
  original_value: unknown;
  corrected_value: unknown;
  author: string;
  created_at: string;
  reason: string;
  evidence?: string;
}

// ─── API Payloads ─────────────────────────────────────────────────────────────

export interface ChatRequest {
  question: string;
  user_id: string;
  session_id?: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  visualization?: VisualizationSpec;
  conflict?: boolean;
  conflict_message?: string;
}
