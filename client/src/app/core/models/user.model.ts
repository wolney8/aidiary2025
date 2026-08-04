// User model mapping to database schema
export interface User {
  id: number;
  username: string;
  password?: string; // Not returned from API
  first_name?: string;
  last_name?: string;
  age?: number;
  sex?: string;
  goals?: string;
  display_name?: string;
  profile_picture_url?: string | null;
  pronouns?: string;
  gender?: string;
  custom_guidance?: string;
  timezone?: string;
  holiday_country_code?: string;
  show_public_holidays?: boolean;
  show_on_this_day?: boolean;
  ai_tone?: string;
  ai_verbosity?: string;
  ai_focus?: string;
  ai_model?: string;
  allow_ai_history?: boolean;
  allow_ai_attachment_context?: boolean;
  writing_reminders_enabled?: boolean;
  writing_reminder_days?: string;
  writing_reminder_time?: string;
  writing_reminder_silence_days?: number;
  writing_reminder_entry_types?: string;
  writing_rhythm_progress_enabled?: boolean;
  writing_rhythm_weekly_goal?: number;
  chat_enabled?: boolean;
  dailydiary_api_key?: string;
  dreamdiary_api_key?: string;
  chatgpt_daily_diary_coachname?: string;
  chatgpt_dream_diary_coachname?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}
