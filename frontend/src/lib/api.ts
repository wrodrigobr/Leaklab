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
  const text = await res.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(`Erro do servidor (HTTP ${res.status})`);
    }
  }
  if (!res.ok) throw new Error((data.error as string) ?? `HTTP ${res.status}`);
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
  plan: string;
  tournaments_used: number;
  ai_calls_used: number;
  plan_limits: { tournaments: number | null; ai_calls: number | null };
  whatsapp_phone?: string | null;
  digest_subscribed?: boolean;
  profile_completed_at?: string | null;
}

export interface DemographicProfile {
  birth_year?: number | null;
  country?: string | null;
  state_province?: string | null;
  city?: string | null;
  poker_experience_years?: number | null;
  main_game_type?: "mtt" | "cash" | "spin" | "mixed" | null;
  usual_buyin_range?: "micro" | "low" | "mid" | "high" | null;
  profile_completed_at?: string | null;
}

export const profile = {
  get: () => request<DemographicProfile>("/player/profile"),
  update: (data: Partial<DemographicProfile>) =>
    request<DemographicProfile>("/player/profile", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
};

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

  updatePhone: (phone: string | null) =>
    request<{ ok: boolean; phone: string | null }>("/profile/phone", {
      method: "PATCH",
      body: JSON.stringify({ phone }),
    }),
};

// ── Tournaments ───────────────────────────────────────────────────────────────

export interface Tournament {
  id: number;
  tournament_id: string;
  site: string;
  tournament_name?: string | null;
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
  coach_reviewed?: boolean;
}

export interface TournamentsResponse {
  tournaments: Tournament[];
}

export interface TournamentComparison {
  tournament_id: string;
  tournament_name: string | null;
  played_at: string | null;
  site: string;
  standard_pct: number | null;
  avg_score: number | null;
  clear_pct: number | null;
  hands_count: number | null;
  decisions_count: number | null;
  profit: number | null;
  buy_in: number | null;
  place: number | null;
  phases: { phase: string; range: string; n: number; mistake_rate: number; avg_score: number }[];
  top_leaks: [string, number, number][];
}

export interface PhaseData {
  phase: string;
  range: string;
  n: number;
  mistake_rate: number;
  avg_score: number;
}

export interface TextureData {
  texture: string;
  label: string;
  n: number;
  mistake_rate: number;
  avg_score: number;
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
  has_annotation?: boolean;
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

export type CoachOverrideLabel = "standard" | "marginal" | "small_mistake" | "clear_mistake" | null;

export interface CoachAnnotation {
  id: number;
  coach_id: number;
  student_id: number;
  decision_id: number;
  comment: string;
  mode: "complement" | "replace";
  coach_action: string | null;
  coach_override_label: CoachOverrideLabel;
  created_at: string;
  street?: string;
  action_taken?: string;
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
  coach_annotations?: Record<string, CoachAnnotation>;
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

  narrative: (tournamentId: string) =>
    request<{ narrative: string; quality_level: "solid" | "regular" | "poor" }>(
      `/history/tournament/${tournamentId}/narrative`
    ),

  compare: (ids: string[]) =>
    request<{
      items: TournamentComparison[];
      narrative: string;
    }>(`/history/tournaments/compare?ids=${ids.join(",")}`),

  downloadReport: async (tournamentId: string): Promise<{ format: "pdf" | "html" }> => {
    const t = sessionStorage.getItem("ll_token");
    const res = await fetch(`${BASE}/history/tournament/${tournamentId}/report.pdf`, {
      headers: t ? { Authorization: `Bearer ${t}` } : {},
    });
    if (!res.ok) {
      const msg = await res.text().catch(() => `HTTP ${res.status}`);
      throw new Error(msg);
    }
    const isPdf = (res.headers.get("content-type") ?? "").includes("application/pdf");
    const ext = isPdf ? "pdf" : "html";
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leaklab-report-${tournamentId}.${ext}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    return { format: isPdf ? "pdf" : "html" };
  },

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

