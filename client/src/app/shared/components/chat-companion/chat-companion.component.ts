import { A11yModule } from "@angular/cdk/a11y";
import { CommonModule } from "@angular/common";
import {
  Component,
  DestroyRef,
  ElementRef,
  ViewChild,
  computed,
  inject,
  signal,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatTooltipModule } from "@angular/material/tooltip";
import { finalize } from "rxjs";
import { ChatMessage } from "../../../core/models/chat.model";
import { AppDialogService } from "../../../core/services/app-dialog.service";
import { AuthService } from "../../../core/services/auth.service";
import { ChatService } from "../../../core/services/chat.service";

@Component({
  selector: "app-chat-companion",
  standalone: true,
  imports: [
    A11yModule,
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
  ],
  template: `
    <section
      *ngIf="isOpen()"
      class="chat-panel"
      data-testid="chat-panel"
      role="dialog"
      aria-modal="false"
      [attr.aria-label]="'Chat with ' + coachName()"
      cdkTrapFocus
      [cdkTrapFocusAutoCapture]="true"
      (keydown.escape)="close()"
    >
      <header class="chat-header" data-testid="chat-header">
        <div class="chat-heading" data-testid="chat-heading">
          <span class="coach-icon" aria-hidden="true">
            <mat-icon>auto_awesome</mat-icon>
          </span>
          <div>
            <h2>{{ coachName() }}</h2>
            <p>Diary companion</p>
          </div>
        </div>
        <div class="chat-header-actions">
          <button
            mat-icon-button
            type="button"
            matTooltip="Clear conversation"
            aria-label="Clear conversation"
            [disabled]="isStreaming() || messages().length === 0"
            (click)="clearConversation()"
            data-testid="chat-clear-button"
          >
            <mat-icon>delete_sweep</mat-icon>
          </button>
          <button
            mat-icon-button
            type="button"
            matTooltip="Close chat"
            aria-label="Close chat"
            (click)="close()"
            data-testid="chat-close-button"
          >
            <mat-icon>close</mat-icon>
          </button>
        </div>
      </header>

      <div
        #messageThread
        class="message-thread"
        data-testid="chat-message-thread"
        aria-live="polite"
        aria-relevant="additions text"
        [attr.aria-busy]="isLoading() || isStreaming()"
      >
        <div
          *ngIf="isLoading()"
          class="chat-loading-state"
          data-testid="chat-loading-state"
          role="status"
        >
          <mat-icon aria-hidden="true">history</mat-icon>
          <span>Loading your conversation…</span>
        </div>

        <div
          *ngIf="!isLoading() && messages().length === 0"
          class="chat-empty-state"
          data-testid="chat-empty-state"
        >
          <mat-icon aria-hidden="true">forum</mat-icon>
          <h3>Start a conversation</h3>
          <p>Ask about patterns, feelings, or themes across your diary.</p>
        </div>

        <article
          *ngFor="let message of messages(); trackBy: trackMessage"
          class="message-row"
          data-testid="chat-message-row"
          [class.message-row-user]="message.role === 'user'"
        >
          <div class="message-bubble" [class.user-bubble]="message.role === 'user'">
            <span class="message-role">{{ message.role === "user" ? "You" : coachName() }}</span>
            <p>{{ message.content }}</p>
            <time *ngIf="message.created_at" [attr.datetime]="message.created_at">
              {{ message.created_at | date: "shortTime" }}
            </time>
          </div>
        </article>

        <div
          *ngIf="showTypingIndicator()"
          class="chat-typing-indicator"
          data-testid="chat-typing-indicator"
          role="status"
        >
          <span class="visually-hidden">{{ coachName() }} is responding</span>
          <span class="typing-dot" aria-hidden="true"></span>
          <span class="typing-dot" aria-hidden="true"></span>
          <span class="typing-dot" aria-hidden="true"></span>
        </div>
      </div>

      <p
        *ngIf="errorMessage()"
        class="chat-error-message"
        data-testid="chat-error-message"
        role="alert"
      >
        <mat-icon aria-hidden="true">error</mat-icon>
        <span>{{ errorMessage() }}</span>
      </p>

      <form
        class="chat-composer"
        data-testid="chat-composer"
        (ngSubmit)="send()"
      >
        <label class="visually-hidden" for="chat-message-input">Message</label>
        <textarea
          #messageInput
          id="chat-message-input"
          data-testid="chat-message-input"
          name="chatMessage"
          [(ngModel)]="draft"
          rows="2"
          maxlength="2000"
          placeholder="Ask about your diary…"
          [disabled]="isStreaming()"
          (keydown)="handleComposerKeydown($event)"
        ></textarea>
        <button
          mat-fab
          type="submit"
          class="send-button"
          data-testid="chat-send-button"
          aria-label="Send message"
          [disabled]="!canSend()"
        >
          <mat-icon>send</mat-icon>
        </button>
      </form>
      <div class="chat-composer-meta" data-testid="chat-composer-meta">
        <span>Enter to send · Shift+Enter for a new line</span>
        <span>{{ draft.length }} / 2000</span>
      </div>
    </section>

    <button
      #fab
      *ngIf="!isOpen()"
      mat-fab
      type="button"
      class="chat-fab"
      data-testid="chat-open-button"
      aria-label="Open diary companion chat"
      [attr.aria-expanded]="isOpen()"
      (click)="open()"
    >
      <mat-icon>forum</mat-icon>
    </button>
  `,
  styles: [
    `
      :host {
        position: relative;
        z-index: 900;
      }

      .chat-fab {
        position: fixed;
        right: 1.5rem;
        bottom: 1.5rem;
        z-index: 900;
        background: var(--colour-primary);
        color: var(--colour-on-primary);
        box-shadow: 0 0.5rem 1.5rem var(--colour-overlay);
      }

      .chat-panel {
        position: fixed;
        right: 1.5rem;
        bottom: 1.5rem;
        z-index: 900;
        display: grid;
        grid-template-rows: auto minmax(0, 1fr) auto auto auto;
        width: min(30rem, calc(100vw - 3rem));
        height: min(35rem, calc(100vh - 6rem));
        overflow: hidden;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-elevated);
        color: var(--colour-text-primary);
        box-shadow: 0 1.25rem 3rem var(--colour-overlay);
      }

      .chat-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-sm);
        padding: 0.85rem 0.75rem 0.85rem 1rem;
        border-bottom: 1px solid var(--colour-border);
        background: var(--colour-surface-muted);
      }

      .chat-heading,
      .chat-header-actions {
        display: flex;
        align-items: center;
      }

      .chat-heading {
        min-width: 0;
        gap: 0.75rem;
      }

      .chat-header-actions {
        flex: 0 0 auto;
      }

      .coach-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2.5rem;
        height: 2.5rem;
        flex: 0 0 2.5rem;
        border-radius: var(--radius-pill);
        background: var(--colour-violet-bg);
        color: var(--colour-violet-text);
      }

      .coach-icon mat-icon {
        width: 1.25rem;
        height: 1.25rem;
        font-size: 1.25rem;
      }

      h2,
      h3,
      p {
        margin: 0;
      }

      h2 {
        overflow: hidden;
        font-size: 1rem;
        line-height: 1.25;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .chat-heading p,
      .chat-composer-meta,
      .message-bubble time {
        color: var(--colour-text-secondary);
        font-size: 0.78rem;
      }

      .message-thread {
        min-height: 0;
        overflow-y: auto;
        overscroll-behavior: contain;
        padding: 1rem;
        background: var(--colour-surface);
        scrollbar-gutter: stable;
      }

      .chat-loading-state,
      .chat-empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--colour-text-secondary);
      }

      .chat-loading-state {
        min-height: 100%;
        gap: 0.5rem;
      }

      .chat-empty-state {
        min-height: 100%;
        flex-direction: column;
        gap: 0.5rem;
        padding: 1rem;
        text-align: center;
      }

      .chat-empty-state > mat-icon {
        width: 2rem;
        height: 2rem;
        font-size: 2rem;
        color: var(--colour-primary);
      }

      .chat-empty-state h3 {
        color: var(--colour-text-primary);
        font-size: 1rem;
      }

      .chat-empty-state p {
        max-width: 18rem;
        line-height: 1.45;
      }

      .message-row {
        display: flex;
        margin-bottom: 0.75rem;
      }

      .message-row-user {
        justify-content: flex-end;
      }

      .message-bubble {
        max-width: 82%;
        padding: 0.7rem 0.85rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
        background: var(--colour-surface-muted);
        overflow-wrap: anywhere;
      }

      .message-bubble.user-bubble {
        border-color: transparent;
        border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
        background: var(--colour-primary);
        color: var(--colour-on-primary);
      }

      .message-role {
        display: block;
        margin-bottom: 0.2rem;
        font-size: 0.72rem;
        font-weight: 700;
      }

      .message-bubble p {
        line-height: 1.45;
        white-space: pre-wrap;
      }

      .message-bubble time {
        display: block;
        margin-top: 0.35rem;
      }

      .user-bubble time {
        color: inherit;
        opacity: 0.82;
      }

      .chat-typing-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        min-width: 3.25rem;
        min-height: 2.25rem;
        padding: 0 0.8rem;
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
      }

      .typing-dot {
        width: 0.42rem;
        height: 0.42rem;
        border-radius: 50%;
        background: var(--colour-text-secondary);
        animation: typing-pulse 1.1s ease-in-out infinite;
      }

      .typing-dot:nth-child(3) {
        animation-delay: 0.15s;
      }

      .typing-dot:nth-child(4) {
        animation-delay: 0.3s;
      }

      .chat-error-message {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        margin: 0.75rem 1rem 0;
        padding: 0.65rem 0.8rem;
        border-radius: var(--radius-md);
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
        font-size: 0.88rem;
        line-height: 1.35;
      }

      .chat-error-message mat-icon {
        width: 1.15rem;
        height: 1.15rem;
        flex: 0 0 1.15rem;
        font-size: 1.15rem;
      }

      .chat-composer {
        display: flex;
        align-items: flex-end;
        gap: 0.65rem;
        padding: 0.8rem 1rem 0.35rem;
        border-top: 1px solid var(--colour-border);
        background: var(--colour-surface-elevated);
      }

      textarea {
        width: 100%;
        min-height: 2.75rem;
        max-height: 7rem;
        resize: vertical;
        box-sizing: border-box;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        padding: 0.7rem 0.8rem;
        background: var(--colour-surface);
        color: var(--colour-text-primary);
        font: inherit;
        line-height: 1.35;
      }

      textarea:focus-visible,
      .chat-fab:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      textarea::placeholder {
        color: var(--colour-text-secondary);
      }

      .send-button {
        width: 2.75rem;
        height: 2.75rem;
        flex: 0 0 2.75rem;
        background: var(--colour-primary);
        color: var(--colour-on-primary);
        box-shadow: none;
      }

      .chat-composer-meta {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0 1rem 0.8rem;
        background: var(--colour-surface-elevated);
      }

      .visually-hidden {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      @keyframes typing-pulse {
        0%,
        60%,
        100% {
          opacity: 0.35;
          transform: translateY(0);
        }
        30% {
          opacity: 1;
          transform: translateY(-0.18rem);
        }
      }

      @media (max-width: 599px) {
        .chat-panel {
          right: 0.75rem;
          bottom: 0.75rem;
          left: 0.75rem;
          width: auto;
          height: min(38rem, calc(100dvh - 1.5rem));
        }

        .chat-fab {
          right: 1rem;
          bottom: 1rem;
        }

        .message-bubble {
          max-width: 88%;
        }

        .chat-composer-meta span:first-child {
          display: none;
        }

        .chat-composer-meta {
          justify-content: flex-end;
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .typing-dot {
          animation: none;
        }
      }
    `,
  ],
})
export class ChatCompanionComponent {
  @ViewChild("messageInput") private messageInput?: ElementRef<HTMLTextAreaElement>;
  @ViewChild("messageThread") private messageThread?: ElementRef<HTMLElement>;
  @ViewChild("fab") private fab?: ElementRef<HTMLButtonElement>;

