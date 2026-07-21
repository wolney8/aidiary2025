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

@Injectable({ providedIn: "root" })
export class ChatService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = environment.apiBaseUrl;

  sendMessage(conversationId: string, message: string): Observable<string> {
    return new Observable<string>((observer) => {
      const controller = new AbortController();

      void this.streamMessage(conversationId, message, controller, observer);
      return () => controller.abort();
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
    controller: AbortController,
    observer: {
      next(value: string): void;
      error(error: unknown): void;
      complete(): void;
      closed: boolean;
    },
  ): Promise<void> {
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
        }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errorPayload = (await response.json().catch(() => null)) as {
          error?: string;
        } | null;
        throw new Error(errorPayload?.error || "Chat request failed.");
      }
      if (!response.body) throw new Error("Chat response stream is unavailable.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (!observer.closed) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const event = this.parseEvent(block);
          if (!event) continue;
          if (event.error) throw new Error(event.error);
          if (event.chunk) observer.next(event.chunk);
          if (event.done) {
            observer.complete();
            return;
          }
        }

        if (done) break;
      }

      if (!observer.closed) observer.complete();
    } catch (error) {
      if (controller.signal.aborted || observer.closed) return;
      observer.error(error instanceof Error ? error : new Error("Chat request failed."));
    }
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
