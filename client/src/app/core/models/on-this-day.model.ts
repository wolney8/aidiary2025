export type OnThisDayEntryType = "daily" | "dream" | "thought_record";

export interface OnThisDayEntry {
  id: number;
  type: OnThisDayEntryType;
  entry_date: string;
  title: string;
  preview: string;
  tags: string[];
  image_url: string | null;
  image_source: string | null;
  attachment_count: number;
}

export interface OnThisDayFeed {
  enabled: boolean;
  date: string;
  entries: OnThisDayEntry[];
}
