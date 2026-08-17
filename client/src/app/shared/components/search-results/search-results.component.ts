import {
  Component,
  inject,
  ElementRef,
  OnInit,
  OnDestroy,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import {
  SearchService,
  SearchResult,
  SearchState,
} from "../../../core/services/search.service";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatCheckboxModule } from "@angular/material/checkbox";
import {
  trigger,
  state,
  style,
  transition,
  animate,
} from "@angular/animations";
import { DomSanitizer, SafeHtml } from "@angular/platform-browser";
import { Subscription } from "rxjs";
import { EntriesService } from "../../../core/services/entries.service";
import { AppDialogService } from "../../../core/services/app-dialog.service";

@Component({
  selector: "app-search-results",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatPaginatorModule,
    MatCheckboxModule,
  ],
  animations: [
    trigger("slideInOut", [
      transition(":enter", [
        style({ height: "0", opacity: "0", transform: "translateY(-10px)" }),
        animate(
          "300ms cubic-bezier(0.4, 0.0, 0.2, 1)",
          style({ height: "*", opacity: "1", transform: "translateY(0)" }),
        ),
      ]),
      transition(":leave", [
        animate(
          "300ms cubic-bezier(0.4, 0.0, 0.2, 1)",
          style({ height: "0", opacity: "0", transform: "translateY(-10px)" }),
        ),
      ]),
    ]),
  ],
  template: `
    <div
      *ngIf="results$ | async as searchState"
      class="search-results"
      data-testid="search-results"
      (click)="closeExpandedIfClickingAway($event)"
    >
      <div *ngIf="searchState.active" class="search-header">
        <h2
          *ngIf="
            !searchState.loading &&
            !searchState.error &&
            searchState.results.length > 0
          "
        >
          {{ getResultCountMessage(searchState) }}
        </h2>
        <h2 *ngIf="searchState.loading">
          Searching records for "{{ searchState.query }}" in
          {{ searchState.filters_display }}...
        </h2>
      </div>

      <!-- Enhanced Loading State -->
      <div *ngIf="searchState.loading" class="loading-container">
        <!-- Skeleton Loading Cards -->
        <div class="skeleton-grid">
          <div *ngFor="let i of [1, 2, 3, 4, 5, 6]" class="skeleton-card">
            <div class="skeleton-header">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-title-group">
                <div class="skeleton-title"></div>
                <div class="skeleton-subtitle"></div>
              </div>
            </div>
            <div class="skeleton-content">
              <div class="skeleton-image"></div>
              <div class="skeleton-text-lines">
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
                <div class="skeleton-line medium"></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Centered Loading Message (positioned like no-results card) -->
        <div class="loading-message-overlay">
          <mat-card class="loading-message-card">
            <mat-card-content class="loading-message-content">
              <mat-progress-spinner
                diameter="48"
                mode="indeterminate"
                color="primary"
              ></mat-progress-spinner>
              <p class="loading-text">Searching your entries...</p>
            </mat-card-content>
          </mat-card>
        </div>
      </div>

      <!-- Enhanced Error Panel -->
      <mat-card *ngIf="searchState.error" class="error-card">
        <mat-card-content class="error-content">
          <div class="error-icon">
            <mat-icon>error_outline</mat-icon>
          </div>
          <h3>Search failed</h3>
          <p class="error-message">{{ getErrorMessage(searchState.error) }}</p>

          <!-- Error-specific suggestions -->
          <div
            class="error-suggestions"
            *ngIf="getErrorSuggestions(searchState.error).length > 0"
          >
            <h4>Try these steps:</h4>
            <ul>
              <li
                *ngFor="
                  let suggestion of getErrorSuggestions(searchState.error)
                "
              >
                {{ suggestion }}
              </li>
            </ul>
          </div>

          <div class="error-actions">
            <button
              mat-raised-button
              color="primary"
              (click)="retry(searchState)"
              [disabled]="isRetrying"
            >
              <mat-progress-spinner
                *ngIf="isRetrying"
                diameter="20"
                mode="indeterminate"
              ></mat-progress-spinner>
              <span *ngIf="!isRetrying">Try Again</span>
              <span *ngIf="isRetrying">Retrying...</span>
            </button>
            <button mat-button (click)="searchService.clear()">Cancel</button>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- No Results State -->
      <mat-card
        *ngIf="
          !searchState.loading &&
          !searchState.error &&
          searchState.active &&
          searchState.results.length === 0
        "
        class="no-results-card"
      >
        <mat-card-content class="no-results-content">
          <div class="no-results-icon">
            <mat-icon>search_off</mat-icon>
          </div>
          <h3>No results found</h3>
          <p class="no-results-message">
            We couldn't find any records matching "<strong>{{
              searchState.query
            }}</strong
            >" in {{ searchState.filters_display }}.
          </p>

          <!-- Smart Suggestions -->
          <div
            class="search-suggestions"
            *ngIf="getSearchSuggestions(searchState.query).length > 0"
          >
            <h4>Try these suggestions:</h4>
            <ul>
              <li
                *ngFor="
                  let suggestion of getSearchSuggestions(searchState.query)
                "
              >
                {{ suggestion }}
              </li>
            </ul>
          </div>

          <div class="no-results-actions">
            <button
              mat-raised-button
              color="primary"
              (click)="browseAllEntries()"
            >
              Browse All Entries
            </button>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- Top Pagination (matching entries list exactly) -->
      <div
        class="selection-toolbar"
        *ngIf="!searchState.loading && hasDeletableResults(searchState)"
        role="toolbar"
        aria-label="Select and delete matching entries"
      >
        <button mat-stroked-button type="button" (click)="toggleCurrentPageSelection()">
          <mat-icon>{{ isCurrentPageSelected() ? "deselect" : "select_all" }}</mat-icon>
          <span>{{ isCurrentPageSelected() ? "Clear this page" : "Select this page" }}</span>
        </button>
        <span class="selection-count" aria-live="polite">
          {{ selectedEntries.size }} selected
        </span>
        <button
          mat-raised-button
          class="delete-selected-button"
          type="button"
          [disabled]="selectedEntries.size === 0 || deletingSelected"
          (click)="deleteSelected(searchState)"
        >
          <mat-icon>delete</mat-icon>
          <span>{{ deletingSelected ? "Deleting…" : "Delete selected" }}</span>
        </button>
      </div>

      <div
        class="pagination-container"
        *ngIf="
          !searchState.loading &&
          !searchState.error &&
          searchState.active &&
          searchState.results.length > 0
        "
      >
        <mat-paginator
          [length]="searchState.results.length"
          [pageSize]="pageSize"
          [pageSizeOptions]="[8, 16, 32]"
          [pageIndex]="currentPage"
          [showFirstLastButtons]="true"
          (page)="onPageChange($event)"
          aria-label="Select page"
          data-testid="search-results-top-paginator"
        >
        </mat-paginator>
      </div>

      <div
        class="results-grid"
        *ngIf="
          !searchState.loading &&
          !searchState.error &&
          searchState.active &&
          searchState.results.length > 0
        "
      >
        <div
          *ngFor="let result of paginatedResults"
          class="result-container"
          [attr.data-card-id]="selectionKey(result)"
        >
          <mat-checkbox
            *ngIf="isDeletableResult(result)"
            class="result-selector"
            [checked]="isSelected(result)"
            (click)="$event.stopPropagation()"
            (change)="setSelected(result, $event.checked)"
            [aria-label]="'Select ' + result.title"
          ></mat-checkbox>
          <!-- Main Card View (Fixed Size) -->
          <mat-card
            class="entry-card"
            role="button"
            tabindex="0"
            [attr.aria-expanded]="isExpanded(result)"
            [attr.aria-label]="'Review ' + getResultTypeLabel(result) + ' search result ' + result.title"
            data-testid="search-result-card"
            (click)="toggleExpand(result); $event.stopPropagation()"
            (keydown.enter)="toggleExpand(result); $event.stopPropagation()"
            (keydown.space)="$event.preventDefault(); toggleExpand(result); $event.stopPropagation()"
          >
            <mat-card-header>
              <mat-icon mat-card-avatar>
                {{ getResultIcon(result) }}
              </mat-icon>
              <mat-card-title
                [innerHTML]="getDisplayTitle(result)"
              ></mat-card-title>
              <mat-card-subtitle>{{
                (result.entry_date | date: "dd/MM/yyyy") ||
                  result.entry_date_display
              }}</mat-card-subtitle>
            </mat-card-header>

            <mat-card-content>
              <div class="entry-image-placeholder">
                <mat-icon>{{ getResultPlaceholderIcon(result) }}</mat-icon>
              </div>
              <div class="match-snippets">
                <p
                  class="snippet"
                  [innerHTML]="getSafeHtml(getBestSnippet(result))"
                ></p>
              </div>
            </mat-card-content>
          </mat-card>

          <!-- Expanded Details Card (Separate Card Below) -->
          <div *ngIf="isExpanded(result)" class="expanded-connector">
            <!-- Visual connector arrow -->
            <div class="connector-arrow">
              <mat-icon>keyboard_arrow_down</mat-icon>
            </div>
          </div>

          <mat-card
            *ngIf="isExpanded(result)"
            class="expanded-details-card"
            [@slideInOut]
            (click)="$event.stopPropagation()"
            data-testid="search-result-detail"
          >
            <div class="expanded-header">
              <div class="expanded-actions">
                <a
                  [routerLink]="getResultLink(result)"
                  [queryParams]="getResultQueryParams(result, searchState)"
                  mat-flat-button
                  class="search-result-primary-action"
                >
                  <mat-icon>open_in_new</mat-icon>
                  <span>View {{ getResultTypeLabel(result) }}</span>
                </a>
                <button
                  mat-icon-button
                  class="close-btn"
                  [attr.aria-label]="'Close expanded search result ' + result.title"
                  (click)="closeExpanded($event)"
                >
                  <mat-icon>close</mat-icon>
                </button>
              </div>
            </div>

            <div class="expanded-content">
              <!-- Title Row -->
              <div class="detail-row">
                <mat-icon class="detail-icon">bookmark</mat-icon>
                <span
                  class="detail-text"
                  [innerHTML]="getDisplayTitle(result)"
                ></span>
              </div>

              <!-- Date Row -->
              <div class="detail-row">
                <mat-icon class="detail-icon">calendar_today</mat-icon>
                <span class="detail-text">{{
                  (result.entry_date | date: "dd/MM/yyyy") ||
                    result.entry_date_display
                }}</span>
              </div>

              <!-- Tags Row (if has matching tags) -->
              <div class="detail-row" *ngIf="result.matches.tags">
                <mat-icon class="detail-icon">local_offer</mat-icon>
                <span
                  class="detail-text"
                  [innerHTML]="getSafeHtml(result.matches.tags)"
                ></span>
              </div>

              <!-- Body/Content Row (if has matching body) -->
              <div class="detail-row" *ngIf="result.matches.body">
                <mat-icon class="detail-icon">edit</mat-icon>
                <span
                  class="detail-text"
                  [innerHTML]="getSafeHtml(result.matches.body)"
                ></span>
              </div>

              <!-- AI Response Row (if has matching AI response) -->
              <div class="detail-row" *ngIf="result.matches.ai">
                <mat-icon class="detail-icon">psychology</mat-icon>
                <span
                  class="detail-text"
                  [innerHTML]="getSafeHtml(result.matches.ai)"
                ></span>
              </div>
            </div>
          </mat-card>
        </div>
      </div>

      <!-- Bottom Pagination (matching entries list exactly) -->
      <div
        class="pagination-container"
        *ngIf="
          !searchState.loading &&
          !searchState.error &&
          searchState.active &&
          searchState.results.length > 0
        "
      >
        <mat-paginator
          [length]="searchState.results.length"
          [pageSize]="pageSize"
          [pageSizeOptions]="[8, 16, 32]"
          [pageIndex]="currentPage"
          [showFirstLastButtons]="true"
          (page)="onPageChange($event)"
          aria-label="Select page"
          data-testid="search-results-bottom-paginator"
        >
        </mat-paginator>
      </div>
    </div>
  `,
  styles: [
    `
      .search-results {
        padding: var(--spacing-sm) 0;
      }

      .loading-container {
        position: relative;
        min-height: 400px;
      }

      /* Centered Loading Message Card - aligned with first row of results */
      .loading-message-overlay {
        position: absolute;
        top: 1rem; /* Align with skeleton-grid padding */
        left: 0;
        right: 0;
        display: flex;
        align-items: flex-start;
        justify-content: center;
        z-index: 10;
        pointer-events: none; /* Allow interaction with skeleton cards underneath */
        padding-top: 2rem; /* Additional spacing to align with first card row */
      }

      .loading-message-card {
        background: var(--colour-surface-elevated);
        backdrop-filter: blur(8px);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        box-shadow: 0 8px 32px var(--colour-shadow-medium);
        max-width: 400px;
        pointer-events: auto;
      }

      .loading-message-content {
        padding: 2rem;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 1rem;
        text-align: center;
      }

      .loading-text {
        margin: 0;
        color: var(--colour-text-secondary);
        font-size: 0.95rem;
        font-weight: 500;
      }

      /* Skeleton Loading Cards */
      .skeleton-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: 16px;
        padding: 1rem;
        animation: fadeInSkeletons 0.5s ease-in-out;
      }

      .skeleton-card {
        background: var(--colour-surface-elevated);
        border-radius: var(--radius-lg);
        padding: 16px;
        box-shadow: 0 2px 8px var(--colour-shadow-soft);
        /* Match actual entry-card dimensions exactly: 303 x 350 */
        height: 350px;
        width: 303px;
        min-width: 303px;
        max-width: 303px;
        display: flex;
        flex-direction: column;
        opacity: 0.8;
        border: 1px solid var(--colour-border);
      }

      .skeleton-header {
        display: flex;
        align-items: center;
        margin-bottom: 16px;
        gap: 12px;
      }

      .skeleton-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(
          90deg,
          var(--colour-surface-muted) 25%,
          var(--colour-surface-strong) 50%,
          var(--colour-surface-muted) 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
      }

      .skeleton-title-group {
        flex: 1;
      }

      .skeleton-title {
        height: 16px;
        background: linear-gradient(
          90deg,
          var(--colour-surface-muted) 25%,
          var(--colour-surface-strong) 50%,
          var(--colour-surface-muted) 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
        margin-bottom: 8px;
        width: 70%;
      }

      .skeleton-subtitle {
        height: 12px;
        background: linear-gradient(
          90deg,
          var(--colour-surface-muted) 25%,
          var(--colour-surface-strong) 50%,
          var(--colour-surface-muted) 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
        width: 50%;
      }

      .skeleton-content {
        flex: 1;
        display: flex;
        flex-direction: column;
      }

      .skeleton-image {
        height: 120px; /* Match entry-image-placeholder height exactly */
        background: linear-gradient(
          90deg,
          var(--colour-surface-muted) 25%,
          var(--colour-surface-strong) 50%,
          var(--colour-surface-muted) 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 8px;
        margin-bottom: 12px; /* Match entry-image-placeholder margin-bottom */
        flex-shrink: 0; /* Match entry-image-placeholder behavior */
      }

      .skeleton-text-lines {
        flex: 1; /* Match match-snippets flex behavior */
        display: flex;
        flex-direction: column;
        gap: 8px;
        max-height: 100px; /* Match match-snippets max-height */
        overflow: hidden;
        padding: 8px 0; /* Match match-snippets padding */
      }

      .skeleton-line {
        height: 14px;
        background: linear-gradient(
          90deg,
          var(--colour-surface-muted) 25%,
          var(--colour-surface-strong) 50%,
          var(--colour-surface-muted) 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 4px;
        width: 100%;
      }

      .skeleton-line.short {
        width: 60%;
      }

      .skeleton-line.medium {
        width: 80%;
      }

      @keyframes shimmer {
        0% {
          background-position: -200% 0;
        }
        100% {
          background-position: 200% 0;
        }
      }

      @keyframes fadeInSkeletons {
        from {
          opacity: 0;
          transform: translateY(20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      .error-card {
        margin: 2rem auto;
        max-width: 500px;
        background: var(--colour-danger-bg);
        border: 1px solid var(--colour-danger-text);
        color: var(--colour-danger-text);
      }

      .error-content {
        padding: 2rem;
        text-align: center;
      }

      .error-icon {
        margin-bottom: 1rem;
      }

      .error-icon mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--colour-danger-text);
      }

      .error-content h3 {
        margin: 0 0 1rem;
        font-size: 1.25rem;
        font-weight: 500;
        color: var(--colour-danger-text);
      }

      .error-message {
        margin: 0 0 1.5rem;
        color: var(--colour-danger-text);
        line-height: 1.5;
      }

      .error-suggestions {
        margin: 1.5rem 0;
        text-align: left;
        background: var(--colour-danger-bg);
        border-radius: 8px;
        padding: 1rem;
      }

      .error-suggestions h4 {
        margin: 0 0 0.5rem;
        font-size: 0.9rem;
        font-weight: 500;
        color: var(--colour-danger-text);
      }

      .error-suggestions ul {
        margin: 0;
        padding-left: 1.2rem;
        color: var(--colour-danger-text);
      }

      .error-suggestions li {
        margin-bottom: 0.25rem;
        font-size: 0.85rem;
      }

      .error-actions {
        display: flex;
        gap: 1rem;
        justify-content: center;
        flex-wrap: wrap;
      }

      .error-actions button {
        min-width: 120px;
      }

      .no-results-card {
        margin: 2rem auto;
        max-width: 500px;
        text-align: center;
        background: var(--colour-surface-elevated);
        border: 1px solid var(--colour-border);
      }

      .no-results-content {
        padding: 3rem 2rem 2rem;
      }

      .no-results-icon {
        margin-bottom: 1.5rem;
      }

      .no-results-icon mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        color: var(--colour-text-secondary);
      }

      .no-results-content h3 {
        margin: 0 0 1rem;
        font-size: 1.5rem;
        font-weight: 500;
        color: var(--colour-text-primary);
      }

      .no-results-message {
        margin: 0 0 2rem;
        color: var(--colour-text-secondary);
        line-height: 1.5;
      }

      .search-suggestions {
        margin: 2rem 0;
        text-align: left;
        background: var(--colour-surface-muted);
        border-radius: 8px;
        padding: 1.5rem;
      }

      .search-suggestions h4 {
        margin: 0 0 1rem;
        font-size: 1rem;
        font-weight: 500;
        color: var(--colour-text-primary);
      }

      .search-suggestions ul {
        margin: 0;
        padding-left: 1.2rem;
        color: var(--colour-text-secondary);
      }

      .search-suggestions li {
        margin-bottom: 0.5rem;
      }

      .no-results-actions {
        display: flex;
        gap: 1rem;
        justify-content: center;
        flex-wrap: wrap;
      }

      .search-header {
        margin: 0 0 var(--spacing-md);
      }

      .search-header h2 {
        margin: 0;
        font-size: clamp(1.45rem, 2.2vw, 2rem);
        font-weight: 800;
        letter-spacing: -0.02em;
        color: var(--colour-text-primary);
      }

      .results-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(min(18.75rem, 100%), 21.875rem));
        justify-content: center;
        gap: var(--spacing-md);
        padding: var(--spacing-md) 0;
        position: relative; /* Allow expanded cards to position relative to grid */
      }
      .selection-toolbar {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        margin-block: var(--spacing-sm) var(--spacing-md);
        padding: var(--spacing-sm) var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
      }
      .selection-toolbar button {
        border-radius: var(--radius-pill);
      }
      .selection-toolbar button .mat-icon {
        margin-right: 0.45rem;
      }
      .selection-count {
        color: var(--colour-text-secondary);
        font-weight: 700;
      }
      .delete-selected-button {
        margin-left: auto;
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
        border-radius: var(--radius-pill);
      }
      .delete-selected-button:disabled {
        background: var(--colour-surface-muted);
        color: var(--colour-text-secondary);
        opacity: 0.62;
      }
      .result-container {
        position: relative;
      }
      .result-selector {
        position: absolute;
        z-index: 3;
        top: var(--spacing-sm);
        right: var(--spacing-sm);
      }

      .result-container {
        display: flex;
        flex-direction: column;
        gap: 8px;
        position: relative; /* Allow for absolute positioning of expanded cards */
      }

      .result-container:has(.expanded-details-card) {
        /* Ensure expanded cards have proper stacking context */
        z-index: 1;
        /* Add extra bottom margin to prevent other cards from creeping up */
        margin-bottom: var(--spacing-sm);
      }

      /* Visual connector between main card and expanded card */
      .expanded-connector {
        display: flex;
        justify-content: center;
        padding-left: 0;
        margin: 4px 0;
        z-index: 15;
        position: relative;
      }

      .connector-arrow {
        background-color: var(--colour-primary);
        color: var(--colour-on-primary);
        border-radius: 50%;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 2px 8px var(--colour-primary-shadow);
      }

      .connector-arrow mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      .entry-card {
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        transform: translateZ(0);
        width: 100%;
        min-width: 300px;
        max-width: 350px;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-elevated);
        overflow: hidden;
      }

      /* When expanded, make the expanded card appear below and span wider */
      .expanded-details-card {
        background-color: var(--colour-surface-elevated);
        border-left: 4px solid var(--colour-primary);
        overflow: hidden;
        width: 100%;
        max-width: 100%;
        margin: 0; /* Remove default margin since we have connector spacing */
        transform: none;
        /* Ensure it appears above other content */
        z-index: 20;
        box-shadow: 0 4px 20px var(--colour-shadow-medium);
        border-radius: var(--radius-lg);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        /* Position relative to maintain document flow */
        position: relative;
      }

      /* Make sure expanded cards push down subsequent content more */
      .result-container:has(.expanded-details-card) ~ .result-container {
        margin-top: 0;
      }

      /* Ensure other cards don't creep into expanded area */
      .result-container:has(.expanded-details-card) {
        /* Create a clear boundary around expanded content */
        padding-bottom: 16px;
        border-bottom: 1px solid transparent; /* Invisible spacer */
      }

      /* Ensure search result cards also have consistent heights */
      .entry-card {
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        transform: translateZ(0);
        width: 100%;
        min-width: 300px;
        max-width: 350px;
        /* Force consistent height for search result cards too */
        height: 420px;
        display: flex;
        flex-direction: column;
      }

      .entry-card .mat-mdc-card-header {
        position: relative;
        align-items: flex-start;
        min-height: 4.8rem;
        padding: 1rem 2.6rem 0.35rem 1rem;
      }

      .entry-card .mat-mdc-card-avatar {
        flex: 0 0 2rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 2rem;
        height: 2rem;
        margin: 0.05rem 0.75rem 0 0;
        border-radius: 50%;
        background: var(--colour-surface-muted);
        color: var(--colour-primary);
      }
      .entry-card .mat-mdc-card-avatar.mat-icon {
        font-size: 1.25rem;
        line-height: 1;
      }
      .entry-card .mat-mdc-card-title {
        display: -webkit-box;
        overflow: hidden;
        line-height: 1.3;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        min-height: 2.6em;
      }
      .entry-card .mat-mdc-card-subtitle {
        color: var(--colour-text-secondary);
        font-weight: 700;
      }

      /* Highlight the selected/expanded card */
      .result-container:has(.expanded-details-card) .entry-card {
        border: 2px solid var(--colour-primary);
        box-shadow: 0 4px 20px var(--colour-primary-shadow);
      }

      /* Ensure search result card content fills properly */
      .entry-card .mat-mdc-card-content {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 0.8rem;
        overflow: hidden; /* Prevent content overflow */
      }

      .entry-card:hover {
        box-shadow: 0 4px 20px var(--colour-shadow-soft);
        transform: translateY(-2px);
      }

      .entry-image-placeholder {
        height: 132px;
        background: linear-gradient(
          180deg,
          var(--colour-surface-muted) 0%,
          var(--colour-surface-strong) 100%
        );
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: var(--radius-md);
        margin-bottom: 0;
        flex-shrink: 0; /* Don't shrink, maintain fixed height */

        mat-icon {
          font-size: 48px;
          width: 48px;
          height: 48px;
          color: var(--colour-text-secondary);
        }
      }
      .match-snippets {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        overflow: hidden; /* Prevent overflow from container */
        flex: 1; /* Take remaining space after image placeholder */
        max-height: none;
        padding: 0;
      }

      .snippet {
        margin: 0;
        font-size: 0.95rem;
        color: var(--colour-text-secondary);
        line-height: 1.5;
        /* Text truncation for long snippets */
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 4; /* Increased to 4 lines since we only show one snippet */
        -webkit-box-orient: vertical;
        word-break: break-word; /* Handle long words */

        ::ng-deep mark {
          background: none;
          color: var(--colour-danger-text);
          font-weight: 500;
        }
      }

      /* Server may wrap matches in <span class="match">..</span> or <mark>..</mark> */
      ::ng-deep .match {
        color: var(--colour-danger-text);
        font-weight: 500;
      }

      .expanded-header {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid var(--colour-border);
      }

      .expanded-content {
        padding: 16px;
      }

      .detail-row {
        display: flex;
        align-items: flex-start;
        margin-bottom: 16px;
        padding: 8px 0;
        transition: background-color 0.2s ease;
      }

      .detail-row:last-child {
        margin-bottom: 0;
      }

      .detail-row:hover {
        background-color: var(--colour-info-bg);
        border-radius: 8px;
        margin: 0 -8px 16px -8px;
        padding: 8px;
      }

      .detail-icon {
        flex-shrink: 0;
        width: 24px;
        height: 24px;
        margin-right: 16px;
        color: var(--colour-text-secondary);
        font-size: 20px !important;
      }

      .detail-text {
        flex: 1;
        font-size: 0.9rem;
        line-height: 1.5;
        color: var(--colour-text-secondary);
        word-wrap: break-word;
      }

      .expanded-actions {
        display: flex;
        gap: var(--spacing-xs);
        align-items: center;
      }

      .search-result-primary-action {
        border-radius: var(--radius-pill);
        background: var(--colour-primary);
        color: var(--colour-on-primary);
        min-height: 2.75rem;
      }

      .search-result-primary-action .mat-icon {
        margin-right: 0.45rem;
      }

      .close-btn {
        color: var(--colour-text-secondary);
        transition: color 0.2s ease;
      }

      .close-btn:hover {
        color: var(--colour-text-primary);
      }

      /* Pagination Styles - matching entries list exactly */
      .pagination-container {
        display: flex;
        justify-content: center;
        padding: var(--spacing-xs);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
        margin-inline: auto;
        max-width: min(68rem, 100%);
      }

      .pagination-container:first-of-type {
        margin-bottom: 1rem;
      }

      .pagination-container:last-of-type {
        margin-top: 1rem;
      }

      .pagination-container mat-paginator {
        background: transparent;
      }

      /* Responsive pagination */
      @media (max-width: 768px) {
        .pagination-container {
          padding: 0.75rem 0;
        }
      }

      :host-context(html[data-theme="dark"]) .search-results {
        color: var(--colour-text-primary);
      }

      :host-context(html[data-theme="dark"]) .search-header h2 {
        color: var(--colour-text-primary);
      }

      :host-context(html[data-theme="dark"]) .loading-message-card,
      :host-context(html[data-theme="dark"]) .skeleton-card,
      :host-context(html[data-theme="dark"]) .no-results-card,
      :host-context(html[data-theme="dark"]) .expanded-details-card {
        background: linear-gradient(
          180deg,
          var(--colour-surface-elevated) 0%,
          var(--colour-surface) 100%
        );
        border-color: var(--colour-border);
        color: var(--colour-text-primary);
      }

      :host-context(html[data-theme="dark"]) .loading-message-card {
        box-shadow: 0 18px 36px var(--colour-shadow-medium);
      }

      :host-context(html[data-theme="dark"]) .loading-text,
      :host-context(html[data-theme="dark"]) .no-results-message,
      :host-context(html[data-theme="dark"]) .search-suggestions ul,
      :host-context(html[data-theme="dark"]) .detail-icon,
      :host-context(html[data-theme="dark"]) .detail-text,
      :host-context(html[data-theme="dark"]) .snippet,
      :host-context(html[data-theme="dark"]) .close-btn {
        color: var(--colour-text-secondary);
      }

      :host-context(html[data-theme="dark"]) .search-suggestions,
      :host-context(html[data-theme="dark"]) .error-suggestions {
        background: var(--colour-surface-muted);
        border: 1px solid var(--colour-border);
      }

      :host-context(html[data-theme="dark"]) .no-results-content h3,
      :host-context(html[data-theme="dark"]) .search-suggestions h4 {
        color: var(--colour-text-primary);
      }

      :host-context(html[data-theme="dark"]) .error-card {
        background: var(--colour-danger-bg);
        border-color: var(--colour-danger-text);
        color: var(--colour-danger-text);
      }

      :host-context(html[data-theme="dark"]) .error-content h3,
      :host-context(html[data-theme="dark"]) .error-message,
      :host-context(html[data-theme="dark"]) .error-suggestions h4,
      :host-context(html[data-theme="dark"]) .error-suggestions ul,
      :host-context(html[data-theme="dark"]) .error-icon mat-icon {
        color: var(--colour-danger-text);
      }

      :host-context(html[data-theme="dark"]) .connector-arrow {
        background: var(--colour-primary);
        color: var(--colour-on-primary);
        box-shadow: 0 8px 18px var(--colour-shadow-strong);
      }

      :host-context(html[data-theme="dark"]) .expanded-details-card {
        border-left-color: var(--colour-primary);
        box-shadow: 0 20px 40px var(--colour-shadow-medium);
      }

      :host-context(html[data-theme="dark"]) .result-container:has(.expanded-details-card) .entry-card {
        border-color: var(--colour-primary);
        box-shadow: 0 16px 32px var(--colour-shadow-medium);
      }

      :host-context(html[data-theme="dark"]) .entry-card:hover {
        box-shadow: 0 16px 28px var(--colour-shadow-soft);
      }

      :host-context(html[data-theme="dark"]) .entry-image-placeholder {
        background: linear-gradient(
          180deg,
          var(--colour-surface-strong) 0%,
          var(--colour-surface-muted) 100%
        );
      }

      :host-context(html[data-theme="dark"]) .entry-image-placeholder mat-icon {
        color: var(--colour-text-secondary);
      }

      :host-context(html[data-theme="dark"]) .detail-row:hover {
        background-color: var(--colour-info-bg);
      }

      :host-context(html[data-theme="dark"]) .expanded-header {
        border-bottom-color: var(--colour-border);
      }

      :host-context(html[data-theme="dark"]) .pagination-container {
        background: color-mix(
          in srgb,
          var(--colour-surface-muted) 78%,
          var(--colour-background)
        );
        border-color: var(--colour-border);
      }

      :host-context(html[data-theme="dark"]) .skeleton-avatar,
      :host-context(html[data-theme="dark"]) .skeleton-title,
      :host-context(html[data-theme="dark"]) .skeleton-subtitle,
      :host-context(html[data-theme="dark"]) .skeleton-image,
      :host-context(html[data-theme="dark"]) .skeleton-line {
        background: linear-gradient(
          90deg,
          var(--colour-surface-elevated) 25%,
          var(--colour-surface-strong) 50%,
          var(--colour-surface-elevated) 75%
        );
        background-size: 200% 100%;
      }
    `,
  ],
})
export class SearchResultsComponent implements OnInit, OnDestroy {
  protected readonly searchService = inject(SearchService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly elementRef = inject(ElementRef);
  private readonly entriesService = inject(EntriesService);
  private readonly appDialog = inject(AppDialogService);
  protected readonly results$ = this.searchService.results$;
  private expandedKey: string | null = null;
  protected isRetrying = false;
  private searchSubscription?: Subscription;

  // Pagination properties matching entries list exactly
  protected pageSize = 8; // 2 rows of 4 cards - default from entries
  protected currentPage = 0;
  protected paginatedResults: SearchResult[] = [];
  protected selectedEntries = new Map<string, SearchResult>();
  protected deletingSelected = false;
  private selectionSearchKey = "";

  ngOnInit(): void {
    // Subscribe to search state changes and update pagination
    this.searchSubscription = this.results$.subscribe((searchState) => {
      const searchKey = `${searchState.query}|${searchState.filters.join(",")}`;
      if (this.selectionSearchKey && searchKey !== this.selectionSearchKey) {
        this.selectedEntries.clear();
      }
      this.selectionSearchKey = searchKey;
      if (searchState.results && searchState.results.length > 0) {
        // Reset to first page when new search results arrive
        // (We'll always reset pagination for new searches to avoid complexity)
        this.currentPage = 0;
        this.updatePaginatedResults(searchState);
      } else {
        this.paginatedResults = [];
      }
    });
  }

  ngOnDestroy(): void {
    this.searchSubscription?.unsubscribe();
  }

  toggleExpand(result: SearchResult): void {
    // Clean up any previously expanded cards
    this.cleanupPreviousExpanded();

    const key = this.selectionKey(result);
    this.expandedKey = this.expandedKey === key ? null : key;

    // If expanding, scroll the card into view after a short delay for animation
    if (this.expandedKey !== null) {
      setTimeout(() => this.scrollToCard(key), 300);
    }
  }

  private cleanupPreviousExpanded(): void {
    // Remove positioning classes and styles from all expanded cards
    const expandedCards = this.elementRef.nativeElement.querySelectorAll(
      ".expanded-details-card",
    );
    expandedCards.forEach((card: HTMLElement) => {
      card.classList.remove("align-left", "align-right");
      card.style.removeProperty("--offset-x");
      card.style.removeProperty("--expanded-width");
    });

    // Also clean up connector positioning if needed
    const connectors = this.elementRef.nativeElement.querySelectorAll(
      ".expanded-connector",
    );
    connectors.forEach((connector: HTMLElement) => {
      connector.style.removeProperty("--connector-offset");
    });
  }

  private scrollToCard(key: string): void {
    const cardElement = this.elementRef.nativeElement.querySelector(
      `[data-card-id="${key}"]`,
    );
    if (cardElement) {
      setTimeout(() => {
        // Get the grid container and its bounds
        const gridContainer =
          this.elementRef.nativeElement.querySelector(".results-grid");
        const expandedCard = cardElement.querySelector(
          ".expanded-details-card",
        );

        if (expandedCard && gridContainer) {
          const gridRect = gridContainer.getBoundingClientRect();
          const cardRect = cardElement.getBoundingClientRect();

          // Calculate position relative to grid
          const cardPositionInGrid = cardRect.left - gridRect.left;
          const gridWidth = gridRect.width;
          const expandedWidth = Math.min(900, gridWidth * 0.9); // 90% of grid width max

          // Check if card is in right half of grid
          const isRightSide = cardPositionInGrid > gridWidth / 2;

          // Calculate optimal position
          let leftOffset = 0;
          if (isRightSide) {
            // Position so right edge aligns with grid right edge
            leftOffset = gridWidth - expandedWidth - cardPositionInGrid;
          } else {
            // Position so left edge aligns with grid left edge
            leftOffset = -cardPositionInGrid;
          }

          // Apply the positioning
          expandedCard.style.setProperty("--offset-x", `${leftOffset}px`);
          expandedCard.style.setProperty(
            "--expanded-width",
            `${expandedWidth}px`,
          );

          if (isRightSide) {
            expandedCard.classList.add("align-right");
          } else {
            expandedCard.classList.add("align-left");
          }
        }

        // Scroll into view
        cardElement.scrollIntoView({
          behavior: "smooth",
          block: "start",
          inline: "nearest",
        });
      }, 50); // Small delay to ensure DOM is updated
    }
  }

  isExpanded(result: SearchResult): boolean {
    return this.expandedKey === this.selectionKey(result);
  }

  getDisplayTitle(result: SearchResult): SafeHtml {
    // Use highlighted title if available, otherwise plain title
    const highlighted =
      result.matches?.title || result.title_highlight || result.title;
    return this.sanitizer.bypassSecurityTrustHtml(highlighted);
  }

  getSafeHtml(content: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(content);
  }

  getBestSnippet(result: SearchResult): string {
    // Prioritize: body match > tags match > people match
    // Return the most relevant single snippet to avoid visual clutter
    if (result.matches.body) {
      return this.truncateSnippet(result.matches.body);
    }
    if (result.matches.tags) {
      return this.truncateSnippet(result.matches.tags);
    }
    if (result.matches.people) {
      return this.truncateSnippet(result.matches.people);
    }

    // Fallback to a simple message if no matches found
    return "No preview available";
  }

  private truncateSnippet(snippet: string): string {
    // Remove HTML tags temporarily to count actual text length
    const textOnly = snippet.replace(/<[^>]*>/g, "");

    // If the text is already short, return as-is
    if (textOnly.length <= 120) {
      return snippet;
    }

    // For longer text, try to truncate at word boundaries while preserving highlighting
    const maxLength = 100;
    let truncated = snippet;

    // Find a good truncation point near the highlighted term
    const matchIndex = snippet.toLowerCase().indexOf("<span");
    if (matchIndex > -1) {
      // Keep content around the match
      const beforeMatch = snippet.substring(0, matchIndex);
      const afterMatchStart = snippet.indexOf("</span>", matchIndex) + 7;
      const afterMatch = snippet.substring(afterMatchStart);

      // Truncate before and after the match
      const beforeTruncated =
        beforeMatch.length > 50
          ? "..." + beforeMatch.substring(beforeMatch.length - 40)
          : beforeMatch;
      const afterTruncated =
        afterMatch.length > 50
          ? afterMatch.substring(0, 40) + "..."
          : afterMatch;

      truncated =
        beforeTruncated +
        snippet.substring(matchIndex, afterMatchStart) +
        afterTruncated;
    } else {
      // No highlighting found, just truncate normally
      truncated =
        snippet.substring(0, maxLength) +
        (snippet.length > maxLength ? "..." : "");
    }

    return truncated;
  }

  closeExpanded(event: Event): void {
    event.stopPropagation();
    this.expandedKey = null;
  }

  closeExpandedIfClickingAway(event: Event): void {
    // Only close if we have an expanded card and the click wasn't on a card
    if (this.expandedKey !== null) {
      this.expandedKey = null;
    }
  }

  retry(state: SearchState): void {
    if (this.isRetrying) return; // Prevent multiple retry attempts

    this.isRetrying = true;
    const filtersObj = {
      tags: state.filters.includes("tags"),
      date: state.filters.includes("date"),
      keywords: state.filters.includes("keywords"),
      people: state.filters.includes("people"),
    };

    this.searchService.search(state.query, filtersObj).subscribe({
      next: () => {
        this.isRetrying = false;
      },
      error: () => {
        this.isRetrying = false;
      },
      complete: () => {
        this.isRetrying = false;
      },
    });
  }

  getErrorMessage(error: string): string {
    if (error.toLowerCase().startsWith("openmynd could not")) {
      return error;
    }
    // Parse common error types and provide user-friendly messages
    if (
      error.toLowerCase().includes("network") ||
      error.toLowerCase().includes("connection")
    ) {
      return "Unable to connect to the server. Please check your internet connection.";
    }
    if (error.toLowerCase().includes("timeout")) {
      return "Search request timed out. The server may be busy or your connection is slow.";
    }
    if (error.toLowerCase().includes("server") || error.includes("500")) {
      return "The search service is temporarily unavailable. Please try again in a moment.";
    }
    if (error.toLowerCase().includes("unauthorized") || error.includes("401")) {
      return "Your session has expired. Please refresh the page and log in again.";
    }

    // Generic error message for unknown errors
    return "Something went wrong while searching. Please try again.";
  }

  getErrorSuggestions(error: string): string[] {
    const suggestions: string[] = [];

    if (
      error.toLowerCase().includes("network") ||
      error.toLowerCase().includes("connection")
    ) {
      suggestions.push("Check your internet connection");
      suggestions.push("Try refreshing the page");
      suggestions.push("Contact support if the issue persists");
    } else if (error.toLowerCase().includes("timeout")) {
      suggestions.push("Try a simpler search term");
      suggestions.push("Check your internet speed");
      suggestions.push("Wait a moment and try again");
    } else if (
      error.toLowerCase().includes("server") ||
      error.includes("500")
    ) {
      suggestions.push("Wait a few minutes and try again");
      suggestions.push("Try a different search term");
      suggestions.push("Contact support if the issue continues");
    } else if (
      error.toLowerCase().includes("unauthorized") ||
      error.includes("401")
    ) {
      suggestions.push("Refresh the page and log in again");
      suggestions.push("Clear your browser cache");
    } else {
      // Generic suggestions
      suggestions.push("Try refreshing the page");
      suggestions.push("Check your internet connection");
      suggestions.push("Try a different search term");
    }

    return suggestions.slice(0, 3); // Limit to 3 suggestions
  }

  clearSearch(): void {
    this.searchService.clear();
    void this.router.navigate(["/entries"], {
      queryParams: this.getQueryParamsWithoutSearch(),
      replaceUrl: true,
    });
  }

  browseAllEntries(): void {
    this.searchService.clear();
    void this.router.navigate(["/entries"], {
      queryParams: this.getQueryParamsWithoutSearch(),
      replaceUrl: true,
    });
  }

  private getQueryParamsWithoutSearch(): Record<string, string> {
    const queryParams = this.route.snapshot.queryParams;
    const filtered = Object.entries(queryParams).filter(
      ([key, value]) =>
        key !== "search" &&
        key !== "filters" &&
        value !== null &&
        value !== undefined &&
        value !== "",
    );
    return Object.fromEntries(filtered);
  }

  getResultLink(result: SearchResult): unknown[] {
    if (result.type === "thought_record") {
      return ["/cbt", result.id];
    }
    if (result.type === "important_day") {
      return ["/important-days"];
    }
    return ["/entries", result.id];
  }

  getResultQueryParams(
    result: SearchResult,
    state: SearchState,
  ): Record<string, string> {
    const params: Record<string, string> = {
      search: state.query,
      entryType: result.type,
    };
    if (state.filters.length > 0) {
      params["filters"] = state.filters.join(",");
    }
    if (result.type === "important_day") {
      params["importantDayId"] = String(result.id);
    }
    return params;
  }

  protected getResultIcon(result: SearchResult): string {
    if (result.type === "dream") return "nights_stay";
    if (result.type === "thought_record") return "psychology_alt";
    if (result.type === "important_day") return "event";
    return "book";
  }

  protected getResultPlaceholderIcon(result: SearchResult): string {
    if (result.type === "thought_record") return "psychology_alt";
    if (result.type === "important_day") return "event_note";
    return "pie_chart";
  }

  protected getResultTypeLabel(result: SearchResult): string {
    if (result.type === "dream") return "dream";
    if (result.type === "thought_record") return "thought record";
    if (result.type === "important_day") return "important day";
    return "entry";
  }

  getSearchSuggestions(query: string): string[] {
    const suggestions: string[] = [];

    // Basic suggestions based on query characteristics
    if (query.length > 0) {
      // Check if query looks like a person's name (capitalized)
      if (
        query.charAt(0) === query.charAt(0).toUpperCase() &&
        !query.includes(" ")
      ) {
        suggestions.push(
          `Try variations like "${query.toLowerCase()}" or nicknames`,
        );
        suggestions.push("Search for the full name if you used a nickname");
      }

      // Always show comprehensive search tips
      suggestions.push(
        'Try searching for a date (e.g., "26th August", "October 2023")',
      );
      suggestions.push(
        "Search for keywords, places, or emotions from your entries",
      );
      suggestions.push("Try tags or people names mentioned in your diary");
      suggestions.push("Check your spelling and try fewer keywords");
    }

    // Limit to 4 suggestions max for clean UI
    return suggestions.slice(0, 4);
  }

  getResultCountMessage(searchState: SearchState): string {
    const count = searchState.results.length;
    const query = searchState.query;
    const context = searchState.filters_display;

    if (count === 0) {
      return `No records found for "${query}" in ${context}`;
    } else if (count === 1) {
      return `About 1 result for "${query}" in ${context}`;
    } else if (searchState.truncated) {
      return `Showing first ${count} results for "${query}" in ${context}`;
    } else {
      return `About ${count} results for "${query}" in ${context}`;
    }
  }

  // Pagination Methods - Matching entries list exactly

  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.updatePaginatedResults();
  }

