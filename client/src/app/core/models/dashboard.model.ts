export type DashboardRange = "1w" | "1m" | "3m" | "all";

export interface DashboardStreak {
  current_days: number;
  best_days: number;
  weekly_goal: number;
  week_count: number;
  month_count: number;
  weekly_progress: number;
  included_entry_types: string[];
}

export interface DashboardSeriesPoint {
  date: string;
  daily_words: number;
  dream_words: number;
  thought_records: number;
  mood_score: number | null;
  sentiment_score: number | null;
}

export interface DashboardSeasonOption {
  value: string;
  label: string;
}

export type DashboardThemeKind =
  | "tag"
  | "person"
  | "place"
  | "dream_symbol"
  | "pos_noun"
  | "pos_verb";

export interface DashboardTheme {
  label: string;
  count: number;
  kind: DashboardThemeKind;
}

export interface DashboardCbtPattern {
  label: string;
  count: number;
}

export interface DashboardCbtReflection {
  id: number;
  title: string;
  date: string | null;
  situation: string;
  balanced_thought: string;
}

export interface DashboardCbtSummary {
  total_records: number;
  common_patterns: DashboardCbtPattern[];
  average_before: number | null;
  average_after: number | null;
  average_change: number | null;
  recent_reflections: DashboardCbtReflection[];
}

export type DashboardActivityType =
  | "daily"
  | "dream"
  | "thought_record"
  | "important_day";

export interface DashboardRecentActivity {
  type: DashboardActivityType;
  id: number;
  title: string;
  date: string | null;
  summary: string;
  route: string;
}

export interface DashboardDreamLatest {
  id: number;
  title: string;
  date: string | null;
  summary: string;
  image_url: string | null;
  route: string;
  symbols?: string[];
  people?: string[];
  places?: string[];
}

export interface DashboardDreamInsights {
  total_dreams: number;
  top_symbols: DashboardTheme[];
  top_people: DashboardTheme[];
  top_places: DashboardTheme[];
  recent: DashboardDreamLatest[];
  recent_repeating_patterns: DashboardTheme[];
  latest: DashboardDreamLatest | null;
}

export interface DashboardMemoryEchoItem {
  type: "daily" | "dream";
  id: number;
  title: string;
  date: string | null;
  summary: string;
  route: string;
}

export interface DashboardMemoryEcho {
  label: string;
  count: number;
  items: DashboardMemoryEchoItem[];
}

export interface DashboardThemeDriftItem {
  label: string;
  kind: DashboardThemeKind;
  current_count: number;
  previous_count: number;
  change: number;
}

export interface DashboardMoodAnchor {
  label: string;
  kind: DashboardThemeKind;
  average_mood: number;
  count: number;
}

export interface DashboardImportantDayCue {
  id: number;
  label: string;
  date: string | null;
  category: string;
  note: string;
  icon_name: string;
  accent_color: string;
  days_until: number | null;
  route: string;
}

export interface DashboardFocusSections {
  memory_echo: DashboardMemoryEcho;
  theme_drift: DashboardThemeDriftItem[];
  mood_anchors: DashboardMoodAnchor[];
  important_day_cues: DashboardImportantDayCue[];
}

export interface DashboardQuickAction {
  type: DashboardActivityType;
  label: string;
  icon: string;
  route: string;
}

export interface DashboardOverview {
  range: DashboardRange;
  theme_filter: { label: string; kind: DashboardThemeKind } | null;
  generated_at: string;
  available_seasons: DashboardSeasonOption[];
  streak: DashboardStreak;
  series: DashboardSeriesPoint[];
  themes: DashboardTheme[];
  cbt: DashboardCbtSummary;
  recent_activity: DashboardRecentActivity[];
  recent_activity_by_type: Record<DashboardActivityType, DashboardRecentActivity[]>;
  dream_insights: DashboardDreamInsights;
  focus_sections: DashboardFocusSections;
  quick_actions: DashboardQuickAction[];
}
