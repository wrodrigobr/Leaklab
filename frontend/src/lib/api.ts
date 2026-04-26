const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:5000";

function token(): string | null {
  return sessionStorage.getItem("ll_token");
}

function authHeaders(): HeadersInit {
  const t = token();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...init.headers,
    },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
  return data as T;
}

// ── Auth ─────────────────────────────────────────────────────────────────────

export interface AuthResponse {
  token: string;
  user_id: number;
  role: string;
}

export interface UserProfile {
  user_id: number;
  username: string;
  email: string;
  role: string;
  coach_id: number | null;
  coach_username: string | null;
}

export const auth = {
  register: (username: string, email: string, password: string, role: "player" | "coach" = "player") =>
    request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password, role }),
    }),

  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request<UserProfile>("/auth/me"),

  updateEmail: (email: string, current_password: string) =>
    request<{ ok: boolean; email: string }>("/auth/update-email", {
      method: "POST",
      body: JSON.stringify({ email, current_password }),
    }),

  changePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
};

// ── Tournaments ───────────────────────────────────────────────────────────────

export interface Tournament {
  id: number;
  tournament_id: string;
  site: string;
  hero: string;
  played_at: string | null;
  imported_at: string;
  hands_count: number;
  decisions_count: number;
  avg_score: number | null;
  standard_pct: number | null;
  clear_pct: number | null;
  result: string | null;
  place: number | null;
  buy_in: number | null;
  prize: number | null;
  profit: number | null;
  llm_summary: string | null;
}

export interface TournamentsResponse {
  tournaments: Tournament[];
}

export interface TournamentDecision {
  id: number;
  tournament_id: number;
  hand_id: string;
  street: string;
  hero_cards: string;
  board: string;
  action_taken: string;
  best_action: string;
  label: "standard" | "small_mistake" | "clear_mistake" | "marginal";
  score: number;
  math_penalty: number;
  range_penalty: number;
  m_ratio: number | null;
  icm_pressure: string | null;
  stack_bb: number | null;
  draw_profile: string;
  position: string | null;
  num_players: number | null;
  level_sb: number | null;
  level_bb: number | null;
  level_num: number | null;
  note: string | null;
}

export interface ReplaySeat {
  player: string;
  stack: number;
  stack_bb: number;
  pos: string;
}

export interface ShowdownSeatInfo {
  seat:      number;
  player:    string;
  cards:     string[];
  won:       number;
  hand_desc: string;
  outcome:   "won" | "lost";
}

export interface ReplayStep {
  type: "deal" | "street" | "action" | "showdown";
  desc: string;
  street: string;
  seats: Record<string, ReplaySeat>;
  hero: string;
  hero_cards: string[];
  board: string[];
  pot: number;
  pot_bb: number;
  bets: Record<string, number>;
  folded: string[];
  bb: number;
  button: number;
  // action-specific
  player?: string;
  seat?: number;
  action?: string;
  amount?: number;
  is_hero?: boolean;
  is_error?: boolean;
  error_label?: string;
  error_score?: number;
  best_action?: string;
  // error details
  pot_odds_equity?: number;
  hand_equity?: number;
  m_ratio?: number;
  icm_pressure?: string;
  hero_stack_bb?: number;
  // showdown-specific
  revealed_cards?: Record<string, string[]>; // seat_num → ["Ah","Kd"]
  summary?: {
    total_pot: number | null;
    board:     string[];
    seats:     ShowdownSeatInfo[];
    winners:   ShowdownSeatInfo[];
  };
}

export interface ReplayData {
  hand_id: string;
  tournament_id: string;
  hero: string;
  hero_cards: string[];
  board: string[];
  button: number;
  sb: number;
  bb: number;
  seats: Record<string, { player: string; stack: number; pos: string }>;
  timeline: ReplayStep[];
}

