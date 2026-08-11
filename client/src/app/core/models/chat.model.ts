export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id?: number;
  conversation_id: string;
  role: ChatRole;
  content: string;
  created_at?: string;
  token_count?: number;
}

export interface ChatHistoryResponse {
  conversation_id: string;
  messages: Array<{
    role: ChatRole;
    message: string;
    created_at?: string;
    token_count?: number;
  }>;
}

export interface ChatStreamEvent {
  chunk: string;
  done: boolean;
  event?: "started" | string;
  token_count?: number;
  error?: string;
  error_code?: string;
  retryable?: boolean;
  retry_after_ms?: number;
}

export interface ChatContextSource {
  key: string;
  label: string;
  count: number;
  enabled: boolean;
}

export interface ChatContextStatus {
  history_enabled: boolean;
  sources: ChatContextSource[];
}

export interface ChatMonthlyUsage {
  used: number;
  limit: number | null;
  remaining: number | null;
  unlimited: boolean;
}

export interface ChatStats {
  conversation_id: string;
  message_count: number;
  user_message_count: number;
  assistant_message_count: number;
  token_count: number;
  started_at?: string | null;
  last_message_at?: string | null;
  active_seconds: number;
  conversation_count: number;
  limits: {
    max_message_length: number;
    max_messages_per_conversation: number;
    model_history_limit: number;
    history_response_limit: number;
    daily_token_budget: number;
    monthly_chat?: ChatMonthlyUsage;
  };
}
