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
