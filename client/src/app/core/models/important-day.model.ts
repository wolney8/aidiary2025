export type ImportantDayCategory =
  | "birthday"
  | "anniversary"
  | "milestone"
  | "other";

export type ImportantDayRecurrence = "once" | "yearly";
export type ImportantDayIcon =
  | "cake"
  | "favorite"
  | "flag"
  | "event"
  | "celebration"
  | "star"
  | "sentiment_neutral"
  | "sentiment_dissatisfied"
  | "mood_bad";
export type ImportantDayAccentColor =
  | "amber"
  | "rose"
  | "blue"
  | "violet"
  | "emerald"
  | "slate";

export interface ImportantDay {
  id: number;
  label: string;
  starts_on: string;
  month: number;
  day: number;
  original_year?: number | null;
  category: ImportantDayCategory;
  recurrence: ImportantDayRecurrence;
  icon_name: ImportantDayIcon;
  accent_color: ImportantDayAccentColor;
  note?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ImportantDayPayload {
  label: string;
  starts_on: string;
  original_year?: number | null;
  category: ImportantDayCategory;
  recurrence: ImportantDayRecurrence;
  icon_name: ImportantDayIcon;
  accent_color: ImportantDayAccentColor;
  note?: string;
}
