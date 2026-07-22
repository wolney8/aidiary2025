export type ReflectionSummaryPeriodType = "weekly" | "monthly";

export interface ReflectionSummarySourceRef {
  type: "daily" | "dream" | "thought_record";
  id: number;
  date: string;
  theme: string;
}

export interface ReflectionSummary {
  id: number;
  period_type: ReflectionSummaryPeriodType;
  period_start: string;
  period_end: string;
  title: string;
  summary_text: string;
  themes: string[];
  source_refs: ReflectionSummarySourceRef[];
  model: string;
  created_at: string;
  updated_at: string;
}