  phaseAnalysis: (tournamentId: string) =>
    request<{ phase_analysis: PhaseData[] }>(
      `/history/tournament/${tournamentId}/phase_analysis`
    ),

  textureAnalysis: (tournamentId: string) =>
    request<{ texture_analysis: TextureData[] }>(
      `/history/tournament/${tournamentId}/texture_analysis`
    ),
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

export interface LeakRoiData {
  spot: string;
  n: number;
  avg_score: number;
  total_score: number;
  avg_buy_in: number;
  ev_loss_monthly: number;
  priority_score: number;
  priority_rank: number;
  drill_count: number;
  drill_accuracy: number | null;
  trend: "improving" | "regressing" | "stagnant" | "new";
}

export interface PressureProfile {
  baseline_score: number | null;
  by_pressure: Record<string, { n: number; avg_score: number; standard_rate: number }>;
  collapse_delta: number | null;
  has_collapse: boolean;
}

export interface ConfidenceDrift {
  drift_detected: boolean;
  affected_sessions: number;
  severity: "mild" | "moderate" | "severe" | null;
  baseline_score: number;
  sessions: { tournament_id: number; name: string; played_at: string; avg_score: number; delta_pct: number }[];
}

export interface DrillSpot {
  id: number;
  hand_id: string;
  street: string;
  hero_cards: string | null;
  board: string | null;
  action_taken: string;
  best_action: string;
  label: string;
  score: number;
  m_ratio: number | null;
  icm_pressure: string | null;
  stack_bb: number | null;
  position: string | null;
  num_players: number | null;
  is_3bet: boolean;
  level_bb: number | null;
  tournament_name: string | null;
  played_at: string | null;
  buy_in: number | null;
  note: string | null;
  draw_profile: string | null;
  pot_size: number | null;
  facing_bet: number | null;
  // Sprint R — SRS
  next_drill_at: string | null;
  srs_interval_days: number | null;
  days_overdue: number | null;
}

export interface DrillStats {
  total: number;
  correct: number;
  incorrect: number;
  accuracy: number | null;
  avg_delta: number | null;
}

export interface DrillSubmitResult {
  is_correct: boolean;
  best_action: string;
  new_action: string;
  new_score: number;
  original_score: number;
  delta: number;
  next_drill_at: string;
  srs_interval_days: number;
}

export interface DrillAnalysisResult {
  analysis: string;
  cached: boolean;
}

export interface PlayerDna {
  aggression_index: number;
  fold_frequency: number;
  three_bet_pct: number;
  positional_awareness: number;
  discipline: number;
  icm_awareness: number | null;
  archetype: string;
}

export interface PlayerDnaResponse {
  dna: PlayerDna | null;
  sample_size: number;
}

export const drill = {
  spots: (params?: { limit?: number; street?: string; spot?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit)  q.set("limit",  String(params.limit));
    if (params?.street) q.set("street", params.street);
    if (params?.spot)   q.set("spot",   params.spot);
    const qs = q.toString();
    return request<{ spots: DrillSpot[]; stats: DrillStats }>(`/player/spots/drill${qs ? "?" + qs : ""}`);
  },

  submit: (decision_id: number, new_action: string) =>
    request<DrillSubmitResult>("/player/spots/drill/submit", {
      method: "POST",
      body: JSON.stringify({ decision_id, new_action }),
    }),

  analysis: (decision_id: number) =>
    request<DrillAnalysisResult>(`/player/spots/drill/${decision_id}/analysis`),
};

export const sparring = {
  hand: (hand_id?: string, tournament_id?: number, exclude_hand_ids?: string[]) => {
    const q = new URLSearchParams();
    if (hand_id)       q.set("hand_id", hand_id);
    if (tournament_id) q.set("tournament_id", String(tournament_id));
    if (exclude_hand_ids?.length) q.set("exclude_hand_ids", exclude_hand_ids.join(","));
    const qs = q.toString();
    return request<SparringHand>(`/player/sparring/hand${qs ? "?" + qs : ""}`);
  },
};

export const metrics = {
  evolution: (days = 90) =>
    request<EvolutionResponse>(`/history/evolution?days=${days}`),

  breakdown: (days = 90) =>
    request<BreakdownResponse>(`/history/breakdown?days=${days}`),

  playerStats: (days = 90) =>
    request<PlayerStatsResponse>(`/metrics/player-stats?days=${days}`),

  level: () =>
    request<PlayerLevel>(`/metrics/level`),

  leakRoi: (days = 90) =>
    request<{ leaks: LeakRoiData[] }>(`/player/leak-roi?days=${days}`),

  drillStats: (days = 30) =>
    request<DrillStats>(`/player/drill-stats?days=${days}`),

  pressureProfile: (days = 90) =>
    request<PressureProfile>(`/player/pressure-profile?days=${days}`),

  confidenceDrift: (days = 30) =>
    request<ConfidenceDrift>(`/player/confidence-drift?days=${days}`),

  dna: (days = 90) =>
    request<PlayerDnaResponse>(`/player/dna?days=${days}`),

  leakGraph: (days = 90, lang = "pt-BR") =>
    request<LeakGraphResponse>(`/player/leak-graph?days=${days}&lang=${encodeURIComponent(lang)}`),

  career: (lang = "pt-BR") =>
    request<CareerProjection>(`/player/career?lang=${encodeURIComponent(lang)}`),

  cognitiveFailures: (lang = "pt-BR", days = 90) =>
    request<CognitiveFailureData>(`/player/cognitive-failures?lang=${encodeURIComponent(lang)}&days=${days}`),

  strategicTwin: (lang = "pt-BR", days = 180) =>
    request<StrategicTwinProfile>(`/player/strategic-twin?lang=${encodeURIComponent(lang)}&days=${days}`),

  dailyFocus: () =>
    request<DailyFocusData>(`/player/daily-focus`),

  completeDailyFocus: () =>
    request<{ ok: boolean }>(`/player/daily-focus/complete`, { method: "POST" }),

  xpStatus: () =>
    request<XpStatus>(`/player/xp`),

  addXp: (event_type: string, amount?: number) =>
    request<XpStatus>(`/player/xp`, {
      method: "POST",
      body: JSON.stringify({ event_type, amount }),
    }),

  achievements: () =>
    request<{ achievements: Achievement[] }>(`/player/achievements`),

  createSessionGoal: (goal: { goal_leak_spot?: string; target_standard_pct?: number; notes?: string }) =>
    request<SessionGoal>(`/player/session-goals`, {
      method: "POST",
      body: JSON.stringify(goal),
    }),

  pendingSessionGoal: () =>
    request<SessionGoal | Record<string, never>>(`/player/session-goals/pending`),

  linkSessionGoal: (goalId: number, tournamentId: number) =>
    request<{ ok: boolean }>(`/player/session-goals/${goalId}/link`, {
      method: "POST",
      body: JSON.stringify({ tournament_id: tournamentId }),
    }),

  sessionReview: (tournamentId: number) =>
    request<SessionReviewResponse>(`/player/session-review/${tournamentId}`),
};

// ── Leak Causal Graph (Sprint S) ─────────────────────────────────────────────

export interface LeakGraphNode {
  id: string;
  label: string;
  n: number;
  avg_score: number;
  severity: "critical" | "moderate" | "minor";
  degree: number;
}

export interface LeakGraphEdge {
  source: string;
  target: string;
  co_occurrences: number;
  correlation: number;
}

export interface LeakGraphResponse {
  nodes: LeakGraphNode[];
  edges: LeakGraphEdge[];
  narrative: string;
}

// ── Career Projection (Sprint AP) ────────────────────────────────────────────

export interface CareerMilestone {
  level_name: string;
  level_slug: string;
  threshold: number;
  reachable: boolean;
  tournaments_needed?: number;
  months_needed?: number;
  estimated_date?: string;
}

export interface CareerProjection {
  insufficient_data: boolean;
  tournament_count: number;
  current_level?: string;
  current_level_slug?: string;
  current_avg?: number;
  slope_per_tournament?: number;
  tourns_per_month?: number;
  milestones?: CareerMilestone[];
  next_milestone?: CareerMilestone | null;
  series_history?: number[];
  series_projection?: number[];
  blocking_leaks?: { spot: string; n: number; avg_score: number }[];
  narrative?: string;
}

// ── Cognitive Failure Mapper (Sprint AQ) ─────────────────────────────────────

export interface CognitivePattern {
  type: "revenge_aggression" | "fear_folding" | "sunk_cost" | "entitlement_tilt" | "compensation_call";
  count: number;
  frequency: number;
  severity: "high" | "medium" | "low";
}

export interface CognitiveFailureData {
  insufficient_data: boolean;
  patterns: CognitivePattern[];
  total_decisions: number;
  narrative?: string;
}

// ── Strategic Twin (Sprint AR) ───────────────────────────────────────────────

export interface TwinSpot {
  street: "preflop" | "flop" | "turn" | "river";
  best_action: "jam" | "fold" | "call" | "raise" | "bet" | "check";
  icm_pressure: "low" | "medium" | "high" | "critical";
  total: number;
  mistakes: number;
  error_rate: number;
  delta_from_avg: number;
}

export interface StrategicTwinProfile {
  insufficient_data: boolean;
  total_decisions: number;
  player_avg_error_rate?: number;
  high_volume_spots?: TwinSpot[];
  costly_spots?: TwinSpot[];
  narrative?: string;
}

// ── Sparring Mode (Sprint AS) ─────────────────────────────────────────────────

export interface SparringStep {
  step_index: number;
  decision_id: number;
  street: "preflop" | "flop" | "turn" | "river";
  hero_cards: string | null;
  board: string | null;
  action_taken: string;
  best_action: string;
  label: string;
  score: number;
  m_ratio: number | null;
  icm_pressure: string | null;
  stack_bb: number | null;
  position: string | null;
  num_players: number | null;
  pot_size: number | null;
  facing_bet: number | null;
  is_3bet: boolean;
}

export interface SparringHand {
  insufficient_data: boolean;
  hand_id?: string;
  tournament_id?: number;
  tournament_name?: string | null;
  primary_decision_id?: number;
  steps?: SparringStep[];
  total_steps?: number;
}

// ── Daily Focus + XP (Sprint Q) ───────────────────────────────────────────────

export interface DailyFocusAction {
  type: "leak" | "drill" | "tournament" | "none";
  label: string;
  description: string;
  link: string;
}

export interface DailyFocusData {
  primary: DailyFocusAction;
  secondary: DailyFocusAction[];
  valid_until: string;
  completed: boolean;
  streak: number;
}

export interface XpStatus {
  xp_total: number;
  streak: number;
  last_activity: string | null;
}

export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlocked_at: string;
}

// ── Player Level / Gamification (BACK-009) ────────────────────────────────────

export interface PlayerLevel {
  level: string | null;
  icon: string;
  standard_pct: number;
  level_min: number;
  level_max: number;
  next_level: string | null;
  next_level_icon: string | null;
  next_pct: number | null;
  progress: number;
  tournament_count: number;
  top_blocking_leaks: { spot: string; n: number; avg_score: number }[];
}

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

export interface BiggestResult {
  name: string;
  prize: string;
  year: number;
}

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
  avg_rating: number | null;
  review_count: number;
  // Sprint 7 — campos estendidos
  photo_url: string | null;
  experience_years: number | null;
  stakes: string | null;
  coaching_style: string | null;
  languages: string[];
  biggest_results: BiggestResult[];
  price_per_session: number | null;
  price_monthly: number | null;
  trial_available: boolean;
  availability: string | null;
  social_youtube: string | null;
  social_twitch: string | null;
  social_twitter: string | null;
}

