// Entry models mapping to database schema
export interface DailyEntry {
  id?: number;
  user_id?: number;
  entry_date: string; // ISO date
  entry_number?: number;
  title?: string;
  user_message: string;
  ai_response?: string;
  daily_people_names?: string; // Comma-separated
  tags?: string; // Comma-separated
}

export interface DreamEntry {
  id?: number;
  user_id?: number;
  entry_date: string;
  entry_number?: number;
  title?: string;
  cast?: string;
  location?: string;
  period?: string;
  emotion?: string;
  plot?: string;
  symbols_and_imagery?: string;
  insight?: string;
  action?: string;
  other?: string;
  summary?: string;
  interpretation?: string;
  image_prompt?: string;
  image_url?: string;
  dream_people_names?: string; // Comma-separated
  tags?: string; // Comma-separated
}

export interface AnalysisRequest {
  mode: 'daily' | 'dream';
  text: string;
}

export interface DailyAnalysisResponse {
  ai_response: string;
  tags: string;
  daily_people_names: string;
}

export interface DreamAnalysisResponse {
  summary: string;
  interpretation: string;
  image_prompt: string;
  tags: string;
  dream_people_names: string;
}