  updatePaginatedResults(searchState?: SearchState): void {
    // Use current search state or get it from the service
    const currentState =
      searchState || this.searchService.getCurrentSearchState();

    if (
      currentState &&
      currentState.results &&
      currentState.results.length > 0
    ) {
      const startIndex = this.currentPage * this.pageSize;
      const endIndex = startIndex + this.pageSize;
      this.paginatedResults = currentState.results.slice(startIndex, endIndex);
    } else {
      this.paginatedResults = [];
    }
  }

  // Reset pagination when new search performed
  resetPagination(): void {
    this.currentPage = 0;
    this.updatePaginatedResults();
  }

  protected selectionKey(result: SearchResult): string {
    return `${result.type}:${result.id}`;
  }

  protected isDeletableResult(
    result: SearchResult,
  ): result is SearchResult & { type: "daily" | "dream" } {
    return result.type === "daily" || result.type === "dream";
  }

  protected hasDeletableResults(searchState: SearchState): boolean {
    return searchState.results.some((result) => this.isDeletableResult(result));
  }

  protected isSelected(result: SearchResult): boolean {
    return this.selectedEntries.has(this.selectionKey(result));
  }

  protected setSelected(result: SearchResult, selected: boolean): void {
    const key = this.selectionKey(result);
    if (selected) this.selectedEntries.set(key, result);
    else this.selectedEntries.delete(key);
  }