export interface CoachReview {
  id: number;
  coach_id: number;
  student_id: number;
  username: string;
  rating: number;
  review_text: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewStats {
  avg_rating: number | null;
  total: number;
  r5: number; r4: number; r3: number; r2: number; r1: number;
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

export interface MultiStudentDecision extends StudentWorstDecision {
  student_id: number;
  username: string;
}

export interface CommonLeakStudent {
  id: number;
  username: string;
  n: number;
  avg_score: number;
}

export interface CommonLeak {
  spot: string;
  num_students: number;
  total_n: number;
  avg_score: number;
  students: CommonLeakStudent[];
}

// Sprint 6 — BACK-002
export interface CoachBaseline {
  id: number;
  coach_id: number;
  student_id: number;
  baseline_date: string;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface ActivityEvent {
  type: "tournament";
  ts: string;
  tournament_id: string;
  site: string;
  avg_score: number;
  standard_pct: number;
  hands_count: number;
  profit: number | null;
  buy_in: number | null;
  milestone?: "improvement" | "regression" | "high_standard";
}

export interface LeakSpot {
  spot: string;
  n: number;
}

export interface PeriodMetrics {
  n: number;
  avg_score: number | null;
  standard_pct: number | null;
  total_profit: number | null;
}

export interface ProgressReport {
  baseline: CoachBaseline;
  before: PeriodMetrics;
  after: PeriodMetrics;
  leaks_before: LeakSpot[];
  leaks_after: LeakSpot[];
  fixed_leaks: LeakSpot[];
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

  studentLevel: (studentId: number) =>
    request<PlayerLevel>(`/coach/student/${studentId}/level`),

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

  getAnnotations: (studentId: number) =>
    request<{ annotations: CoachAnnotation[] }>(`/coach/student/${studentId}/hand-annotations`),

  upsertAnnotation: (studentId: number, data: {
    decision_id: number;
    comment: string;
    mode: "complement" | "replace";
    coach_action?: string;
    coach_override_label?: CoachOverrideLabel;
  }) =>
    request<CoachAnnotation>(`/coach/student/${studentId}/hand-annotations`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteAnnotation: (studentId: number, decisionId: number) =>
    request<{ ok: boolean }>(`/coach/student/${studentId}/hand-annotations/${decisionId}`, {
      method: "DELETE",
    }),

  impact: (days = 30) =>
    request<CoachImpactResponse>(`/coach/impact?days=${days}`),

  allWorstDecisions: (params?: { n?: number; student_id?: number; street?: string; label?: string }) => {
    const q = new URLSearchParams();
    if (params?.n)          q.set("n", String(params.n));
    if (params?.student_id) q.set("student_id", String(params.student_id));
    if (params?.street)     q.set("street", params.street);
    if (params?.label)      q.set("label", params.label);
    return request<{ decisions: MultiStudentDecision[] }>(`/coach/all-worst-decisions?${q}`);
  },

  commonLeaks: (days = 30) =>
    request<{ leaks: CommonLeak[] }>(`/coach/common-leaks?days=${days}`),

  // Sprint 6 — BACK-002
  getBaseline: (studentId: number) =>
    request<CoachBaseline | Record<string, never>>(`/coach/student/${studentId}/baseline`),

  setBaseline: (studentId: number, baseline_date: string, note?: string) =>
    request<CoachBaseline>(`/coach/student/${studentId}/baseline`, {
      method: "POST",
      body: JSON.stringify({ baseline_date, note }),
    }),

  deleteBaseline: (studentId: number) =>
    request<{ ok: boolean }>(`/coach/student/${studentId}/baseline`, {
      method: "DELETE",
    }),

  activityFeed: (studentId: number, limit = 30) =>
    request<ActivityEvent[]>(`/coach/student/${studentId}/activity-feed?limit=${limit}`),

  progressReport: (studentId: number) =>
    request<ProgressReport>(`/coach/student/${studentId}/progress-report`),

  // Sprint 7 — BACK-006: reviews
  getReviews: (limit = 20) =>
    request<{ reviews: CoachReview[]; stats: ReviewStats }>(`/coach/reviews?limit=${limit}`),

  getMyReview: (coachId?: number) =>
    request<CoachReview | null>(`/coach/my-review${coachId ? `?coach_id=${coachId}` : ""}`),

  submitReview: (data: { rating: number; review_text?: string; coach_id?: number }) =>
    request<CoachReview>("/coach/review", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteMyReview: (coachId?: number) =>
    request<{ ok: boolean }>(`/coach/review${coachId ? `?coach_id=${coachId}` : ""}`, {
      method: "DELETE",
    }),

  // Sprint V — FEAT-09: Plan Templates
  getTemplates: () =>
    request<{ templates: CoachTemplate[] }>("/coach/templates"),

  createTemplate: (data: { name: string; target_archetype?: string; cards_json: object[] }) =>
    request<CoachTemplate>("/coach/templates", {
      method: "POST",
      body: JSON.stringify({ ...data, cards_json: data.cards_json }),
    }),

  deleteTemplate: (templateId: number) =>
    request<{ ok: boolean }>(`/coach/templates/${templateId}`, { method: "DELETE" }),

  // Sprint V — FEAT-10: Messages (coach side)
  getMessages: (studentId: number) =>
    request<{ messages: CoachMessage[] }>(`/coach/student/${studentId}/messages`),

  sendMessage: (studentId: number, body: string, decision_id?: number) =>
    request<CoachMessage>(`/coach/student/${studentId}/messages`, {
      method: "POST",
      body: JSON.stringify({ body, decision_id }),
    }),

  inbox: () =>
    request<{ threads: InboxThread[] }>("/coach/messages/inbox"),
};

export interface InboxThread {
  student_id: number;
  student_username: string;
  last_message_at: string;
  last_message_body: string;
  last_sender_role: "coach" | "student";
  unread_count: number;
}

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

// ── Public coach directory (BACK-006 pt.2) ───────────────────────────────────

export interface PublicCoachReview {
  username: string;
  rating: number;
  review_text: string | null;
  updated_at: string;
}

export interface PublicCoach extends CoachProfile {
  students_avg_score: number | null;
  reviews?: PublicCoachReview[];
}

export interface CoachDirectoryFilters {
  specialty?: string;
  language?: string;
  trial?: boolean;
  max_price?: number;
  q?: string;
  sort?: "rating" | "students" | "price";
  limit?: number;
}

export const coaches = {
  list: (filters: CoachDirectoryFilters = {}) => {
    const q = new URLSearchParams();
    if (filters.specialty)  q.set("specialty",  filters.specialty);
    if (filters.language)   q.set("language",   filters.language);
    if (filters.trial)      q.set("trial",       "1");
    if (filters.max_price != null) q.set("max_price", String(filters.max_price));
    if (filters.q)          q.set("q",           filters.q);
    if (filters.sort)       q.set("sort",        filters.sort);
    if (filters.limit)      q.set("limit",       String(filters.limit));
    const qs = q.toString();
    return request<{ coaches: PublicCoach[] }>(`/coaches${qs ? `?${qs}` : ""}`);
  },

  get: (coachUserId: number) =>
    request<PublicCoach>(`/coaches/${coachUserId}`),

  recommended: () =>
    request<{ coaches: PublicCoach[] }>("/student/recommended-coaches"),
};

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

// ── Subscription ──────────────────────────────────────────────────────────────

export interface QuotaStatus {
  plan: string;
  tournaments_used: number;
  ai_calls_used: number;
  limits: {
    tournaments: number | null;
    ai_calls: number | null;
  };
}

export interface Invoice {
  id: number;
  plan: string;
  amount_cents: number;
  currency: string;
  status: string;
  gateway_id: string | null;
  created_at: string;
}

export const subscription = {
  status: () => request<QuotaStatus>("/subscription/status"),

  plans: () =>
    request<{ plans: Array<{ id: string; name: string; price: number; features: string[] }> }>(
      "/subscription/plans"
    ),

  upgrade: (plan: string) =>
    request<{ ok: boolean; plan: string }>("/subscription/upgrade", {
      method: "POST",
      body: JSON.stringify({ plan }),
    }),

  checkout: (plan: string) =>
    request<{ client_secret: string; subscription_id: string }>("/subscription/checkout", {
      method: "POST",
      body: JSON.stringify({ plan }),
    }),

  activate: (plan: string, payment_intent_id: string, subscription_id: string) =>
    request<{ ok: boolean; plan: string; subscription_id: string }>("/subscription/activate", {
      method: "POST",
      body: JSON.stringify({ plan, payment_intent_id, subscription_id }),
    }),

  invoices: () => request<{ invoices: Invoice[] }>("/subscription/invoices"),

  cancel: () =>
    request<{ ok: boolean; plan: string }>("/subscription/cancel", { method: "POST" }),
};

// ── Admin & Coach Finance — BACK-014 + BACK-017 ───────────────────────────────

export interface AdminStats {
  total_users: number;
  total_coaches: number;
  active_users_30d: number;
  plans: Record<string, number>;
  mrr_cents: number;
  pending_payouts_cents: number;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  plan: string;
  created_at: string;
  last_login: string | null;
  last_import: string | null;
  tournament_count: number;
  coach_username: string | null;
  suspended: boolean | number;
}

export interface CoachPayout {
  id: number;
  username: string;
  display_name: string | null;
  plan: string;
  total_students: number;
  active_students: number;
  amount_cents: number;
  status: "pending" | "paid";
  payment_id: number | null;
  paid_at: string | null;
}

export interface CoachFinanceSummary {
  period: string;
  total_students: number;
  active_students: number;
  amount_cents: number;
  status: string;
  paid_at: string | null;
  monthly_fee_waived: boolean;
}

export interface CoachFinanceStudent {
  id: number;
  username: string;
  plan: string;
  last_import: string | null;
  tournament_count: number;
  is_active: boolean;
}

export interface CoachPaymentRecord {
  id: number;
  period: string;
  active_students: number;
  amount_cents: number;
  status: "pending" | "paid";
  paid_at: string | null;
  created_at: string;
}

export const adminDashboard = {
  stats: () => request<AdminStats>("/admin/dashboard"),

  users: (params?: { limit?: number; offset?: number; plan?: string; role?: string; search?: string }) => {
    const q = new URLSearchParams();
    if (params?.limit  != null) q.set("limit",  String(params.limit));
    if (params?.offset != null) q.set("offset", String(params.offset));
    if (params?.plan)           q.set("plan",   params.plan);
    if (params?.role)           q.set("role",   params.role);
    if (params?.search)         q.set("search", params.search);
    return request<{ users: AdminUser[]; total: number }>(`/admin/users?${q}`);
  },

  updateUser: (id: number, data: { plan?: string; suspended?: boolean }) =>
    request<{ ok: boolean }>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  coachPayouts: (period?: string) =>
    request<{ payouts: CoachPayout[]; period: string; total_pending_cents: number }>(
      `/admin/finance/coaches${period ? `?period=${period}` : ""}`
    ),

  markPaid: (paymentId: number) =>
    request<{ ok: boolean }>(`/admin/finance/coaches/${paymentId}/pay`, { method: "PATCH" }),

  logs: (limit = 50) => request<{ logs: Array<{ id: number; username: string; plan: string; tournament_id: string; site: string; hands_count: number; imported_at: string }> }>(`/admin/logs?limit=${limit}`),

  coachApplications: (status = "pending") =>
    request<{ applications: CoachApplication[] }>(`/admin/coach-applications?status=${status}`),

  approveApplication: (id: number, note?: string) =>
    request<{ ok: boolean }>(`/admin/coach-applications/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ note: note ?? "" }),
    }),

  rejectApplication: (id: number, note?: string) =>
    request<{ ok: boolean }>(`/admin/coach-applications/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ note: note ?? "" }),
    }),

  demographics: () => request<{
    total_players: number;
    profiles_completed: number;
    completion_rate: number;
    top_countries: Array<{ country: string; n: number }>;
    game_types: Array<{ main_game_type: string; n: number }>;
    buyin_ranges: Array<{ usual_buyin_range: string; n: number }>;
  }>("/admin/demographics"),
};

export interface CoachApplication {
  id: number;
  user_id: number;
  username: string;
  email: string;
  instagram_handle: string | null;
  bio: string;
  specialties: string;
  experience_years: number;
  biggest_results: string;
  status: "pending" | "approved" | "rejected";
  admin_note: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export const coachApplyApi = {
  apply: (data: {
    username: string; email: string; password: string;
    instagram_handle?: string; bio: string; specialties?: string;
    experience_years?: number; biggest_results?: string;
  }) =>
    request<{ ok: boolean; message: string }>("/auth/coach-apply", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const coachFinance = {
  summary: () => request<CoachFinanceSummary>("/coach/finance/summary"),
  students: () => request<{ students: CoachFinanceStudent[] }>("/coach/finance/students"),
  history: () => request<{ payments: CoachPaymentRecord[] }>("/coach/finance/history"),
};

// ── Coach Effectiveness (Sprint T — FEAT-07) ──────────────────────────────────

export interface EffectivenessStudent {
  student_id: number;
  username: string;
  baseline_date: string;
  std_before: number;
  std_after: number;
  delta: number;
  score_before: number;
  score_after: number;
  fixed_leaks: number;
  tournaments_after: number;
}

export interface EffectivenessSummary {
  students_analyzed: number;
  median_delta: number | null;
  positive_pct: number | null;
  badge: string | null;
}

export interface CoachEffectivenessReport {
  students: EffectivenessStudent[];
  summary: EffectivenessSummary;
}

export const coachEffectiveness = {
  report: () => request<CoachEffectivenessReport>("/coach/effectiveness"),
};

// ── Coach Plan Templates — FEAT-09 ───────────────────────────────────────────

export interface CoachTemplate {
  id: number;
  name: string;
  target_archetype: string | null;
  cards_json: string;
  created_at: string;
}

// ── Coach Messages — FEAT-10 ─────────────────────────────────────────────────

export interface CoachMessage {
  id: number;
  body: string;
  sender_role: "coach" | "student";
  decision_id: number | null;
  read_at: string | null;
  created_at: string;
}

export const playerMessages = {
  list: () =>
    request<{ messages: CoachMessage[] }>("/player/coach/messages"),

  send: (body: string) =>
    request<CoachMessage>("/player/coach/messages", {
      method: "POST",
      body: JSON.stringify({ body }),
    }),

  unreadCount: () =>
    request<{ unread: number }>("/player/messages/unread"),
};

// ── Session Goals — FEAT-08 ───────────────────────────────────────────────────

export interface SessionGoal {
  id: number;
  goal_leak_spot: string | null;
  target_standard_pct: number | null;
  notes: string | null;
  llm_review?: string | null;
  created_at: string;
  linked_at?: string | null;
}

export interface SessionReviewResponse {
  review: string | null;
  goal: SessionGoal | null;
  requires_pro: boolean;
}

// ── Digest semanal — FEAT-11 ─────────────────────────────────────────────────

export const digest = {
  subscribe: () =>
    request<{ ok: boolean; digest_subscribed: boolean }>("/player/digest/subscribe", {
      method: "POST",
    }),

  unsubscribe: () =>
    request<{ ok: boolean; digest_subscribed: boolean }>("/player/digest/unsubscribe", {
      method: "POST",
    }),
};

// ── Dashboard preferences — UX-017 ───────────────────────────────────────────

export interface DashboardLayoutData {
  main: string[];
  sidebar: string[];
}

export const preferences = {
  get: () =>
    request<{ dashboard_layout: DashboardLayoutData | null }>("/player/preferences"),

  save: (dashboard_layout: DashboardLayoutData) =>
    request<{ ok: boolean }>("/player/preferences", {
      method: "PATCH",
      body: JSON.stringify({ dashboard_layout }),
    }),
};
