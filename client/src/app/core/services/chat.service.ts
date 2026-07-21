import { HttpClient } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable, map } from "rxjs";
import { environment } from "../../../environments/environment";
import {
  ChatHistoryResponse,
  ChatMessage,
  ChatStreamEvent,
} from "../models/chat.model";
import { AuthService } from "./auth.service";

const CONVERSATION_ID_KEY = "chat_conversation_id";
const CHAT_STREAM_IDLE_TIMEOUT_MS = 45_000;
const MAX_PRE_STREAM_RETRIES = 1;

export class ChatRequestError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly retryable = false,
  ) {
    super(message);
    this.name = "ChatRequestError";
  }
}

@Injectable({ providedIn: "root" })
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = environment.apiBaseUrl;

  sendMessage(conversationId: string, message: string): Observable<string> {
    return new Observable<string>((observer) => {
      const requestId = crypto.randomUUID();
      let activeController: AbortController | null = null;
      let cancelled = false;

      void this.streamMessage(
        conversationId,
        message,
        requestId,
        observer,
        (controller) => (activeController = controller),
        () => cancelled,
      );
      return () => {
        cancelled = true;
        activeController?.abort();
      };
    });
  }

  getHistory(conversationId: string): Observable<ChatMessage[]> {
    return this.http
      .get<ChatHistoryResponse>(`${this.apiUrl}/chat/history`, {
        params: { conversation_id: conversationId },
      })
      .pipe(
        map((response) =>
          response.messages.map((message) => ({
            conversation_id: response.conversation_id,
            role: message.role,
            content: message.message,
            created_at: message.created_at,
            token_count: message.token_count,
          })),
        ),
      );
  }

  clearConversation(conversationId: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/chat/conversation`, {
      params: { conversation_id: conversationId },
    });
  }

  getOrCreateConversationId(): string {
    const existing = localStorage.getItem(CONVERSATION_ID_KEY);
    if (existing) return existing;

    const conversationId = crypto.randomUUID();
    localStorage.setItem(CONVERSATION_ID_KEY, conversationId);
    return conversationId;
  }

  resetConversationId(): string {
    localStorage.removeItem(CONVERSATION_ID_KEY);
    return this.getOrCreateConversationId();
  }

  private async streamMessage(
    conversationId: string,
    message: string,
    requestId: string,
    observer: {
      next(value: string): void;
      error(error: unknown): void;
      complete(): void;
      closed: boolean;
    },
    setActiveController: (controller: AbortController) => void,
    isCancelled: () => boolean,
  ): Promise<void> {
    let emittedChunk = false;

    for (let attempt = 0; attempt <= MAX_PRE_STREAM_RETRIES; attempt += 1) {
      const controller = new AbortController();
      setActiveController(controller);

      try {
        const token = this.authService.getToken();
        const response = await fetch(`${this.apiUrl}/chat/message`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            conversation_id: conversationId,
            message,
            request_id: requestId,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          const errorPayload = (await response.json().catch(() => null)) as {
            error?: string;
          } | null;
          throw new ChatRequestError(
            errorPayload?.error || "Chat request failed.",
            response.status === 429 ? "rate_limited" : "server_error",
            response.status >= 500,
          );
        }
        if (!response.body) {
          throw new ChatRequestError(
            "Chat response stream is unavailable.",
            "stream_unavailable",
            true,
          );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!observer.closed && !isCancelled()) {
          const { value, done } = await this.readWithTimeout(reader, controller);
          buffer += decoder.decode(value, { stream: !done });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() ?? "";

          for (const block of blocks) {
            const event = this.parseEvent(block);
            if (!event) continue;
            if (event.error) {
              throw new ChatRequestError(
                event.error,
                event.error_code || "stream_failed",
                event.error_code === "provider_unavailable",
              );
            }
            if (event.chunk) {
              emittedChunk = true;
              observer.next(event.chunk);
            }
            if (event.done) {
              observer.complete();
              return;
            }
          }

          if (done) break;
        }

        if (!observer.closed && !isCancelled()) {
          throw new ChatRequestError(
            "The chat response ended unexpectedly. Please try again.",
            "stream_incomplete",
            true,
          );
        }
        return;
      } catch (error) {
        if (isCancelled() || observer.closed) return;

        const chatError = this.normaliseError(error, controller.signal.aborted);
        const canRetry = chatError.retryable && !emittedChunk && attempt < MAX_PRE_STREAM_RETRIES;
        if (canRetry) continue;

        observer.error(chatError);
        return;
      }
    }
  }

  private async readWithTimeout(
    reader: ReadableStreamDefaultReader<Uint8Array>,
    controller: AbortController,
  ): Promise<ReadableStreamReadResult<Uint8Array>> {
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([
        reader.read(),
        new Promise<never>((_, reject) => {
          timeoutId = setTimeout(() => {
            controller.abort();
            reject(
              new ChatRequestError(
                "The chat response timed out. Please try again.",
                "timeout",
                true,
              ),
            );
          }, CHAT_STREAM_IDLE_TIMEOUT_MS);
        }),
      ]);
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId);
    }
  }

  private normaliseError(error: unknown, wasAborted: boolean): ChatRequestError {
    if (error instanceof ChatRequestError) return error;
    if (wasAborted) {
      return new ChatRequestError(
        "The chat response timed out. Please try again.",
        "timeout",
        true,
      );
    }
    if (error instanceof TypeError) {
      return new ChatRequestError(
        "Chat is temporarily unavailable. Check your connection and try again.",
        "network",
        true,
      );
    }
    return new ChatRequestError(
      error instanceof Error ? error.message : "Chat request failed.",
      "unknown",
    );
  }

  private parseEvent(block: string): ChatStreamEvent | null {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) return null;

    try {
      return JSON.parse(data) as ChatStreamEvent;
    } catch {
      throw new Error("Chat response could not be read.");
    }
  }
}