  private readonly authService = inject(AuthService);
  private readonly chatService = inject(ChatService);
  private readonly appDialog = inject(AppDialogService);
  private readonly destroyRef = inject(DestroyRef);

  readonly isOpen = signal(false);
  readonly isLoading = signal(false);
  readonly isStreaming = signal(false);
  readonly showTypingIndicator = signal(false);
  readonly errorMessage = signal("");
  readonly messages = signal<ChatMessage[]>([]);
  readonly coachName = computed(() => {
    const user = this.authService.getCurrentUser();
    return (
      user?.chatgpt_daily_diary_coachname?.trim() ||
      user?.chatgpt_dream_diary_coachname?.trim() ||
      "AI Diary"
    );
  });
  draft = "";
  private conversationId = this.chatService.getOrCreateConversationId();
  private historyLoaded = false;

  open(): void {
    this.isOpen.set(true);
    if (!this.historyLoaded) this.loadHistory();
    setTimeout(() => this.messageInput?.nativeElement.focus());
  }

  close(): void {
    this.isOpen.set(false);
    setTimeout(() => this.fab?.nativeElement.focus());
  }

  canSend(): boolean {
    return !this.isStreaming() && this.draft.trim().length > 0;
  }

  handleComposerKeydown(event: KeyboardEvent): void {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    this.send();
  }

