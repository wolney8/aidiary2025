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