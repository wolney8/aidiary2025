export type CbtWorksheetStatus = "draft" | "completed";
export type CbtLinkedEntryType = "daily" | "dream";

export interface CbtFeelingRating {
  label: string;
  intensity: number;
}

export interface CbtWorksheet {
  id: number;
  worksheet_type: "thought_record";
  title: string;
  status: CbtWorksheetStatus;
  current_step: number;
  record_date: string;
  linked_entry_type: CbtLinkedEntryType | null;
  linked_entry_id: number | null;
  situation: string;
  feelings_before: CbtFeelingRating[];
  unhelpful_thoughts: string;
  evidence_for: string;
  evidence_against: string;
  balanced_thought: string;
  feelings_after: CbtFeelingRating[];
  next_step: string;
  ai_response: string;
  ai_responded_at: string | null;
  ai_response_outdated: boolean;
  before_peak_intensity: number | null;
  after_peak_intensity: number | null;
  intensity_change: number | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export type CbtWorksheetPayload = Partial<
  Pick<
    CbtWorksheet,
    | "title"
    | "current_step"
    | "record_date"
    | "linked_entry_type"
    | "linked_entry_id"
    | "situation"
    | "feelings_before"
    | "unhelpful_thoughts"
    | "evidence_for"
    | "evidence_against"
    | "balanced_thought"
    | "feelings_after"
    | "next_step"
  >
>;
