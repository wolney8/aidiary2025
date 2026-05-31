// Entry models mapping to database schema exactly
export interface DailyEntry {
  id?: number;
  user_id?: number;
  entry_date: string;
  entry_number?: number;
  title?: string;
  user_message?: string;
  ai_response?: string;
  daily_people_names?: string;
  daily_places?: string;
  tags?: string;
  mood?: string;
  ai_style?: string;
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
  dream_places?: string; // Comma-separated
  tags?: string; // Comma-separated
  mood?: string; // New field for mood emoji
  ai_style?: string; // New field for AI response style
}

// Enhanced analysis interfaces
export interface AnalysisRequest {
  mode: "daily" | "dream";
  text: string;
  reference_date?: string;
  ai_style?: string;
  existing_content?: Partial<DailyEntry | DreamEntry>; // For extracting people/places
}

export interface DailyAnalysisResponse {
  ai_response: string;
  tags: string;
  daily_people_names: string;
  daily_places: string;
}

export interface DreamAnalysisResponse {
  summary: string;
  interpretation: string;
  image_prompt: string;
  tags: string;
  dream_people_names: string;
  dream_places: string;
}

// New interfaces for enhanced functionality
export interface MoodOption {
  emoji: string;
  label: string;
  value: string;
}

export interface AIStyleOption {
  label: string;
  value: string;
  description: string;
}

// Dream-specific field options
export interface DreamFieldOptions {
  emotions: string[];
  periods: string[];
  commonLocations?: string[]; // Optional since we removed the dropdown
}

// Entry display interfaces
export interface ParsedEntry {
  type: "daily" | "dream";
  entry: DailyEntry | DreamEntry;
  parsedTags: string[];
  parsedPeople: string[];
  formattedContent: string;
  formattedAIResponse?: string;
}