export const tournaments = {
  list: () => request<TournamentsResponse>("/history/tournaments"),

  get: (tournamentId: string) =>
    request<{ tournament: Tournament; decisions: TournamentDecision[] }>(
      `/history/tournament/${tournamentId}`
    ),

  analyze: (content: string) =>
    request<{
      tournament_id: string;
      tournament_db_id: number;
      hero: string;
      total_hands: number;
      metrics: Record<string, unknown>;
      leaks: unknown[];
      hands: Record<string, unknown>;
    }>("/analyze", {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  summary: (dbId: number) =>
    request<{ summary: string; hero: string }>("/analyze/tournament-summary", {
      method: "POST",
      body: JSON.stringify({ tournament_id: dbId }),
    }),

  replay: (tournamentId: string, handId: string) =>
    request<ReplayData>(`/replay/${tournamentId}/${handId}`),

  analyzeDecision: (decisionId: number) =>
    request<{ analysis: string; cached: boolean }>("/analyze/decision", {
      method: "POST",
      body: JSON.stringify({ decision_id: decisionId }),
    }),

  deleteOne: (tournamentId: string) =>
    request<{ ok: boolean }>(`/history/tournament/${tournamentId}`, {
      method: "DELETE",
    }),

  clearAll: () =>
    request<{ ok: boolean; message: string }>("/admin/reset-my-data", {
      method: "POST",
    }),
};

// ── Evolution / KPIs ──────────────────────────────────────────────────────────

export interface EvolutionPoint {
  tournament_id: string;
  played_at: string | null;
  imported_at: string;
  avg_score: number;
  standard_pct: number;
  buy_in: number | null;
  prize: number | null;
  profit: number | null;
}

export interface EvolutionResponse {
  evolution: EvolutionPoint[];
  leaks: {
    spot: string;
    n: number;
    avg_score: number;
  }[];
  icm: Record<string, { n: number; avg_score: number; standard_rate: number }>;
}

export interface BreakdownStat {
  n: number;
  avg_score: number;
  standard_rate: number;
}

export interface BreakdownResponse {
  by_street:   Record<string, BreakdownStat>;
  by_position: Record<string, BreakdownStat>;
  by_label:    Record<string, number>;
}

export interface PlayerStatsResponse {
  total_hands: number;
  vpip: number | null;
  pfr: number | null;
  af: number | null;
  flop_bet_pct: number | null;
  fold_to_3bet: number | null;
  wtsd: number | null;
  three_bet: number | null;
  w_at_sd: number | null;
}

export const metrics = {
  evolution: (days = 90) =>
    request<EvolutionResponse>(`/history/evolution?days=${days}`),

  breakdown: (days = 90) =>
    request<BreakdownResponse>(`/history/breakdown?days=${days}`),

  playerStats: (days = 90) =>
    request<PlayerStatsResponse>(`/metrics/player-stats?days=${days}`),
};

// ── Study Plan ────────────────────────────────────────────────────────────────

export interface StudyCardResources {
  livros: string[];
  videos: string[];
  curso: string | null;
}

export interface StudyCard {
  prioridade: string;
  icone: string;
  titulo: string;
  diagnostico: string;
  conceitos: string[];
  recursos: StudyCardResources;
  exercicio: string;
  metrica: string;
  spot: string;
}

export interface StudyPlanResponse {
  nivel: string;
  resumo: string;
  cards: StudyCard[];
  error?: string;
  coach_managed?: boolean;
}

export const study = {
  plan: (days = 90, forceNew = false) =>
    request<StudyPlanResponse>(`/study/plan?days=${days}${forceNew ? "&new=1" : ""}`),
};

// ── AI Coach ─────────────────────────────────────────────────────────────────

export interface CoachMessage {
  id: number;
  role: "user" | "ai";
  content: string;
}

export interface CoachContext {
  hands_analyzed: number;
  tournaments_analyzed: number;
  top_leaks: { spot: string; avg_score: number; n: number }[];
  avg_score: number | null;
  standard_pct: number | null;
}

export const coach = {
  chat: (message: string) =>
    request<{ reply: string }>("/coach/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  context: () => request<CoachContext>("/coach/context"),
};

// ── Coach Dashboard (human coach, not AI) ────────────────────────────────────

export interface CoachProfile {
  user_id: number;
  username: string;
  email: string;
  display_name: string;
  bio: string;
  specialties: string[];
  contact_email: string | null;
  contact_link: string | null;
  is_public: boolean;
  student_count: number;
  invite_key: string | null;
}

export interface StudentSummary {
  id: number;
  username: string;
  email: string;
  created_at: string;
  total_tournaments: number;
  recent_tournament: Tournament | null;
  trend: "improving" | "worsening" | "stable" | null;
}

export interface CoachImpactStudent {
  student_id: number;
  username: string;
  tournament_count: number;
  avg_score: number | null;
  best_score: number | null;
  standard_pct: number | null;
  last_activity: string | null;
  prev_avg_score: number | null;
  improvement_pct: number | null;
}

export interface CoachImpactResponse {
  students: CoachImpactStudent[];
  top_leaks: { spot: string; n: number; avg_score: number }[];
  summary: {
    total_students: number;
    active_students: number;
    avg_improvement_pct: number | null;
    best_student: string | null;
  };
}

export interface StudentHistory {
  student_id: number;
  evolution: EvolutionPoint[];
  leaks: { spot: string; n: number; avg_score: number }[];
  icm: Record<string, { n: number; avg_score: number; standard_rate: number }>;
  tournaments: Tournament[];
}

export interface StudentWorstDecision {
  id: number;
  hand_id: string;
  street: string;
  hero_cards: string;
  board: string;
  action_taken: string;
  best_action: string;
  label: string;
  score: number;
  position: string | null;
  icm_pressure: string | null;
  m_ratio: number | null;
  stack_bb: number | null;
  tournament_id: string;
  site: string;
}

export const coachDashboard = {
  inviteKey: () =>
    request<{ invite_key: string }>("/coach/invite-key"),

  getProfile: () =>
    request<CoachProfile>("/coach/profile"),

  saveProfile: (data: Partial<CoachProfile>) =>
    request<CoachProfile>("/coach/profile", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  students: () =>
    request<{ students: StudentSummary[] }>("/coach/students"),

  studentHistory: (studentId: number, days = 30) =>
    request<StudentHistory>(`/coach/student/${studentId}/history?days=${days}`),

  studentStats: (studentId: number, days = 90) =>
    request<PlayerStatsResponse>(`/coach/student/${studentId}/stats?days=${days}`),

  studentBreakdown: (studentId: number, days = 90) =>
    request<BreakdownResponse>(`/coach/student/${studentId}/breakdown?days=${days}`),

  studentTournament: (studentId: number, tournamentId: string) =>
    request<{ tournament: Tournament; decisions: TournamentDecision[] }>(
      `/coach/student/${studentId}/tournament/${tournamentId}`
    ),

  studentWorstDecisions: (studentId: number, n = 20) =>
    request<{ decisions: StudentWorstDecision[] }>(
      `/coach/student/${studentId}/worst-decisions?n=${n}`
    ),

  studentStudyPlan: (studentId: number, days = 90, forceNew = false) =>
    request<StudyPlanResponse>(`/coach/student/${studentId}/study-plan?days=${days}${forceNew ? "&new=1" : ""}`),

  studentReplay: (studentId: number, tournamentId: string, handId: string) =>
    request<ReplayData>(`/coach/student/${studentId}/replay/${tournamentId}/${handId}`),

  getStudyOverrides: (studentId: number) =>
    request<{ overrides: StudyOverride[] }>(`/coach/student/${studentId}/study-overrides`),

  saveStudyOverride: (studentId: number, data: {
    card_spot: string;
    status: "validated" | "commented" | "replaced";
    note?: string;
    custom_card?: Partial<StudyCard>;
  }) =>
    request<StudyOverride>(`/coach/student/${studentId}/study-overrides`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteStudyOverride: (studentId: number, cardSpot: string) =>
    request<{ ok: boolean }>(`/coach/student/${studentId}/study-overrides/${encodeURIComponent(cardSpot)}`, {
      method: "DELETE",
    }),

  impact: (days = 30) =>
    request<CoachImpactResponse>(`/coach/impact?days=${days}`),
};

export interface StudyOverride {
  id: number;
  coach_id: number;
  student_id: number;
  card_spot: string;
  status: "validated" | "commented" | "replaced";
  note: string | null;
  custom_card: string | null;
  created_at: string;
}

// ── Student side ─────────────────────────────────────────────────────────────

export const student = {
  linkCoach: (invite_key: string) =>
    request<{ message: string; coach: { id: number; username: string } }>(
      "/student/link-coach",
      { method: "POST", body: JSON.stringify({ invite_key }) }
    ),

  unlinkCoach: (password: string) =>
    request<{ ok: boolean }>("/student/coach", {
      method: "DELETE",
      body: JSON.stringify({ password }),
    }),
};