  send(): void {
    const content = this.draft.trim();
    if (!content || this.isStreaming()) return;

    const createdAt = new Date().toISOString();
    const userMessage: ChatMessage = {
      conversation_id: this.conversationId,
      role: "user",
      content,
      created_at: createdAt,
    };
    const assistantMessage: ChatMessage = {
      conversation_id: this.conversationId,
      role: "assistant",
      content: "",
      created_at: createdAt,
    };

    this.messages.update((messages) => [...messages, userMessage, assistantMessage]);
    this.draft = "";
    this.errorMessage.set("");
    this.isStreaming.set(true);
    this.showTypingIndicator.set(true);
    this.scrollToLatest();

    this.chatService
      .sendMessage(this.conversationId, content)
      .pipe(
        finalize(() => {
          this.isStreaming.set(false);
          this.showTypingIndicator.set(false);
          this.scrollToLatest();
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (chunk) => {
          this.showTypingIndicator.set(false);
          this.messages.update((messages) => {
            const updated = [...messages];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = {
              ...last,
              content: `${last.content}${chunk}`,
            };
            return updated;
          });
          this.scrollToLatest();
        },
        error: (error: Error) => {
          this.messages.update((messages) =>
            messages.at(-1)?.role === "assistant" && !messages.at(-1)?.content
              ? messages.slice(0, -1)
              : messages,
          );
          this.errorMessage.set(error.message || "The chat response could not be completed.");
        },
      });
  }

  async clearConversation(): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "Clear this conversation?",
      message: "This removes the current chat history. Your diary entries are not changed.",
      confirmText: "Clear conversation",
      cancelText: "Keep conversation",
      variant: "danger",
    });
    if (!confirmed) return;

    this.chatService
      .clearConversation(this.conversationId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.messages.set([]);
          this.conversationId = this.chatService.resetConversationId();
          this.errorMessage.set("");
          this.historyLoaded = true;
          setTimeout(() => this.messageInput?.nativeElement.focus());
        },
        error: () => {
          this.errorMessage.set("The conversation could not be cleared. Please try again.");
        },
      });
  }

  trackMessage(index: number, message: ChatMessage): string {
    return `${message.role}-${message.created_at ?? index}-${index}`;
  }

  private loadHistory(): void {
    this.isLoading.set(true);
    this.errorMessage.set("");
    this.chatService
      .getHistory(this.conversationId)
      .pipe(
        finalize(() => this.isLoading.set(false)),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe({
        next: (messages) => {
          this.messages.set(messages);
          this.historyLoaded = true;
          this.scrollToLatest();
        },
        error: () => {
          this.errorMessage.set("Your chat history could not be loaded.");
        },
      });
  }

  private scrollToLatest(): void {
    requestAnimationFrame(() => {
      const thread = this.messageThread?.nativeElement;
      if (thread) thread.scrollTop = thread.scrollHeight;
    });
  }
}