  protected isCurrentPageSelected(): boolean {
    const deletableResults = this.paginatedResults.filter((item) =>
      this.isDeletableResult(item),
    );
    return deletableResults.length > 0 && deletableResults.every((item) => this.isSelected(item));
  }

  protected toggleCurrentPageSelection(): void {
    const selected = !this.isCurrentPageSelected();
    this.paginatedResults
      .filter((item) => this.isDeletableResult(item))
      .forEach((item) => this.setSelected(item, selected));
  }

  protected async deleteSelected(searchState: SearchState): Promise<void> {
    const count = this.selectedEntries.size;
    if (!count || this.deletingSelected) return;
    const confirmed = await this.appDialog.confirm({
      title: `Delete ${count} selected ${count === 1 ? "entry" : "entries"}?`,
      message: "This permanently deletes the selected entries and their images and attachments.",
      confirmText: "Delete selected",
      cancelText: "Cancel",
      variant: "danger",
    });
    if (!confirmed) return;

    this.deletingSelected = true;
    const entries = Array.from(this.selectedEntries.values())
      .filter(
        (
          result,
        ): result is SearchResult & { type: "daily" | "dream" } =>
          this.isDeletableResult(result),
      )
      .map(({ id, type }) => ({ id, type }));
    this.entriesService.deleteSelectedEntries(entries).subscribe({
      next: () => {
        this.selectedEntries.clear();
        this.deletingSelected = false;
        const filters = {
          tags: searchState.filters.includes("tags"),
          date: searchState.filters.includes("date"),
          keywords: searchState.filters.includes("keywords"),
          people: searchState.filters.includes("people"),
        };
        this.searchService.search(searchState.query, filters).subscribe();
      },
      error: (error: Error) => {
        this.deletingSelected = false;
        void this.appDialog.alert({
          title: "Entries could not be deleted",
          message: error.message || "Please try again.",
          confirmText: "Close",
          variant: "error",
        });
      },
    });
  }
}
