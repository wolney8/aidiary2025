import {
  Component,
  Output,
  EventEmitter,
  inject,
  OnDestroy,
  OnInit,
  ViewChild,
  computed,
  signal,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { BreakpointObserver } from "@angular/cdk/layout";
import { MatToolbarModule } from "@angular/material/toolbar";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatMenuModule, MatMenuTrigger } from "@angular/material/menu";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { Router, RouterModule, NavigationEnd } from "@angular/router";
import { ReactiveFormsModule, FormBuilder } from "@angular/forms";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import {
  trigger,
  state,
  style,
  transition,
  animate,
} from "@angular/animations";
import { DomSanitizer, SafeHtml } from "@angular/platform-browser";
import { AuthService } from "../../services/auth.service";
import { APP_VERSION } from "../../../version";
import { Observable, Subject } from "rxjs";
import { map, filter, takeUntil } from "rxjs/operators";
import { SearchService } from "../../services/search.service";
import { Location } from "@angular/common";
import { ThemeService } from "../../services/theme.service";
import { ImportJobService } from "../../services/import-job.service";
import { type AppNotification } from "../../services/import-job.service";

type SearchFilterKey = "keywords" | "tags" | "people" | "date";

@Component({
  selector: "app-top-bar",
  standalone: true,
  imports: [
    CommonModule,
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatProgressBarModule,
    MatSlideToggleModule,
    RouterModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  animations: [
    trigger("slideDown", [
      transition(":enter", [
        style({ opacity: "0", transform: "translateY(-10px)" }),
        animate(
          "200ms cubic-bezier(0.4, 0.0, 0.2, 1)",
          style({ opacity: "1", transform: "translateY(0)" }),
        ),
      ]),
      transition(":leave", [
        animate(
          "150ms cubic-bezier(0.4, 0.0, 1, 1)",
          style({ opacity: "0", transform: "translateY(-10px)" }),
        ),
      ]),
    ]),
  ],
  template: `
    <mat-toolbar
      color="primary"
      [class.compact-toolbar]="isCompact()"
      [class.compact-search-mode]="isCompactSearchOpen()"
    >
      <button mat-icon-button (click)="toggleSidenav.emit()" aria-label="Open navigation">
        <mat-icon>menu</mat-icon>
      </button>

      <button
        class="logo"
        (click)="goHome()"
        aria-label="Home"
        *ngIf="!isCompactSearchOpen()"
      >
        LOGO
      </button>

      <div
        class="search-wrapper"
        [class.search-wrapper-compact]="isCompact()"
        [class.search-wrapper-hidden]="isCompact() && !isCompactSearchOpen()"
        [class.search-wrapper-expanded]="isCompact() && isCompactSearchOpen()"
      >
        <form
          [formGroup]="searchForm"
          (ngSubmit)="filterResults()"
          class="search-form"
        >
          <div class="search-shell">
            <button
              type="button"
              class="search-button"
              (click)="filterResults()"
              [disabled]="isSearching"
            >
              <mat-progress-spinner
                *ngIf="isSearching"
                diameter="20"
                mode="indeterminate"
              ></mat-progress-spinner>
              <mat-icon *ngIf="!isSearching">search</mat-icon>
            </button>
            <input
              #searchInput
              class="search-input"
              type="search"
              placeholder="Search entries, tags, people, dates..."
              formControlName="query"
              (keydown.enter)="$event.preventDefault(); filterResults()"
              (focus)="onSearchInputFocus()"
              (blur)="onSearchInputBlur()"
              (input)="onSearchInputChange($event)"
            />
            <button
              type="button"
              class="search-filter-button"
              [matMenuTriggerFor]="searchFiltersMenu"
              aria-label="Choose search fields"
              [attr.aria-description]="getSearchFilterSummary()"
            >
              <mat-icon>tune</mat-icon>
            </button>
            <button
              *ngIf="isCompact()"
              type="button"
              class="compact-search-close"
              (click)="closeCompactSearch()"
              aria-label="Close search"
            >
              <mat-icon>close</mat-icon>
            </button>
          </div>

          <mat-menu #searchFiltersMenu="matMenu" aria-label="Search fields">
            <button mat-menu-item type="button" (click)="selectAllSearchFilters()">
              <mat-icon>{{ areAllSearchFiltersSelected() ? "check" : "search" }}</mat-icon>
              <span>All fields</span>
            </button>
            <button
              mat-menu-item
              type="button"
              *ngFor="let option of searchFilterOptions"
              (click)="toggleSearchFilter(option.key)"
            >
              <mat-icon>{{ isSearchFilterSelected(option.key) ? "check" : option.icon }}</mat-icon>
              <span>{{ option.label }}</span>
            </button>
          </mat-menu>

          <!-- Search History Dropdown (Google-style) -->
          <div
            class="search-history-dropdown"
            *ngIf="
              (!isCompact() || isCompactSearchOpen()) &&
              showSearchHistory &&
              (filteredSearchHistory.length > 0 ||
                (searchInputFocused && currentSearchQuery.length === 0))
            "
            [@slideDown]
          >
            <!-- Recent Searches Header -->
            <div
              class="search-history-header"
              *ngIf="filteredSearchHistory.length > 0"
            >
              <span class="search-history-title">Recent searches</span>
            </div>

            <!-- History Items -->
            <div
              class="search-history-item"
              *ngFor="let historyItem of filteredSearchHistory"
              (click)="selectHistoryItem(historyItem)"
            >
              <mat-icon class="history-icon">history</mat-icon>
              <span
                class="history-text"
                [innerHTML]="highlightMatch(historyItem, currentSearchQuery)"
              ></span>
              <button
                class="history-remove"
                (click)="removeHistoryItem(historyItem, $event)"
                type="button"
                [attr.aria-label]="'Remove ' + historyItem + ' from history'"
              >
                <mat-icon>close</mat-icon>
              </button>
            </div>

            <!-- Empty State -->
            <div
              class="search-history-empty"
              *ngIf="
                filteredSearchHistory.length === 0 &&
                searchInputFocused &&
                currentSearchQuery.length === 0
              "
            >
              <mat-icon class="empty-icon">search</mat-icon>
              <span class="empty-text"
                >Start searching to see recent searches</span
              >
            </div>
          </div>
        </form>
      </div>

      <span class="spacer" *ngIf="!isCompactSearchOpen()"></span>

      <div class="compact-actions" *ngIf="isCompact() && !isCompactSearchOpen()">
        <button
          type="button"
          class="theme-toggle"
          [class.is-dark]="isDarkTheme()"
          (click)="toggleTheme()"
          role="switch"
          [attr.aria-checked]="isDarkTheme()"
          [attr.aria-label]="
            isDarkTheme() ? 'Switch to light mode' : 'Switch to dark mode'
          "
        >
          <span class="theme-toggle-track" aria-hidden="true">
            <span class="theme-toggle-slot">
              <mat-icon>light_mode</mat-icon>
            </span>
            <span class="theme-toggle-slot">
              <mat-icon>dark_mode</mat-icon>
            </span>
          </span>
        </button>
        <button
          mat-icon-button
          type="button"
          (click)="openCompactSearch()"
          aria-label="Open search"
          [attr.aria-expanded]="isCompactSearchOpen()"
        >
          <mat-icon>search</mat-icon>
        </button>
      </div>

      <div class="user-section" *ngIf="!isCompactSearchOpen()">
        <ng-container *ngIf="userName$ | async as name">
          <span class="user-name" *ngIf="showUserName()">{{ name }}</span>
        </ng-container>
        <button
          type="button"
          class="theme-toggle"
          [class.is-dark]="isDarkTheme()"
          (click)="toggleTheme()"
          role="switch"
          [attr.aria-checked]="isDarkTheme()"
          [attr.aria-label]="
            isDarkTheme() ? 'Switch to light mode' : 'Switch to dark mode'
          "
        >
          <span class="theme-toggle-track" aria-hidden="true">
            <span class="theme-toggle-slot">
              <mat-icon>light_mode</mat-icon>
            </span>
            <span class="theme-toggle-slot">
              <mat-icon>dark_mode</mat-icon>
            </span>
          </span>
        </button>
        <span class="version-label" *ngIf="showVersionLabel()">{{
          versionLabel
        }}</span>
        <button
          #notificationMenuTrigger="matMenuTrigger"
          mat-icon-button
          class="notification-bell"
          type="button"
          [matMenuTriggerFor]="notificationMenu"
          aria-label="Open notifications"
        >
          <ng-container *ngIf="notifications$ | async as notifications">
            <mat-icon>{{ hasRunningImport(notifications) ? "notifications_active" : "notifications_none" }}</mat-icon>
            <span
              *ngIf="getUnreadCount(notifications) > 0"
              class="notification-count"
              aria-hidden="true"
            >{{ getUnreadBadgeLabel(notifications) }}</span>
          </ng-container>
        </button>
        <button
          mat-icon-button
          class="account-menu-trigger"
          [matMenuTriggerFor]="userMenu"
          aria-label="Open account menu"
        >
          <ng-container *ngIf="currentUser$ | async as user">
            <img
              *ngIf="user.profile_picture_url; else accountIcon"
              class="account-avatar"
              [src]="user.profile_picture_url"
              alt=""
            />
            <ng-template #accountIcon>
              <mat-icon>account_circle</mat-icon>
            </ng-template>
          </ng-container>
        </button>
      </div>

      <mat-menu #userMenu="matMenu">
        <button mat-menu-item routerLink="/profile">Profile</button>
        <button mat-menu-item routerLink="/settings">Settings</button>
        <button mat-menu-item disabled>{{ versionLabel }}</button>
        <button mat-menu-item (click)="logout()">Logout</button>
      </mat-menu>

      <mat-menu #notificationMenu="matMenu" class="notification-menu">
        <div class="notification-panel" (click)="$event.stopPropagation()">
          <div class="notification-panel__header">
            <div class="notification-panel__title">
              <mat-icon aria-hidden="true">notifications</mat-icon>
              <strong>Notifications</strong>
            </div>
            <button mat-button type="button" (click)="clearNotifications()">
              Clear
            </button>
          </div>
          <div class="notification-panel__filters">
            <mat-slide-toggle
              [checked]="showUnreadOnly()"
              (change)="showUnreadOnly.set($event.checked)"
            >Only show unread</mat-slide-toggle>
          </div>
          <ng-container *ngIf="notifications$ | async as notifications">
            <div
              *ngFor="let notification of getVisibleNotifications(notifications)"
              class="notification-item"
              [class.notification-item--unread]="notification.unread"
              tabindex="0"
              role="article"
              [attr.aria-label]="notification.title + (notification.unread ? ', unread' : '')"
              (click)="markNotificationRead(notification.id)"
              (keydown.enter)="markNotificationRead(notification.id)"
              (keydown.space)="$event.preventDefault(); markNotificationRead(notification.id)"
            >
              <span
                *ngIf="notification.unread"
                class="notification-unread-dot"
                aria-label="Unread notification"
              ></span>
              <div class="notification-item__title">
                <mat-icon aria-hidden="true">
                  {{ notification.status === "completed" ? "task_alt" : notification.status === "failed" ? "error" : "sync" }}
                </mat-icon>
                <strong>{{ notification.title }}</strong>
              </div>
              <p>{{ notification.message }}</p>
              <mat-progress-bar
                *ngIf="notification.status === 'queued' || notification.status === 'running'"
                mode="determinate"
                [value]="notification.percent"
                aria-label="Import progress"
              ></mat-progress-bar>
              <p class="notification-item__progress" *ngIf="notification.total > 0">
                {{ notification.processed }} of {{ notification.total }} entries
              </p>
              <p class="notification-item__delayed" *ngIf="notification.isDelayed">
                Progress has not updated recently. The import is still being monitored.
              </p>
              <div class="notification-item__actions">
                <button
                  mat-stroked-button
                  type="button"
                  (click)="$event.stopPropagation(); openImportPage(notification)"
                >
                  Go to import
                </button>
                <button
                  *ngIf="notification.status === 'completed' || notification.status === 'failed'"
                  mat-button
                  type="button"
                  (click)="$event.stopPropagation(); dismissImportNotification(notification.id)"
                >
                  Dismiss
                </button>
              </div>
            </div>
            <p
              *ngIf="getVisibleNotifications(notifications).length === 0"
              class="notification-panel__empty"
            >
              {{ showUnreadOnly() ? "No unread notifications." : "No notifications." }}
            </p>
          </ng-container>
        </div>
      </mat-menu>
    </mat-toolbar>
  `,
  styles: [
    `
      mat-toolbar {
        gap: var(--spacing-sm);
        min-height: 72px;
        padding-inline: clamp(0.5rem, 2vw, 1rem);
        position: relative;
        flex-wrap: nowrap;
        background: var(--colour-toolbar);
        color: var(--colour-toolbar-text);
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 24px rgba(2, 6, 23, 0.2);
      }
      .compact-toolbar {
        min-height: 64px;
      }
      .compact-search-mode {
        gap: 0.5rem;
      }
      .logo {
        background: rgba(255, 255, 255, 0.12);
        color: var(--colour-toolbar-text);
        padding: 8px 16px;
        border-radius: var(--radius-pill);
        font-weight: 700;
        cursor: pointer;
        border: 1px solid rgba(255, 255, 255, 0.18);
      }
      .spacer {
        flex: 1;
      }
      .search-wrapper {
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
        gap: var(--spacing-sm);
        min-width: 0;
      }
      .search-wrapper-hidden {
        display: none;
      }
      .search-wrapper-expanded {
        flex: 1 1 auto;
      }
      .search-form {
        width: 100%;
        max-width: 540px;
        position: relative;
      }
      .search-wrapper-compact .search-form {
        max-width: none;
      }
      .search-shell {
        display: flex;
        align-items: center;
        width: 100%;
        background: rgba(5, 11, 24, 0.68);
        border-radius: var(--radius-pill);
        border: 1px solid rgba(255, 255, 255, 0.12);
        padding: 6px 12px;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
      }
      .compact-search-close {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: none;
        background: transparent;
        color: rgba(255, 255, 255, 0.8);
        padding: 4px;
        margin-left: 6px;
        cursor: pointer;
      }
      .search-filter-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex: 0 0 36px;
        width: 36px;
        height: 36px;
        padding: 0;
        border: 0;
        border-radius: 50%;
        background: transparent;
        color: rgba(255, 255, 255, 0.82);
        cursor: pointer;
      }
      .search-filter-button:hover,
      .search-filter-button:focus-visible {
        background: rgba(255, 255, 255, 0.12);
      }
      .search-filter-button:focus-visible {
        outline: 2px solid var(--colour-toolbar-text);
        outline-offset: 2px;
      }
      .search-shell:focus-within {
        border-color: var(--colour-primary);
        box-shadow: 0 0 0 2px rgba(155, 184, 255, 0.24);
      }
      .search-button {
        background: none;
        border: none;
        color: rgba(255, 255, 255, 0.82);
        cursor: pointer;
        padding: 4px;
        margin-right: 8px;
      }
      .search-input {
        flex: 1;
        border: none;
        outline: none;
        font-size: 16px;
        background: transparent;
        color: var(--colour-toolbar-text);
      }
      .search-input::placeholder {
        color: rgba(226, 232, 240, 0.72);
      }
      .user-section {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        flex-shrink: 0;
      }
      .account-menu-trigger {
        overflow: hidden;
      }
      .account-avatar {
        display: block;
        width: 32px;
        height: 32px;
        border: 1px solid rgba(255, 255, 255, 0.36);
        border-radius: 50%;
        object-fit: cover;
      }
      .compact-actions {
        display: flex;
        align-items: center;
        gap: 0.25rem;
      }
      .theme-toggle {
        width: 48px;
        height: 48px;
        padding: 0;
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 32px;
        overflow: hidden;
        cursor: pointer;
        background: rgba(255, 255, 255, 0.06);
        color: #ffffff;
        flex-shrink: 0;
        transition:
          border-color 0.2s ease,
          background-color 0.2s ease,
          box-shadow 0.2s ease;
      }
      .theme-toggle:hover {
        background: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.3);
      }
      .theme-toggle:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }
      .theme-toggle-track {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 96px;
        transform: translateY(0);
        transition: transform 0.3s cubic-bezier(0.2, 0, 0, 1);
      }
      .theme-toggle.is-dark .theme-toggle-track {
        transform: translateY(-48px);
      }
      .theme-toggle-slot {
        width: 48px;
        height: 48px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
      }
      .theme-toggle-slot mat-icon {
        font-size: 24px;
        width: 24px;
        height: 24px;
      }
      .user-name {
        white-space: nowrap;
      }
      .version-label {
        font-size: 12px;
        padding: 4px 8px;
        background: rgba(255, 255, 255, 0.12);
        border-radius: var(--radius-pill);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #ffffff;
        white-space: nowrap;
      }

      .notification-panel {
        box-sizing: border-box;
        width: min(17rem, calc(100vw - 1rem));
        max-width: 100%;
        max-height: min(70vh, 32rem);
        overflow-y: auto;
        overflow-x: hidden;
        padding: var(--spacing-sm);
        color: var(--colour-text-primary);
        background: var(--colour-surface-elevated);
      }
      :host ::ng-deep .notification-menu.mat-mdc-menu-panel {
        min-width: 0 !important;
        max-width: min(19rem, calc(100vw - 1rem)) !important;
        overflow-x: hidden !important;
      }
      :host ::ng-deep .notification-menu .mat-mdc-menu-content {
        box-sizing: border-box;
        max-width: 100%;
        overflow-x: hidden;
        padding: 0;
      }
      .notification-panel__header,
      .notification-panel__title,
      .notification-item__title,
      .notification-item__actions {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }
      .notification-panel__header {
        justify-content: space-between;
        min-width: 0;
        padding-bottom: var(--spacing-sm);
        border-bottom: 1px solid var(--colour-border);
      }
      .notification-panel__title {
        min-width: 0;
      }
      .notification-panel__header > button {
        flex: 0 0 auto;
      }
      .notification-panel__filters {
        padding: var(--spacing-sm) 0;
      }
      .notification-item {
        box-sizing: border-box;
        min-width: 0;
        position: relative;
        margin-top: var(--spacing-sm);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
        cursor: pointer;
      }
      .notification-item:hover,
      .notification-item:focus-visible {
        border-color: var(--colour-primary);
      }
      .notification-item:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }
      .notification-item--unread {
        background: var(--colour-info-bg);
      }
      .notification-unread-dot {
        position: absolute;
        top: var(--spacing-sm);
        right: var(--spacing-sm);
        width: 0.625rem;
        height: 0.625rem;
        border-radius: 50%;
        background: var(--colour-primary);
      }
      .notification-item p {
        margin: var(--spacing-sm) 0;
        color: var(--colour-text-secondary);
        overflow-wrap: anywhere;
      }
      .notification-item__progress {
        font-size: 0.875rem;
      }
      .notification-item__delayed {
        color: var(--colour-warning-text) !important;
      }
      .notification-item__actions {
        justify-content: flex-end;
        flex-wrap: wrap;
        margin-top: var(--spacing-md);
      }
      .notification-panel__empty {
        margin: var(--spacing-md) 0 0;
        color: var(--colour-text-secondary);
      }
      .notification-bell {
        position: relative;
        overflow: visible;
      }
      .notification-count {
        position: absolute;
        top: 0;
        right: 0;
        min-width: 1.25rem;
        height: 1.25rem;
        padding-inline: 0.25rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border: 2px solid var(--colour-toolbar);
        border-radius: var(--radius-pill);
        background: #b91c1c;
        color: #ffffff;
        font-size: 0.6875rem;
        font-weight: 800;
        line-height: 1;
        transform: translate(25%, -20%);
        pointer-events: none;
      }

      @media (max-width: 767px) {
        mat-toolbar {
          padding-inline: 0.5rem;
        }
        .logo {
          padding: 8px 12px;
        }
      }

      /* Search History Dropdown - Google Style */
      .search-history-dropdown {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        right: 0;
        background: var(--colour-surface);
        border-radius: var(--radius-md);
        box-shadow: 0 18px 36px rgba(2, 6, 23, 0.28);
        border: 1px solid var(--colour-border);
        max-height: 320px;
        overflow-y: auto;
        z-index: 1000;
      }

      .search-history-header {
        padding: 12px 16px 8px 16px;
        border-bottom: 1px solid var(--colour-border);
      }

      .search-history-title {
        font-size: 14px;
        color: var(--colour-text-secondary);
        font-weight: 500;
      }

      .search-history-item {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        cursor: pointer;
        border-bottom: 1px solid var(--colour-border);
        transition: background-color 0.2s ease;
      }

      .search-history-item:hover {
        background-color: var(--colour-surface-muted);
      }

      .search-history-item:focus-within {
        background-color: var(--colour-surface-muted);
      }

      .search-history-item:last-child {
        border-bottom: none;
      }

      .history-icon {
        color: var(--colour-text-secondary);
        font-size: 20px;
        width: 20px;
        height: 20px;
        margin-right: 12px;
      }

      .history-text {
        flex: 1;
        font-size: 14px;
        color: var(--colour-text-primary);
        text-overflow: ellipsis;
        overflow: hidden;
        white-space: nowrap;
      }

      .search-history-dropdown .highlight-match {
        color: var(--colour-accent) !important;
        font-weight: 600 !important;
        background: var(--colour-surface-muted) !important;
        padding: 1px 2px !important;
        border-radius: 2px !important;
        display: inline !important;
      }

      .history-remove {
        background: none;
        border: none;
        color: var(--colour-text-secondary);
        cursor: pointer;
        padding: 4px;
        border-radius: var(--radius-sm);
        opacity: 0;
        transition:
          opacity 0.2s ease,
          background-color 0.2s ease;
      }

      .search-history-item:hover .history-remove {
        opacity: 1;
      }

      .search-history-item:focus-within .history-remove,
      .history-remove:focus-visible {
        opacity: 1;
      }

      .history-remove:hover {
        background-color: var(--colour-surface-muted);
        color: var(--colour-text-primary);
      }

      .history-remove:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
        background-color: var(--colour-surface-muted);
        color: var(--colour-text-primary);
      }

      .history-remove mat-icon {
        font-size: 16px;
        width: 16px;
        height: 16px;
      }

      .search-history-empty {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px 16px;
        color: var(--colour-text-secondary);
        font-size: 14px;
        gap: 8px;
      }

      .empty-icon {
        color: var(--colour-border);
        font-size: 24px;
        width: 24px;
        height: 24px;
      }

      /* Responsive adjustments */
      @media (max-width: 768px) {
        .search-form {
          max-width: none;
        }
        .search-history-dropdown {
          max-height: 240px;
        }
      }
    `,
  ],
})
export class TopBarComponent implements OnInit, OnDestroy {
  @ViewChild("notificationMenuTrigger")
  private notificationMenuTrigger!: MatMenuTrigger;
  protected readonly searchFilterOptions = [
    { key: "keywords", label: "Entry text", icon: "notes" },
    { key: "tags", label: "Tags", icon: "label" },
    { key: "people", label: "People", icon: "person" },
    { key: "date", label: "Dates", icon: "event" },
  ] as const;
  private readonly selectedSearchFilters = new Set<SearchFilterKey>(
    this.searchFilterOptions.map((option) => option.key),
  );
  private readonly breakpointObserver = inject(BreakpointObserver);
  private readonly isCompactViewport = signal(false);
  private readonly isMediumViewport = signal(false);

  readonly isCompact = computed(() => this.isCompactViewport());
  readonly isCompactSearchOpen = signal(false);
  readonly showUserName = computed(
    () => !this.isCompactViewport() && !this.isMediumViewport(),
  );
  readonly showVersionLabel = computed(() => !this.isCompactViewport());
  @Output() toggleSidenav = new EventEmitter<void>();
  private authService = inject(AuthService);
  private searchService = inject(SearchService);
  private router = inject(Router);
  private location = inject(Location);
  private fb = inject(FormBuilder);
  private sanitizer = inject(DomSanitizer);
  private readonly themeService = inject(ThemeService);
  private readonly importJobService = inject(ImportJobService);
  private destroy$ = new Subject<void>();

  // Search History Properties
  protected searchHistory: string[] = [];
  protected filteredSearchHistory: string[] = [];
  protected showSearchHistory = false;
  protected searchInputFocused = false;
  protected currentSearchQuery = "";

  userName$: Observable<string | null> = this.authService.currentUser$.pipe(
    map(
      (user) =>
        user?.display_name || user?.first_name || user?.username || null,
    ),
  );
  readonly currentUser$ = this.authService.currentUser$;

  versionLabel = APP_VERSION;
  readonly isDarkTheme = this.themeService.isDark;
  readonly importJob$ = this.importJobService.job$;
  readonly notifications$ = this.importJobService.notifications$;
  readonly showUnreadOnly = signal(false);

  // Track search loading state
  isSearching = false;

  searchForm = this.fb.group({
    query: [""],
  });

  constructor() {
    // Clear search when navigating away from entries
    this.router.events
      .pipe(
        filter(
          (event): event is NavigationEnd => event instanceof NavigationEnd,
        ),
        takeUntil(this.destroy$),
      )
      .subscribe((event) => {
        if (!event || !event.url) return;
        if (!event.url.includes("/entries")) {
          this.searchService.clear();
          this.searchForm.patchValue({ query: "" });
          this.selectAllSearchFilters();
          return;
        }

        this.applySearchRouteState(event.urlAfterRedirects);
      });
  }

  logout(): void {
    this.authService.logout();
  }

  toggleTheme(): void {
    this.themeService.toggleTheme();
  }

  openImportPage(notification: AppNotification): void {
    this.importJobService.markRead(notification.id);
    this.notificationMenuTrigger.closeMenu();
    void this.router.navigate(["/settings/import"]);
  }

  dismissImportNotification(notificationId: string): void {
    this.importJobService.dismiss(notificationId);
  }

  markNotificationRead(notificationId: string): void {
    this.importJobService.markRead(notificationId);
  }

  clearNotifications(): void {
    this.importJobService.clearCompleted();
  }

  getUnreadCount(notifications: AppNotification[]): number {
    return notifications.filter((notification) => notification.unread).length;
  }

  getUnreadBadgeLabel(notifications: AppNotification[]): string {
    const count = this.getUnreadCount(notifications);
    return count > 9 ? "9+" : String(count);
  }

  hasRunningImport(notifications: AppNotification[]): boolean {
    return notifications.some(
      (notification) =>
        notification.status === "queued" || notification.status === "running",
    );
  }

  getVisibleNotifications(
    notifications: AppNotification[],
  ): AppNotification[] {
    return this.showUnreadOnly()
      ? notifications.filter((notification) => notification.unread)
      : notifications;
  }

  filterResults(): void {
    const query = this.searchForm.value.query?.trim() || "";
    if (!query) return;

    this.isCompactSearchOpen.set(false);
    this.showSearchHistory = false;

    const currentPath = this.location.path() || "";
    const filters = this.getSearchFilterQueryParam();
    if (!currentPath.includes("/entries")) {
      // Navigate to entries with search query - let the route handler trigger search
      this.router.navigate(["/entries"], {
        queryParams: { search: query, filters },
      });
    } else {
      // Preserve list type/month context while replacing search-specific state.
      this.router.navigate(["/entries"], {
        queryParams: { search: query, filters },
        queryParamsHandling: "merge",
      });
    }
  }

  protected toggleSearchFilter(filterKey: SearchFilterKey): void {
    if (this.selectedSearchFilters.has(filterKey)) {
      if (this.selectedSearchFilters.size > 1) {
        this.selectedSearchFilters.delete(filterKey);
      }
      return;
    }

    this.selectedSearchFilters.add(filterKey);
  }

  protected selectAllSearchFilters(): void {
    for (const option of this.searchFilterOptions) {
      this.selectedSearchFilters.add(option.key);
    }
  }

  protected isSearchFilterSelected(filterKey: SearchFilterKey): boolean {
    return this.selectedSearchFilters.has(filterKey);
  }

  protected areAllSearchFiltersSelected(): boolean {
    return this.selectedSearchFilters.size === this.searchFilterOptions.length;
  }

  protected getSearchFilterSummary(): string {
    if (this.areAllSearchFiltersSelected()) {
      return "Searching all fields";
    }

    const selectedLabels = this.searchFilterOptions
      .filter((option) => this.selectedSearchFilters.has(option.key))
      .map((option) => option.label.toLowerCase());
    return `Searching ${selectedLabels.join(", ")}`;
  }

  private getSearchFilterQueryParam(): string | null {
    if (this.areAllSearchFiltersSelected()) {
      return null;
    }

    return this.searchFilterOptions
      .filter((option) => this.selectedSearchFilters.has(option.key))
      .map((option) => option.key)
      .join(",");
  }

  goHome(): void {
    this.router.navigate(["/entries"]).then(() => {
      this.searchService.clear();
      this.searchForm.patchValue({ query: "" });
    });
  }

  // Search History Methods

  ngOnInit(): void {
    this.applySearchRouteState(this.location.path() || "/entries");

    this.breakpointObserver
      .observe(["(max-width: 767px)", "(min-width: 768px) and (max-width: 1023px)"])
      .pipe(takeUntil(this.destroy$))
      .subscribe((state) => {
        this.isCompactViewport.set(state.breakpoints["(max-width: 767px)"] === true);
        this.isMediumViewport.set(
          state.breakpoints["(min-width: 768px) and (max-width: 1023px)"] === true,
        );

        if (!this.isCompactViewport()) {
          this.isCompactSearchOpen.set(false);
        }
      });

    // Subscribe to search history changes
    this.searchService.searchHistory$
      .pipe(takeUntil(this.destroy$))
      .subscribe((history) => {
        this.searchHistory = history;
        this.updateFilteredHistory();
      });

    // Subscribe to search state changes to clear input when search is cleared
    this.searchService.results$
      .pipe(takeUntil(this.destroy$))
      .subscribe((searchState) => {
        // Clear the search input when search is not active (user navigated away from search results)
        if (!searchState.active && this.searchForm.get("query")?.value) {
          this.searchForm.patchValue({ query: "" });
          this.currentSearchQuery = "";
          this.updateFilteredHistory();
        }
      });
  }

  openCompactSearch(): void {
    this.isCompactSearchOpen.set(true);
    this.showSearchHistory = false;
    queueMicrotask(() => {
      const input = document.querySelector<HTMLInputElement>(
        ".search-wrapper .search-input",
      );
      input?.focus();
      input?.select();
    });
  }

  closeCompactSearch(): void {
    this.isCompactSearchOpen.set(false);
    this.showSearchHistory = false;
  }

  onSearchInputFocus(): void {
    this.searchInputFocused = true;
    this.currentSearchQuery = this.searchForm.get("query")?.value || "";
    this.updateFilteredHistory();
    this.showSearchHistory = true;
  }

  onSearchInputBlur(): void {
    // Delay hiding to allow for click events
    setTimeout(() => {
      this.searchInputFocused = false;
      this.showSearchHistory = false;
    }, 200);
  }

  onSearchInputChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    const value = input.value.trim();

    this.currentSearchQuery = value;
    this.updateFilteredHistory();

    // Show dropdown based on filtering results or empty query with focus
    this.showSearchHistory =
      this.searchInputFocused &&
      (this.filteredSearchHistory.length > 0 || value.length === 0);
  }

  private updateFilteredHistory(): void {
    if (!this.currentSearchQuery) {
      // Show all history when query is empty
      this.filteredSearchHistory = [...this.searchHistory];
    } else {
      // Filter history items that start with the current query (case-insensitive)
      this.filteredSearchHistory = this.searchHistory.filter((item) =>
        item.toLowerCase().startsWith(this.currentSearchQuery.toLowerCase()),
      );
    }
  }

  private applySearchRouteState(url: string): void {
    const queryParams = this.router.parseUrl(url).queryParams;
    const routeQuery = String(queryParams["search"] || "");
    if (routeQuery !== (this.searchForm.get("query")?.value || "")) {
      this.searchForm.patchValue({ query: routeQuery });
      this.currentSearchQuery = routeQuery;
    }

    const routeFilters = String(queryParams["filters"] || "");
    if (!routeFilters) {
      this.selectAllSearchFilters();
      return;
    }

    const validFilters = new Set<SearchFilterKey>(
      this.searchFilterOptions.map((option) => option.key),
    );
    const selected = routeFilters
      .split(",")
      .map((filter) => filter.trim() as SearchFilterKey)
      .filter((filter) => validFilters.has(filter));

    if (selected.length === 0) {
      this.selectAllSearchFilters();
      return;
    }

    this.selectedSearchFilters.clear();
    for (const filter of selected) {
      this.selectedSearchFilters.add(filter);
    }
  }

  highlightMatch(historyItem: string, query: string): SafeHtml {
    if (!query) {
      return this.sanitizer.bypassSecurityTrustHtml(historyItem);
    }

    // Only highlight at the beginning of the text (matching our filtering logic)
    const regex = new RegExp(`^(${this.escapeRegExp(query)})`, "i");
    const highlighted = historyItem.replace(
      regex,
      '<span class="highlight-match">$1</span>',
    );

    return this.sanitizer.bypassSecurityTrustHtml(highlighted);
  }

  private escapeRegExp(text: string): string {
    return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  selectHistoryItem(historyItem: string): void {
    // Update form and perform search
    this.searchForm.patchValue({ query: historyItem });
    this.currentSearchQuery = historyItem;
    this.showSearchHistory = false;
    this.filterResults();
  }

  removeHistoryItem(historyItem: string, event: Event): void {
    event.stopPropagation(); // Prevent triggering selectHistoryItem
    this.searchService.removeFromHistory(historyItem);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
