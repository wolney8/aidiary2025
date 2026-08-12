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
import { NavigationEnd, Router } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatTooltipModule } from "@angular/material/tooltip";
import { filter, finalize } from "rxjs";
import { ChatContextStatus, ChatMessage, ChatStats } from "../../../core/models/chat.model";
import { AppDialogService } from "../../../core/services/app-dialog.service";
import { AuthService } from "../../../core/services/auth.service";
import { ChatService } from "../../../core/services/chat.service";

const CHAT_ENTRY_DRAFT_KEY = "openmynd_chat_entry_draft";
const STALE_CONVERSATION_THRESHOLD_MS = 2 * 60 * 60 * 1000;

interface ChatStarterChip {
  label: string;
  prompt: string;
  icon: string;
}

@Component({
  selector: "app-chat-companion",
  standalone: true,
  imports: [
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
      (keydown.escape)="minimise()"
    >
      <header class="chat-header" data-testid="chat-header">
        <div class="chat-heading" data-testid="chat-heading">
          <span class="coach-icon" aria-hidden="true">
            <mat-icon>auto_awesome</mat-icon>
          </span>
          <div>
            <h2 [attr.title]="coachName()">{{ displayCoachName() }}</h2>
            <p>Diary companion</p>
          </div>
        </div>
        <div class="chat-header-actions">
          <button
            mat-icon-button
            type="button"
            class="chat-tools-toggle"
            matTooltip="Chat tools"
            aria-label="Open chat tools"
            [attr.aria-expanded]="isToolsOpen()"
            aria-controls="chat-tools-drawer"
            [disabled]="messages().length === 0"
            (click)="toggleTools()"
            data-testid="chat-tools-button"
          >
            <mat-icon>{{ isToolsOpen() ? "keyboard_double_arrow_right" : "more_horiz" }}</mat-icon>
          </button>
          <div
            *ngIf="messages().length > 0"
            id="chat-tools-drawer"
            class="chat-tools-drawer"
            [class.is-open]="isToolsOpen()"
            [attr.aria-hidden]="!isToolsOpen()"
            data-testid="chat-tools-drawer"
            aria-label="Chat tools"
          >
            <button
              mat-icon-button
              type="button"
              matTooltip="Chat session"
              aria-label="Open chat session options"
              [disabled]="isStreaming()"
              [attr.tabindex]="isToolsOpen() ? 0 : -1"
              (click)="openSessionChoice()"
              data-testid="chat-session-button"
            >
              <mat-icon>history</mat-icon>
            </button>
            <button
              mat-icon-button
              type="button"
              matTooltip="Create diary draft"
              aria-label="Create diary draft from chat"
              [disabled]="isStreaming()"
              [attr.tabindex]="isToolsOpen() ? 0 : -1"
              (click)="createEntryDraft()"
              data-testid="chat-create-entry-button"
            >
              <mat-icon>note_add</mat-icon>
            </button>
            <button
              mat-icon-button
              type="button"
              matTooltip="Download conversation"
              aria-label="Download conversation"
              [disabled]="isStreaming()"
              [attr.tabindex]="isToolsOpen() ? 0 : -1"
              (click)="downloadConversation()"
              data-testid="chat-download-button"
            >
              <mat-icon>download</mat-icon>
            </button>
            <button
              mat-icon-button
              type="button"
              matTooltip="Clear conversation"
              aria-label="Clear conversation"
              [disabled]="isStreaming()"
              [attr.tabindex]="isToolsOpen() ? 0 : -1"
              (click)="clearConversation()"
              data-testid="chat-clear-button"
            >
              <mat-icon>delete_sweep</mat-icon>
            </button>
          </div>
          <button
            mat-icon-button
            type="button"
            matTooltip="Minimise chat"
            aria-label="Minimise chat"
            (click)="minimise()"
            data-testid="chat-close-button"
          >
            <mat-icon>keyboard_arrow_down</mat-icon>
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
          *ngIf="!isLoading() && messages().length === 0 && !showSessionChoice()"
          class="chat-empty-state"
          data-testid="chat-empty-state"
        >
          <mat-icon aria-hidden="true">forum</mat-icon>
          <h3>Start a conversation</h3>
          <p>Ask about patterns, feelings, or themes across your diary.</p>
          <small>For reflection only. This is not platform support or emergency help.</small>
          <div
            *ngIf="starterChips().length > 0"
            class="chat-starter-chips"
            data-testid="chat-starter-chips"
            aria-label="Conversation starters"
          >
            <button
              *ngFor="let chip of starterChips(); trackBy: trackStarterChip"
              type="button"
              class="chat-starter-chip"
              [disabled]="isStreaming()"
              (click)="useStarterChip(chip)"
              [attr.aria-label]="chip.label"
            >
              <mat-icon aria-hidden="true">{{ chip.icon }}</mat-icon>
              <span>{{ chip.label }}</span>
            </button>
          </div>
        </div>

        <section
          *ngIf="showSessionChoice()"
          class="chat-session-choice"
          data-testid="chat-session-choice"
          aria-label="Resume previous chat"
        >
          <mat-icon aria-hidden="true">history</mat-icon>
          <div>
            <h3>Continue previous chat?</h3>
            <p>{{ staleConversationSummary() }}</p>
          </div>
          <div class="chat-session-actions">
            <button
              mat-stroked-button
              type="button"
              (click)="continueChat()"
              data-testid="chat-continue-button"
            >
              Continue
            </button>
            <button
              mat-flat-button
              type="button"
              (click)="startNewChat()"
              data-testid="chat-start-new-button"
            >
              Start new chat
            </button>
          </div>
        </section>

        <div
          *ngIf="!isLoading() && messages().length > 0 && !showSessionChoice() && starterChips().length > 0"
          class="chat-starter-strip"
          data-testid="chat-starter-strip"
          aria-label="Conversation starters"
        >
          <button
            *ngFor="let chip of starterChips(); trackBy: trackStarterChip"
            type="button"
            class="chat-starter-chip"
            [disabled]="isStreaming()"
            (click)="useStarterChip(chip)"
            [attr.aria-label]="chip.label"
          >
            <mat-icon aria-hidden="true">{{ chip.icon }}</mat-icon>
            <span>{{ chip.label }}</span>
          </button>
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

      <aside
        *ngIf="isContextOpen()"
        id="chat-context-drawer"
        class="chat-context-drawer"
        data-testid="chat-context-drawer"
        role="region"
        aria-labelledby="chat-context-title"
      >
        <div class="chat-context-heading">
          <div>
            <h3 id="chat-context-title">Context available</h3>
            <p>{{ contextDetailSummary() }}</p>
          </div>
          <button
            mat-icon-button
            type="button"
            aria-label="Collapse chat context details"
            matTooltip="Collapse context details"
            (click)="toggleContextDrawer()"
            data-testid="chat-context-collapse-button"
          >
            <mat-icon>keyboard_arrow_down</mat-icon>
          </button>
        </div>

        <ul class="chat-context-list" aria-label="Chat context sources">
          <li
            *ngFor="let source of contextSources(); trackBy: trackContextSource"
            [class.is-available]="source.available"
          >
            <mat-icon aria-hidden="true">{{ source.icon }}</mat-icon>
            <span>{{ source.label }}</span>
            <small>{{ source.detail }}</small>
          </li>
        </ul>
      </aside>

      <aside
        *ngIf="isStatsOpen()"
        id="chat-stats-panel"
        class="chat-stats-panel"
        data-testid="chat-stats-panel"
        role="region"
        aria-labelledby="chat-stats-title"
      >
        <div class="chat-stats-heading">
          <div>
            <h3 id="chat-stats-title">Stats for nerds</h3>
            <p>{{ statsSummary() }}</p>
          </div>
          <button
            mat-icon-button
            type="button"
            aria-label="Collapse chat stats"
            matTooltip="Collapse stats"
            (click)="toggleStats()"
            data-testid="chat-stats-collapse-button"
          >
            <mat-icon>keyboard_arrow_down</mat-icon>
          </button>
        </div>

        <dl class="chat-stats-grid" *ngIf="chatStats(); else statsLoading">
          <div>
            <dt>Conversation tokens</dt>
            <dd>{{ chatStats()?.token_count || 0 }}</dd>
          </div>
          <div>
            <dt>Messages</dt>
            <dd>
              {{ chatStats()?.message_count || 0 }} /
              {{ chatStats()?.limits?.max_messages_per_conversation || 0 }}
            </dd>
          </div>
          <div>
            <dt>Chats opened</dt>
            <dd>{{ chatStats()?.conversation_count || 0 }}</dd>
          </div>
          <div>
            <dt>Active for</dt>
            <dd>{{ formatDuration(chatStats()?.active_seconds || 0) }}</dd>
          </div>
          <div>
            <dt>Monthly chat use</dt>
            <dd>{{ monthlyChatUsageLabel() }}</dd>
          </div>
          <div>
            <dt>Model context</dt>
            <dd>Last {{ chatStats()?.limits?.model_history_limit || 0 }} messages</dd>
          </div>
        </dl>
        <ng-template #statsLoading>
          <p class="chat-stats-loading">Loading usage stats…</p>
        </ng-template>
      </aside>

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
        <div class="chat-meta-actions">
          <button
            type="button"
            class="chat-context-toggle"
            [attr.aria-expanded]="isContextOpen()"
            aria-controls="chat-context-drawer"
            (click)="toggleContextDrawer()"
            data-testid="chat-context-toggle"
          >
            <mat-icon aria-hidden="true">privacy_tip</mat-icon>
            <span>{{ contextSummary() }}</span>
            <mat-icon aria-hidden="true">
              {{ isContextOpen() ? "keyboard_arrow_down" : "keyboard_arrow_up" }}
            </mat-icon>
          </button>
          <button
            type="button"
            class="chat-stats-toggle"
            [attr.aria-expanded]="isStatsOpen()"
            aria-controls="chat-stats-panel"
            (click)="toggleStats()"
            data-testid="chat-stats-toggle"
          >
            <mat-icon aria-hidden="true">query_stats</mat-icon>
            <span>Stats</span>
          </button>
        </div>
        <span>{{ draft.length }} / 2000</span>
      </div>
    </section>

    <button
      #fab
      *ngIf="!isOpen()"
      mat-fab
      type="button"
      class="chat-fab"
      [class.has-unread]="unreadResponses() > 0"
      data-testid="chat-open-button"
      aria-label="Open diary companion chat"
      [attr.aria-expanded]="isOpen()"
      (click)="open()"
    >
      <mat-icon>forum</mat-icon>
      <span
        *ngIf="unreadResponses() > 0"
        class="chat-fab-badge"
        data-testid="chat-fab-badge"
        aria-label="Unread chat responses"
      >
        {{ unreadResponses() > 9 ? "9+" : unreadResponses() }}
      </span>
    </button>
  `,
  styles: [
    `
      :host {
        position: relative;
        z-index: 900;
        --chat-edge-offset: 1rem;
        --chat-panel-width: min(26.5rem, calc(100dvw - (var(--chat-edge-offset) * 2)));
      }

      .chat-fab {
        position: fixed;
        right: var(--chat-edge-offset);
        bottom: var(--chat-edge-offset);
        z-index: 900;
        background: var(--colour-primary);
        color: var(--colour-on-primary);
        box-shadow: 0 0.5rem 1.5rem var(--colour-overlay);
      }

      .chat-fab-badge {
        position: absolute;
        top: -0.35rem;
        right: -0.35rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 1.35rem;
        height: 1.35rem;
        padding: 0 0.25rem;
        border: 2px solid var(--colour-surface);
        border-radius: var(--radius-pill);
        background: var(--colour-danger);
        color: var(--colour-on-danger);
        font-size: 0.68rem;
        font-weight: 800;
        line-height: 1;
      }

      .chat-panel {
        position: fixed;
        right: var(--chat-edge-offset);
        bottom: var(--chat-edge-offset);
        z-index: 900;
        display: grid;
        grid-template-rows: auto minmax(0, 1fr) auto auto auto;
        width: var(--chat-panel-width);
        max-width: calc(100dvw - (var(--chat-edge-offset) * 2));
        height: min(38rem, calc(100dvh - (var(--chat-edge-offset) * 2)));
        max-height: calc(100dvh - (var(--chat-edge-offset) * 2));
        box-sizing: border-box;
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
        gap: var(--spacing-md);
        min-width: 0;
        padding: 0.75rem;
        border-bottom: 1px solid var(--colour-border);
        background: var(--colour-surface-muted);
      }

      .chat-heading,
      .chat-header-actions {
        display: flex;
        align-items: center;
        gap: var(--spacing-xs);
      }

      .chat-heading {
        min-width: 0;
        gap: 0.75rem;
      }

      .chat-header-actions {
        position: relative;
        flex: 0 0 auto;
        overflow: visible;
      }

      .chat-header-actions button {
        width: 2.5rem;
        height: 2.5rem;
        flex: 0 0 2.5rem;
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
        color: var(--colour-text-primary);
      }

      .chat-header-actions button:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .chat-tools-drawer {
        position: absolute;
        top: 50%;
        right: 5.6rem;
        z-index: 2;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-elevated);
        box-shadow: 0 0.75rem 1.8rem var(--colour-overlay);
        opacity: 0;
        pointer-events: none;
        transform: translate(0.7rem, -50%) scaleX(0.85);
        transform-origin: right center;
        transition:
          opacity 0.22s cubic-bezier(0.2, 0, 0, 1),
          transform 0.22s cubic-bezier(0.2, 0, 0, 1);
      }

      .chat-tools-drawer.is-open {
        opacity: 1;
        pointer-events: auto;
        transform: translate(0, -50%) scaleX(1);
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

      .chat-empty-state small {
        max-width: 18rem;
        color: var(--colour-text-secondary);
        font-size: 0.75rem;
        line-height: 1.35;
      }

      .chat-starter-chips,
      .chat-starter-strip {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: center;
        gap: 0.45rem;
        width: 100%;
      }

      .chat-starter-chips {
        margin-top: 0.45rem;
      }

      .chat-starter-strip {
        justify-content: flex-start;
        margin-bottom: 0.8rem;
      }

      .chat-starter-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.4rem;
        min-height: 2.25rem;
        max-width: 100%;
        border: 1px solid color-mix(in srgb, var(--colour-primary) 36%, var(--colour-border));
        border-radius: var(--radius-pill);
        background: var(--colour-primary-container);
        color: var(--colour-on-primary-container);
        padding: 0.35rem 0.7rem;
        font: inherit;
        font-size: 0.78rem;
        font-weight: 800;
        cursor: pointer;
      }

      .chat-starter-chip:hover {
        border-color: var(--colour-primary);
        box-shadow: 0 0.35rem 1rem color-mix(in srgb, var(--colour-primary) 18%, transparent);
      }

      .chat-starter-chip:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .chat-starter-chip:disabled {
        cursor: not-allowed;
        opacity: 0.62;
      }

      .chat-starter-chip mat-icon {
        width: 1rem;
        height: 1rem;
        flex: 0 0 1rem;
        font-size: 1rem;
      }

      .chat-starter-chip span {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .chat-session-choice {
        display: grid;
        grid-template-columns: 2rem minmax(0, 1fr);
        gap: 0.65rem;
        margin-bottom: 0.9rem;
        padding: 0.8rem;
        border: 1px solid color-mix(in srgb, var(--colour-primary) 50%, var(--colour-border));
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
      }

      .chat-session-choice > mat-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2rem;
        height: 2rem;
        border-radius: var(--radius-pill);
        background: var(--colour-primary-container);
        color: var(--colour-on-primary-container);
      }

      .chat-session-choice h3 {
        color: var(--colour-text-primary);
        font-size: 0.92rem;
        line-height: 1.25;
      }

      .chat-session-choice p {
        margin-top: 0.15rem;
        color: var(--colour-text-secondary);
        font-size: 0.78rem;
        line-height: 1.35;
      }

      .chat-session-actions {
        grid-column: 1 / -1;
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 0.5rem;
      }

      .chat-session-actions button {
        border-radius: var(--radius-pill);
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

      .chat-context-drawer {
        position: absolute;
        right: 0.75rem;
        bottom: 5.6rem;
        left: 0.75rem;
        z-index: 3;
        max-height: min(13rem, 34dvh);
        overflow-y: auto;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
        padding: 0.85rem 1rem;
        box-shadow: 0 1rem 2.5rem var(--colour-overlay);
        animation: chat-drawer-rise 0.22s cubic-bezier(0.2, 0, 0, 1);
      }

      .chat-stats-panel {
        position: absolute;
        right: 0.75rem;
        bottom: 5.6rem;
        left: 0.75rem;
        z-index: 3;
        max-height: min(15rem, 38dvh);
        overflow-y: auto;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
        padding: 0.85rem 1rem;
        box-shadow: 0 1rem 2.5rem var(--colour-overlay);
        animation: chat-drawer-rise 0.22s cubic-bezier(0.2, 0, 0, 1);
      }

      .chat-context-heading,
      .chat-stats-heading {
        position: sticky;
        top: -0.85rem;
        z-index: 1;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--spacing-md);
        margin-bottom: 0.7rem;
        padding-top: 0.85rem;
        padding-bottom: 0.45rem;
        background: var(--colour-surface-muted);
      }

      .chat-context-heading h3,
      .chat-stats-heading h3 {
        color: var(--colour-text-primary);
        font-size: 0.95rem;
        line-height: 1.25;
      }

      .chat-context-heading p,
      .chat-stats-heading p,
      .chat-stats-loading {
        margin-top: 0.15rem;
        color: var(--colour-text-secondary);
        font-size: 0.78rem;
        line-height: 1.35;
      }

      .chat-context-heading button,
      .chat-stats-heading button {
        width: 2.25rem;
        height: 2.25rem;
        flex: 0 0 2.25rem;
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
        color: var(--colour-text-primary);
      }

      .chat-stats-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.55rem;
        margin: 0;
      }

      .chat-stats-grid div {
        min-width: 0;
        padding: 0.6rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface);
      }

      .chat-stats-grid dt {
        color: var(--colour-text-secondary);
        font-size: 0.7rem;
        font-weight: 700;
      }

      .chat-stats-grid dd {
        margin: 0.15rem 0 0;
        color: var(--colour-text-primary);
        font-size: 0.86rem;
        font-weight: 800;
      }

      .chat-context-list {
        display: grid;
        gap: 0.45rem;
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .chat-context-list li {
        display: grid;
        grid-template-columns: 1.5rem minmax(0, 1fr) auto;
        align-items: center;
        gap: 0.55rem;
        min-height: 2.5rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface);
        color: var(--colour-text-secondary);
        padding: 0.35rem 0.7rem;
      }

      .chat-context-list li.is-available {
        border-color: color-mix(in srgb, var(--colour-primary) 50%, var(--colour-border));
        color: var(--colour-text-primary);
      }

      .chat-context-list mat-icon {
        width: 1.25rem;
        height: 1.25rem;
        font-size: 1.25rem;
        color: var(--colour-primary);
      }

      .chat-context-list span {
        min-width: 0;
        overflow: hidden;
        font-size: 0.82rem;
        font-weight: 700;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .chat-context-list small {
        color: var(--colour-text-secondary);
        font-size: 0.72rem;
        white-space: nowrap;
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
        align-items: center;
        gap: 0.75rem;
        padding: 0 1rem 0.8rem;
        background: var(--colour-surface-elevated);
        min-width: 0;
      }

      .chat-meta-actions {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        min-width: 0;
      }

      .chat-context-toggle,
      .chat-stats-toggle {
        display: inline-flex;
        align-items: center;
        min-width: 0;
        max-width: 100%;
        min-height: 2rem;
        gap: 0.35rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
        color: var(--colour-text-secondary);
        padding: 0.2rem 0.45rem 0.2rem 0.55rem;
        font: inherit;
        font-size: 0.78rem;
        cursor: pointer;
      }

      .chat-context-toggle:hover,
      .chat-stats-toggle:hover {
        border-color: var(--colour-primary);
        color: var(--colour-text-primary);
      }

      .chat-context-toggle:focus-visible,
      .chat-stats-toggle:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .chat-context-toggle mat-icon,
      .chat-stats-toggle mat-icon {
        width: 1rem;
        height: 1rem;
        flex: 0 0 1rem;
        font-size: 1rem;
      }

      .chat-context-toggle span,
      .chat-stats-toggle span {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .chat-composer-meta span:last-child {
        flex: 0 0 auto;
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

      @keyframes chat-drawer-rise {
        from {
          opacity: 0;
          transform: translateY(0.75rem);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      @media (max-width: 599px) {
        :host {
          --chat-edge-offset: 0.75rem;
        }

        .chat-panel {
          left: var(--chat-edge-offset);
          width: auto;
          height: min(38rem, calc(100dvh - (var(--chat-edge-offset) * 2)));
        }

        .chat-tools-drawer {
          top: calc(100% + 0.45rem);
          right: 0;
          transform: translateY(-0.35rem) scaleY(0.85);
          transform-origin: top right;
        }

        .chat-tools-drawer.is-open {
          transform: translateY(0) scaleY(1);
        }

        .chat-context-drawer {
          right: 0.65rem;
          bottom: 6.8rem;
          left: 0.65rem;
        }

        .chat-stats-panel {
          right: 0.65rem;
          bottom: 6.8rem;
          left: 0.65rem;
        }

        .message-bubble {
          max-width: 88%;
        }

        .chat-composer-meta {
          align-items: flex-end;
          flex-direction: column;
          gap: 0.45rem;
        }

        .chat-meta-actions,
        .chat-context-toggle {
          width: 100%;
        }

        .chat-meta-actions {
          flex-direction: column;
          align-items: stretch;
        }

        .chat-context-toggle,
        .chat-stats-toggle {
          justify-content: center;
        }

        .chat-stats-grid {
          grid-template-columns: 1fr;
        }

        .chat-context-list li {
          grid-template-columns: 1.5rem minmax(0, 1fr);
          border-radius: var(--radius-lg);
        }

        .chat-context-list small {
          grid-column: 2;
          white-space: normal;
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .typing-dot,
        .chat-context-drawer,
        .chat-stats-panel,
        .chat-tools-drawer {
          animation: none;
          transition: none;
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
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly isOpen = signal(false);
  readonly isLoading = signal(false);
  readonly isStreaming = signal(false);
  readonly showTypingIndicator = signal(false);
  readonly errorMessage = signal("");
  readonly messages = signal<ChatMessage[]>([]);
  readonly isContextOpen = signal(false);
  readonly isStatsOpen = signal(false);
  readonly isToolsOpen = signal(false);
  readonly showSessionChoice = signal(false);
  readonly unreadResponses = signal(0);
  readonly contextStatus = signal<ChatContextStatus | null>(null);
  readonly chatStats = signal<ChatStats | null>(null);
  readonly currentRoute = signal(this.router.url);
  readonly contextSources = computed(() => {
    const status = this.contextStatus();
    const sources = status?.sources ?? [];
    return sources.map((source) => {
      const available = Boolean(status?.history_enabled && source.enabled && source.count > 0);
      return {
        key: source.key,
        label: source.label,
        icon: this.contextIconFor(source.key),
        available,
        detail: !status?.history_enabled
          ? "Off"
          : available
            ? "Available"
            : "No records",
      };
    });
  });
  readonly contextSummary = computed(() => {
    const status = this.contextStatus();
    if (!status) return "Checking context settings…";
    if (!status.history_enabled) {
      return "Past-entry references off";
    }
    const activeSources = status.sources
      .filter((source) => source.enabled && source.count > 0)
      .map((source) => source.label);
    if (activeSources.length === 0) return "No prior context";
    return `May reference ${activeSources.length} source${activeSources.length === 1 ? "" : "s"}`;
  });
  readonly contextDetailSummary = computed(() => {
    const status = this.contextStatus();
    if (!status) return "Checking your current chat context settings.";
    if (!status.history_enabled) {
      return "Past-entry references are off. Chat will not use diary, dream, thought record, or important day history.";
    }
    return "Chat may use these record types when relevant. It does not show private record text here.";
  });
  readonly staleConversationSummary = computed(() => {
    const lastMessage = this.lastMessageDate(this.messages());
    if (!lastMessage) return "Start fresh or keep the current thread.";
    return `Last active ${this.formatRelativeIdle(lastMessage)}. Start fresh or keep the current thread.`;
  });
  readonly statsSummary = computed(() => {
    const stats = this.chatStats();
    if (!stats) return "Loading conversation and plan limits.";
    return `${stats.message_count} messages kept here. ${this.monthlyChatUsageLabel()}.`;
  });
  readonly coachName = computed(() => {
    const user = this.authService.getCurrentUser();
    return (
      user?.chatgpt_daily_diary_coachname?.trim() ||
      user?.chatgpt_dream_diary_coachname?.trim() ||
      "OpenMynd"
    );
  });
  readonly displayCoachName = computed(() => {
    const name = this.coachName();
    return name.length > 22 ? `${name.slice(0, 21).trimEnd()}…` : name;
  });
  readonly starterChips = computed<ChatStarterChip[]>(() => {
    const url = this.currentRoute();
    const hasDiary = this.contextCount("daily") > 0;
    const hasDreams = this.contextCount("dream") > 0;
    const hasThoughtRecords = this.contextCount("thought_record") > 0;
    const hasImportantDays = this.contextCount("important_day") > 0;

    if (/^\/important-days(?:\/|\?|#|$)/.test(url)) {
      return [
        hasImportantDays
          ? {
              label: "Reflect on important dates",
              prompt:
                "Help me reflect on patterns around my important days without quoting private details.",
              icon: "event",
            }
          : {
              label: "Create my first important day",
              prompt: "Help me decide what kind of important day is useful to track.",
              icon: "add_circle",
            },
        {
          label: "What should I track?",
          prompt:
            "What kinds of personal dates are useful to track in Important days?",
          icon: "lightbulb",
        },
      ];
    }

    if (/^\/cbt(?:\/|\?|#|$)/.test(url)) {
      return [
        {
          label: "What's a Thought Record?",
          prompt: "What is a CBT thought record and when should I use one?",
          icon: "psychology_alt",
        },
        {
          label: "How do I fill this out?",
          prompt: "Guide me through filling out a thought record step by step.",
          icon: "checklist",
        },
        hasThoughtRecords
          ? {
              label: "Spot CBT patterns",
              prompt:
                "Help me reflect on patterns across my thought records without quoting private details.",
              icon: "insights",
            }
          : {
              label: "Start with a situation",
              prompt: "Help me choose a clear situation for my first thought record.",
              icon: "edit_note",
            },
      ];
    }

    if (/^\/entries\/create(?:\/|\?|#|$)/.test(url)) {
      return [
        {
          label: "Draft today's diary",
          prompt: "Help me turn today's thoughts into a clear diary entry.",
          icon: "edit_note",
        },
        {
          label: "Turn this into tags",
          prompt: "Suggest a few useful tags, people, or places for this entry.",
          icon: "sell",
        },
        {
          label: "Diary or dream?",
          prompt: "Help me decide whether this should be a diary entry or a dream entry.",
          icon: "alt_route",
        },
      ];
    }

    if (/^\/reflections(?:\/|\?|#|$)/.test(url)) {
      return [
        {
          label: "Explain this reflection",
          prompt: "Help me understand what this reflection is showing me.",
          icon: "auto_stories",
        },
        {
          label: "What changed over time?",
          prompt:
            "Help me compare this reflection with earlier patterns without quoting private details.",
          icon: "timeline",
        },
      ];
    }

    return [
      hasDiary || hasDreams
        ? {
            label: "What patterns stand out?",
            prompt:
              "What patterns stand out across my recent diary and dream entries?",
            icon: "travel_explore",
          }
        : {
            label: "What should I write?",
            prompt: "Help me choose a useful diary prompt for today.",
            icon: "edit_note",
          },
      {
        label: "Summarise recent entries",
        prompt:
          "Summarise my recent diary context at a high level without quoting private details.",
        icon: "summarize",
      },
      {
        label: "What should I write next?",
        prompt: "Suggest a focused diary prompt based on my current patterns.",
        icon: "question_answer",
      },
    ];
  });
  draft = "";
  private conversationId = this.chatService.getOrCreateConversationId();
  private historyLoaded = false;

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((event) => this.currentRoute.set(event.urlAfterRedirects));
  }

  open(): void {
    this.isOpen.set(true);
    this.unreadResponses.set(0);
    if (!this.historyLoaded) this.loadHistory();
    else {
      this.refreshSessionChoice();
      this.loadStats();
      this.scrollToLatest();
    }
    if (!this.contextStatus()) this.loadContextStatus();
    setTimeout(() => this.messageInput?.nativeElement.focus());
  }

  close(): void {
    this.minimise();
  }

  minimise(): void {
    this.isOpen.set(false);
    this.isToolsOpen.set(false);
    this.isContextOpen.set(false);
    this.isStatsOpen.set(false);
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

  toggleContextDrawer(): void {
    this.isStatsOpen.set(false);
    this.isToolsOpen.set(false);
    this.isContextOpen.update((value) => !value);
  }

  toggleStats(): void {
    this.isContextOpen.set(false);
    this.isToolsOpen.set(false);
    this.isStatsOpen.update((value) => !value);
    if (!this.chatStats()) this.loadStats();
  }

  toggleTools(): void {
    this.isToolsOpen.update((value) => !value);
  }

  openSessionChoice(): void {
    if (this.messages().length === 0) return;
    this.isContextOpen.set(false);
    this.isStatsOpen.set(false);
    this.isToolsOpen.set(false);
    this.showSessionChoice.set(true);
    requestAnimationFrame(() => {
      const thread = this.messageThread?.nativeElement;
      if (thread) thread.scrollTop = 0;
    });
  }

  continueChat(): void {
    this.showSessionChoice.set(false);
    this.scrollToLatest();
    setTimeout(() => this.messageInput?.nativeElement.focus());
  }

  startNewChat(): void {
    this.conversationId = this.chatService.resetConversationId();
    this.messages.set([]);
    this.historyLoaded = true;
    this.showSessionChoice.set(false);
    this.isContextOpen.set(false);
    this.isStatsOpen.set(false);
    this.isToolsOpen.set(false);
    this.errorMessage.set("");
    this.chatStats.set(null);
    this.loadStats();
    setTimeout(() => this.messageInput?.nativeElement.focus());
  }

  downloadConversation(): void {
    const messages = this.messages();
    if (messages.length === 0) return;

    const timestamp = new Date();
    const transcript = [
      "OpenMynd chat conversation",
      `Downloaded: ${timestamp.toLocaleString()}`,
      "For reflection only. This chat is not platform support or emergency help.",
      "",
      ...messages.map((message) => {
        const speaker = message.role === "user" ? "You" : this.coachName();
        const time = message.created_at
          ? new Date(message.created_at).toLocaleString()
          : "Unknown time";
        return `[${time}] ${speaker}\n${message.content.trim()}`;
      }),
      "",
    ].join("\n\n");

    const blob = new Blob([transcript], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `openmynd-chat-${this.formatDownloadTimestamp(timestamp)}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  createEntryDraft(): void {
    const messages = this.messages();
    if (messages.length === 0 || this.isStreaming()) return;

    const draft = {
      title: "Chat reflection",
      body: this.buildEntryDraftBody(messages),
      tags: ["chat-reflection"],
      createdAt: new Date().toISOString(),
    };
    sessionStorage.setItem(CHAT_ENTRY_DRAFT_KEY, JSON.stringify(draft));
    this.isOpen.set(false);
    void this.router.navigate(["/entries/create"], {
      queryParams: { type: "daily", source: "chat" },
    });
  }

  useStarterChip(chip: ChatStarterChip): void {
    if (this.isStreaming()) return;
    this.draft = chip.prompt;
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
          if (!this.isOpen()) {
            this.unreadResponses.update((count) => count + 1);
          }
          this.scrollToLatest();
          this.loadStats();
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
          this.showSessionChoice.set(false);
          this.chatStats.set(null);
          this.loadStats();
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

  trackContextSource(index: number, source: { key: string }): string {
    return source.key || String(index);
  }

  trackStarterChip(index: number, chip: ChatStarterChip): string {
    return `${chip.label}-${index}`;
  }

  private contextCount(key: string): number {
    return (
      this.contextStatus()?.sources.find((source) => source.key === key)?.count ?? 0
    );
  }

  private contextIconFor(key: string): string {
    switch (key) {
      case "daily":
        return "book";
      case "dream":
        return "bedtime";
      case "thought_record":
        return "psychology_alt";
      case "important_day":
        return "event";
      default:
        return "source";
    }
  }

  private buildEntryDraftBody(messages: ChatMessage[]): string {
    const latestAssistant = [...messages]
      .reverse()
      .find((message) => message.role === "assistant" && message.content.trim());
    const recentMessages = messages
      .slice(-8)
      .map((message) => {
        const speaker = message.role === "user" ? "You" : this.coachName();
        return `${speaker}: ${message.content.trim()}`;
      })
      .join("\n\n");

    return [
      "Drafted from chat. Edit this into a diary entry before saving.",
      "",
      latestAssistant?.content.trim()
        ? `Useful reflection:\n${latestAssistant.content.trim()}`
        : "",
      "",
      "Conversation notes:",
      recentMessages,
    ]
      .filter((section) => section.trim().length > 0)
      .join("\n\n");
  }

  monthlyChatUsageLabel(): string {
    const usage = this.chatStats()?.limits?.monthly_chat;
    if (!usage) return "Monthly chat use unavailable";
    if (usage.unlimited || usage.limit === null) {
      return `${usage.used} chats this month, unlimited`;
    }
    return `${usage.used} / ${usage.limit} chats this month`;
  }

  formatDuration(totalSeconds: number): string {
    const seconds = Math.max(0, Math.floor(totalSeconds));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    if (minutes > 0) return `${minutes}m`;
    return `${seconds}s`;
  }

  private formatDownloadTimestamp(date: Date): string {
    const pad = (value: number) => String(value).padStart(2, "0");
    return [
      date.getFullYear(),
      pad(date.getMonth() + 1),
      pad(date.getDate()),
      "-",
      pad(date.getHours()),
      pad(date.getMinutes()),
    ].join("");
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
          this.refreshSessionChoice();
          this.loadStats();
          this.scrollToLatest();
        },
        error: () => {
          this.errorMessage.set("Your chat history could not be loaded.");
        },
      });
  }

  private loadContextStatus(): void {
    this.chatService
      .getContextStatus()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (status) => this.contextStatus.set(status),
        error: () => {
          this.contextStatus.set({
            history_enabled: false,
            sources: [],
          });
        },
      });
  }

  private loadStats(): void {
    this.chatService
      .getStats(this.conversationId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (stats) => this.chatStats.set(stats),
        error: () => this.chatStats.set(null),
      });
  }

  private refreshSessionChoice(): void {
    const messages = this.messages();
    if (messages.length === 0) {
      this.showSessionChoice.set(false);
      return;
    }
    const lastMessage = this.lastMessageDate(messages);
    this.showSessionChoice.set(
      Boolean(
        lastMessage &&
          Date.now() - lastMessage.getTime() > STALE_CONVERSATION_THRESHOLD_MS,
      ),
    );
  }

  private lastMessageDate(messages: ChatMessage[]): Date | null {
    for (const message of [...messages].reverse()) {
      if (!message.created_at) continue;
      const parsed = new Date(message.created_at);
      if (!Number.isNaN(parsed.getTime())) return parsed;
    }
    return null;
  }

  private formatRelativeIdle(date: Date): string {
    const elapsedMs = Math.max(0, Date.now() - date.getTime());
    const hours = Math.floor(elapsedMs / 3_600_000);
    const days = Math.floor(hours / 24);
    if (days > 0) return `${days} day${days === 1 ? "" : "s"} ago`;
    if (hours > 0) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
    const minutes = Math.max(1, Math.floor(elapsedMs / 60_000));
    return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  }

  private scrollToLatest(): void {
    requestAnimationFrame(() => {
      const thread = this.messageThread?.nativeElement;
      if (thread) thread.scrollTop = thread.scrollHeight;
    });
  }
}
