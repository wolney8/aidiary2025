// Entry list with timeline and card grid
import {
  Component,
  HostListener,
  OnDestroy,
  OnInit,
  inject,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, Router, RouterModule } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatPaginatorModule, PageEvent } from "@angular/material/paginator";
import { MatChipsModule } from "@angular/material/chips";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { catchError, forkJoin, of } from "rxjs";
import { SearchResultsComponent } from "../../shared/components/search-results/search-results.component";
import { EntriesService } from "../../core/services/entries.service";
import { CbtService } from "../../core/services/cbt.service";
import { ImportantDaysService } from "../../core/services/important-days.service";
import { PublicHolidaysService } from "../../core/services/public-holidays.service";
import { OnThisDayService } from "../../core/services/on-this-day.service";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { ThemeService } from "../../core/services/theme.service";
import { AuthService } from "../../core/services/auth.service";
import {
  SearchFilters,
  SearchService,
} from "../../core/services/search.service";
import { DailyEntry, DreamEntry } from "../../core/models/entry.model";
import { ImportantDay } from "../../core/models/important-day.model";
import { PublicHoliday } from "../../core/models/public-holiday.model";
import { CbtWorksheet } from "../../core/models/cbt.model";
import {
  OnThisDayEntry,
  OnThisDayFeed,
} from "../../core/models/on-this-day.model";

type TimelineMonth = {
  label: string;
  year: number;
  isCurrent: boolean;
  isSelected: boolean;
  isFuture: boolean;
  isActive: boolean;
  entryCount?: number;
};

type EntryItem = (DailyEntry | DreamEntry) & { type: "daily" | "dream" };
type ThoughtRecordItem = CbtWorksheet & { type: "thought_record" };
type CardItem = EntryItem | ThoughtRecordItem;
type WritingRhythmRecordType = "daily" | "dream" | "thought_record";
type ContentFilter =
  | "daily"
  | "dreams"
  | "thought-records"
  | "important-days"
  | "on-this-day";
type WritingRhythmStats = {
  currentRunDays: number;
  weekCount: number;
  monthCount: number;
  weeklyGoal: number;
  weeklyProgress: number;
  includedLabel: string;
  message: string;
};

type CalendarStatus = "none" | "daily" | "dream" | "complete";
type CalendarPreviewType = "daily" | "dream";
type CalendarDayMetricType =
  | "daily"
  | "dream"
  | "thought_record"
  | "important_day"
  | "public_holiday"
  | "on_this_day";

type CalendarDayMetric = {
  type: CalendarDayMetricType;
  icon: string;
  count: number;
  label: string;
  cssClass: string;
  testId?: string;
};

type CalendarDay = {
  date: Date;
  dayNumber: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  isFuture: boolean;
  status: CalendarStatus;
  entries: EntryItem[];
  thoughtRecords: CbtWorksheet[];
  importantDays: ImportantDay[];
  publicHolidays: PublicHoliday[];
  hiddenItemCount: number;
  hiddenItemLabel: string;
};

type CalendarPreviewState = {
  dayKey: string;
  type: CalendarPreviewType;
  phase: "open" | "closing";
  direction: "left-to-right" | "right-to-left";
  entries: EntryItem[];
  totalCount: number;
  dateLabel: string;
  top: number;
  left: number;
  placement: "above" | "below";
};

type ImportantDayPreviewState = {
  dayKey: string;
  scope: "day" | "month";
  heading: string;
  phase: "open" | "closing";
  direction: "left-to-right" | "right-to-left";
  importantDays: ImportantDay[];
  dateLabel: string;
  top: number;
  left: number;
  placement: "above" | "below";
};

type CbtPreviewState = {
  dayKey: string;
  heading: string;
  phase: "open" | "closing";
  direction: "left-to-right" | "right-to-left";
  records: CbtWorksheet[];
  totalCount: number;
  dateLabel: string;
  top: number;
  left: number;
  placement: "above" | "below";
};

type OccasionPreviewItem = {
  kind: "important" | "holiday";
  label: string;
  subtitle: string;
  note?: string;
  meta: string[];
  icon: string;
  accentClass: string;
  imageUrl?: string | null;
};

type OccasionPreviewState = {
  dayKey: string;
  phase: "open" | "closing";
  direction: "left-to-right" | "right-to-left";
  heading: string;
  occasions: OccasionPreviewItem[];
  dateLabel: string;
  top: number;
  left: number;
  placement: "above" | "below";
};

type OnThisDayPreviewState = {
  scope: "day" | "month";
  heading: string;
  phase: "open" | "closing";
  direction: "left-to-right" | "right-to-left";
  entries: OnThisDayEntry[];
  totalCount: number;
  dateLabel: string;
  top: number;
  left: number;
  placement: "above" | "below";
};

@Component({
  selector: "app-list",
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatPaginatorModule,
    MatChipsModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
    SearchResultsComponent,
  ],
  styleUrl: "./list.component.css",
  template: `
    <div class="list-container" [class.entries-are-loading]="isLoadingEntries">
      <h1 class="visually-hidden">Diary entries</h1>
      <ng-container *ngIf="searchService.results$ | async as searchState">
        <!-- Search Results View -->
        <ng-container *ngIf="searchState.active">
          <div class="search-mode-header">
            <button mat-button (click)="exitSearch()">
              <mat-icon>arrow_back</mat-icon>
              Back to Entries
            </button>
          </div>
          <app-search-results></app-search-results>
        </ng-container>

        <!-- Normal Entries View -->
        <ng-container *ngIf="!searchState.active">
          <div class="list-header">
            <div class="list-controls">
              <div
                class="display-mode-toggle"
                [class.cards-active]="displayMode === 'cards'"
                role="group"
                aria-label="Entries display mode"
                data-testid="entries-display-mode-toggle"
              >
                <button
                  type="button"
                  [class.active]="displayMode === 'calendar'"
                  [attr.aria-pressed]="displayMode === 'calendar'"
                  (click)="setDisplayMode('calendar')"
                  data-testid="entries-display-calendar"
                >
                  Calendar
                </button>
                <button
                  type="button"
                  [class.active]="displayMode === 'cards'"
                  [attr.aria-pressed]="displayMode === 'cards'"
                  (click)="setDisplayMode('cards')"
                  data-testid="entries-display-cards"
                >
                  Cards
                </button>
              </div>
              <div class="content-filter-row">
                <mat-chip-listbox
                  class="content-filter-chips"
                  multiple
                  aria-label="Filter visible diary content"
                  data-testid="entries-content-filters"
                >
                  <ng-container *ngFor="let option of contentFilterOptions">
                    <mat-chip-option
                      *ngIf="!isContentFilterDisabled(option.value)"
                      [selected]="isContentFilterActive(option.value)"
                      [class.is-active]="isContentFilterActive(option.value)"
                      (selectionChange)="$event.isUserInput && setContentFilter(option.value, $event.selected)"
                      [attr.data-testid]="'entries-filter-' + option.value"
                    >
                      <mat-icon aria-hidden="true">{{ option.icon }}</mat-icon>
                      {{ option.label }}
                    </mat-chip-option>
                  </ng-container>
                </mat-chip-listbox>
                <span
                  *ngIf="isContentFilterDisabled('on-this-day')"
                  class="disabled-filter-tooltip"
                  role="group"
                  tabindex="0"
                  aria-label="On this day unavailable. Enable it in Customisation."
                  matTooltip="Enable On this day in Customisation."
                >
                  <button
                    type="button"
                    class="content-filter-disabled"
                    data-testid="entries-filter-on-this-day"
                    disabled
                  >
                    <mat-icon aria-hidden="true">history</mat-icon>
                    On this day
                  </button>
                </span>
              </div>
            </div>
            <button
              mat-raised-button
              color="primary"
              (click)="navigateToCreateEntry()"
            >
              New Entry
            </button>
          </div>

          <section
            class="entries-loading-panel"
            *ngIf="isLoadingEntries"
            role="status"
            aria-live="polite"
            data-testid="entries-loading-panel"
          >
            <mat-progress-spinner mode="indeterminate" diameter="34" />
            <div>
              <strong>Loading your entries…</strong>
              <span>Connecting to your journal data. This can take a moment on first load.</span>
            </div>
          </section>

          <section
            class="entries-error-panel"
            *ngIf="!isLoadingEntries && entriesLoadError"
            role="alert"
            data-testid="entries-load-error"
          >
            <mat-icon aria-hidden="true">error</mat-icon>
            <div>
              <strong>Entries could not be loaded.</strong>
              <span>{{ entriesLoadError }}</span>
            </div>
            <button mat-stroked-button type="button" (click)="loadEntries()">
              <mat-icon aria-hidden="true">refresh</mat-icon>
              Retry
            </button>
          </section>

          <section
            *ngIf="getWritingRhythmStats() as rhythm"
            class="writing-rhythm-panel"
            aria-labelledby="writing-rhythm-heading"
            data-testid="writing-rhythm-panel"
          >
            <div class="writing-rhythm-lead">
              <span class="writing-rhythm-icon" aria-hidden="true">
                <mat-icon>local_fire_department</mat-icon>
              </span>
              <div>
                <h2 id="writing-rhythm-heading">Writing rhythm</h2>
                <p>{{ rhythm.message }}</p>
              </div>
            </div>
            <div class="writing-rhythm-metrics" aria-label="Writing rhythm metrics">
              <div class="writing-rhythm-pill">
                <strong>{{ rhythm.currentRunDays }}</strong>
                <span>day run</span>
              </div>
              <div class="writing-rhythm-pill">
                <strong>{{ rhythm.weekCount }}/{{ rhythm.weeklyGoal }}</strong>
                <span>this week</span>
              </div>
              <div class="writing-rhythm-pill">
                <strong>{{ rhythm.monthCount }}</strong>
                <span>this month</span>
              </div>
            </div>
            <div class="writing-rhythm-progress" aria-hidden="true">
              <span [style.width.%]="rhythm.weeklyProgress"></span>
            </div>
            <small>{{ rhythm.includedLabel }}</small>
          </section>

          <!-- Timeline scroller -->
          <div class="timeline-scroller">
            <button
              mat-button
              class="timeline-nav-button"
              (click)="jumpToFirstEntry()"
              [disabled]="!hasEntries()"
            >
              First
            </button>

            <button
              mat-icon-button
              class="timeline-step-button"
              (click)="scrollTimeline(-1)"
              [disabled]="timelineScrollIndex <= minScrollIndex"
              aria-label="Show earlier months"
            >
              <mat-icon>chevron_left</mat-icon>
            </button>

            <div class="timeline-months">
              <button
                type="button"
                class="month-item"
                *ngFor="let item of visibleMonths"
                [class.current]="item.isCurrent"
                [class.selected]="item.isSelected"
                [class.future]="item.isFuture"
                [class.clickable]="!item.isFuture"
                [disabled]="item.isFuture"
                [attr.aria-current]="item.isSelected ? 'date' : null"
                [attr.aria-label]="getTimelineMonthAriaLabel(item)"
                (click)="selectMonth(item)"
              >
                <span class="year">{{ item.year }}</span>
                <span class="month">{{ item.label }}</span>
                <span
                  class="entry-count-badge"
                  *ngIf="item.entryCount && !item.isFuture"
                >
                  {{ item.entryCount }}
                </span>
              </button>
            </div>

            <button
              mat-icon-button
              class="timeline-step-button"
              (click)="scrollTimeline(1)"
              [disabled]="timelineScrollIndex >= maxScrollIndex"
              aria-label="Show later months"
            >
              <mat-icon>chevron_right</mat-icon>
            </button>

            <button
              mat-button
              class="timeline-nav-button"
              (click)="jumpToToday()"
            >
              Today
            </button>
          </div>

          <div
            class="monthly-context-shelves"
            *ngIf="getCurrentMonthImportantDays().length > 0 || getCurrentMonthOnThisDayEntries().length > 0 || getCurrentMonthThoughtRecords().length > 0"
            data-testid="entries-monthly-context-shelves"
          >
            <button
              *ngIf="getCurrentMonthImportantDays().length > 0"
              type="button"
              class="on-this-day-summary calendar-important-days-summary-trigger"
              data-testid="calendar-important-days-summary-trigger"
              [attr.aria-expanded]="importantDayPreview?.scope === 'month' && importantDayPreview?.phase === 'open'"
              [attr.aria-controls]="displayMode === 'cards' ? 'cards-important-day-preview' : 'important-day-preview'"
              (click)="toggleMonthlyImportantDaysPreview($event)"
            >
              <span class="on-this-day-summary-icon important-days" aria-hidden="true">
                <mat-icon>event</mat-icon>
              </span>
              <span class="on-this-day-summary-copy">
                <strong>Important days this month</strong>
                <small>{{ getCurrentMonthImportantDaysSummaryLabel() }}</small>
              </span>
              <mat-icon aria-hidden="true">chevron_right</mat-icon>
            </button>
            <button
              *ngIf="getCurrentMonthThoughtRecords().length > 0"
              type="button"
              class="on-this-day-summary calendar-thought-records-summary-trigger"
              data-testid="calendar-thought-records-summary-trigger"
              [attr.aria-expanded]="cbtPreview?.dayKey === getCurrentMonthThoughtRecordsKey() && cbtPreview?.phase === 'open'"
              [attr.aria-controls]="displayMode === 'cards' ? 'cards-thought-record-preview' : 'thought-record-preview'"
              (click)="toggleMonthlyCbtPreview($event)"
            >
              <span class="on-this-day-summary-icon thought-records" aria-hidden="true">
                <mat-icon>psychology_alt</mat-icon>
              </span>
              <span class="on-this-day-summary-copy">
                <strong>Thought records this month</strong>
                <small>{{ getCurrentMonthThoughtRecordsSummaryLabel() }}</small>
              </span>
              <mat-icon aria-hidden="true">chevron_right</mat-icon>
            </button>
            <button
              *ngIf="getCurrentMonthOnThisDayEntries().length > 0"
              type="button"
              class="on-this-day-summary calendar-on-this-day-summary-trigger"
              data-testid="calendar-on-this-day-month-summary-trigger"
              [attr.aria-expanded]="onThisDayPreview?.scope === 'month' && onThisDayPreview?.phase === 'open'"
              [attr.aria-controls]="displayMode === 'cards' ? 'cards-on-this-day-preview' : 'on-this-day-preview'"
              (click)="toggleMonthlyOnThisDayPreview($event)"
            >
              <span class="on-this-day-summary-icon on-this-day" aria-hidden="true">
                <mat-icon>history</mat-icon>
              </span>
              <span class="on-this-day-summary-copy">
                <strong>On this day this month</strong>
                <small>{{ getCurrentMonthOnThisDaySummaryLabel() }}</small>
              </span>
              <mat-icon aria-hidden="true">chevron_right</mat-icon>
            </button>
          </div>

          <ng-container *ngIf="displayMode === 'cards'">
            <section
              id="cards-on-this-day-preview"
              class="calendar-preview-deck on-this-day-preview-deck"
              *ngIf="onThisDayPreview"
              [class.preview-left-to-right]="onThisDayPreview.direction === 'left-to-right'"
              [class.preview-right-to-left]="onThisDayPreview.direction === 'right-to-left'"
              [class.preview-below]="onThisDayPreview.placement === 'below'"
              [class.preview-above]="onThisDayPreview.placement === 'above'"
              [class.closing]="onThisDayPreview.phase === 'closing'"
              [style.top.px]="onThisDayPreview.top"
              [style.left.px]="onThisDayPreview.left"
              (click)="$event.stopPropagation()"
              aria-label="On this day preview deck"
              data-testid="cards-on-this-day-preview"
            >
              <header class="calendar-preview-header">
                <div>
                  <strong>{{ onThisDayPreview.heading }}</strong>
                  <span>{{ onThisDayPreview.dateLabel }}</span>
                </div>
                <button
                  type="button"
                  class="calendar-preview-close"
                  aria-label="Close On this day preview"
                  (click)="closeOnThisDayPreview($event)"
                >
                  <mat-icon>close</mat-icon>
                </button>
              </header>
              <div class="calendar-preview-cards">
                <article
                  class="calendar-preview-card on-this-day-preview-card"
                  *ngFor="let entry of onThisDayPreview.entries; let previewIndex = index"
                  [style.--preview-index]="previewIndex"
                  [class.has-preview-image]="entry.image_url"
                >
                  <div
                    class="calendar-preview-card-image"
                    *ngIf="entry.image_url"
                    [style.background-image]="getOnThisDayImageStyle(entry)"
                    aria-hidden="true"
                  ></div>
                  <button
                    type="button"
                    class="on-this-day-card-open"
                    (click)="openOnThisDayEntry(entry, $event)"
                    [attr.aria-label]="'View ' + entry.title"
                  >
                    <div class="calendar-preview-card-title">
                      <mat-icon aria-hidden="true">{{ getOnThisDayIcon(entry) }}</mat-icon>
                      <div>
                        <span>{{ entry.title }}</span>
                        <small>{{ getOnThisDayEntryDateLabel(entry) }}</small>
                      </div>
                    </div>
                    <div class="calendar-preview-card-copy">
                      <div class="calendar-preview-copy-block">
                        <span class="calendar-preview-copy-label">Memory</span>
                        <p>{{ entry.preview || 'No preview available.' }}</p>
                      </div>
                    </div>
                  </button>
                  <button
                    mat-icon-button
                    type="button"
                    class="on-this-day-hide"
                    (click)="hideOnThisDayEntry(entry, $event)"
                    [attr.aria-label]="'Hide ' + entry.title + ' from On this day'"
                    matTooltip="Hide this memory"
                  >
                    <mat-icon>visibility_off</mat-icon>
                  </button>
                </article>
                <button
                  *ngIf="shouldShowOnThisDayMoreCard()"
                  type="button"
                  class="calendar-preview-card calendar-preview-card-more"
                  [style.--preview-index]="onThisDayPreview.entries.length"
                  (click)="openOnThisDayFullView($event)"
                  [attr.aria-label]="getOnThisDayMoreLabel()"
                >
                  <mat-icon>arrow_forward</mat-icon>
                  <span>{{ getOnThisDayMoreLabel() }}</span>
                </button>
              </div>
            </section>

            <section
              id="cards-thought-record-preview"
              class="calendar-preview-deck cbt-preview-deck"
              *ngIf="cbtPreview"
              [class.preview-left-to-right]="cbtPreview.direction === 'left-to-right'"
              [class.preview-right-to-left]="cbtPreview.direction === 'right-to-left'"
              [class.preview-below]="cbtPreview.placement === 'below'"
              [class.preview-above]="cbtPreview.placement === 'above'"
              [class.closing]="cbtPreview.phase === 'closing'"
              [style.top.px]="cbtPreview.top"
              [style.left.px]="cbtPreview.left"
              (click)="$event.stopPropagation()"
              aria-label="Thought record preview deck"
              data-testid="cards-thought-record-preview"
            >
              <header class="calendar-preview-header">
                <div>
                  <strong>{{ cbtPreview.heading }}</strong>
                  <span>{{ cbtPreview.dateLabel }}</span>
                </div>
                <button
                  type="button"
                  class="calendar-preview-close"
                  aria-label="Close thought record preview"
                  (click)="closeCbtPreview($event)"
                >
                  <mat-icon>close</mat-icon>
                </button>
              </header>
              <div class="calendar-preview-cards">
                <button
                  type="button"
                  class="calendar-preview-card cbt-calendar-preview-card"
                  *ngFor="let record of getCbtPreviewRecords(); let previewIndex = index"
                  [style.--preview-index]="previewIndex"
                  (click)="openThoughtRecord(record, $event)"
                >
                  <div class="calendar-preview-card-title">
                    <mat-icon>psychology_alt</mat-icon>
                    <div>
                      <span>{{ getThoughtRecordTitle(record) }}</span>
                      <small>{{ getThoughtRecordPreviewMeta(record) }}</small>
                    </div>
                  </div>
                  <div class="calendar-preview-card-copy">
                    <div class="calendar-preview-copy-block">
                      <span class="calendar-preview-copy-label">Situation</span>
                      <p>{{ record.situation || 'No situation added yet.' }}</p>
                    </div>
                    <div class="calendar-preview-copy-block" *ngIf="record.balanced_thought">
                      <span class="calendar-preview-copy-label">Balanced thought</span>
                      <p>{{ record.balanced_thought }}</p>
                    </div>
                  </div>
                </button>
                <button
                  type="button"
                  class="calendar-preview-card calendar-preview-card-more"
                  [style.--preview-index]="getCbtPreviewRecords().length"
                  (click)="openThoughtRecordsDashboard($event)"
                  aria-label="View all thought records"
                >
                  <mat-icon>arrow_forward</mat-icon>
                  <span>{{ getCbtPreviewMoreLabel() }}</span>
                </button>
              </div>
            </section>

            <section
              id="cards-important-day-preview"
              class="calendar-preview-deck important-day-preview-deck"
              *ngIf="importantDayPreview"
              [class.monthly-important-day-preview]="importantDayPreview.scope === 'month'"
              [class.monthly-preview-single]="importantDayPreview.importantDays.length === 1"
              [class.monthly-preview-double]="importantDayPreview.importantDays.length === 2"
              [class.preview-left-to-right]="getImportantDayPreviewDirection() === 'left-to-right'"
              [class.preview-right-to-left]="getImportantDayPreviewDirection() === 'right-to-left'"
              [class.preview-below]="importantDayPreview.placement === 'below'"
              [class.preview-above]="importantDayPreview.placement === 'above'"
              [class.closing]="importantDayPreview.phase === 'closing'"
              [style.top.px]="importantDayPreview.top"
              [style.left.px]="importantDayPreview.left"
              (click)="$event.stopPropagation()"
              aria-label="Important day preview deck"
              data-testid="cards-important-day-preview"
            >
              <header class="calendar-preview-header">
                <div>
                  <strong>{{ importantDayPreview.heading }}</strong>
                  <span>{{ importantDayPreview.dateLabel }}</span>
                </div>
                <button
                  type="button"
                  class="calendar-preview-close"
                  aria-label="Close important day preview"
                  (click)="closeImportantDayPreview($event)"
                >
                  <mat-icon>close</mat-icon>
                </button>
              </header>
              <div class="calendar-important-day-preview-cards">
                <article
                  class="calendar-important-day-card"
                  *ngFor="let importantDay of importantDayPreview.importantDays"
                  [class.has-preview-image]="getImportantDayImageUrl(importantDay)"
                  [ngClass]="'accent-' + importantDay.accent_color"
                >
                  <div class="calendar-important-day-card-media">
                    <div class="calendar-important-day-card-icon" aria-hidden="true">
                      <mat-icon>{{ getImportantDayIcon(importantDay) }}</mat-icon>
                    </div>
                    <button
                      type="button"
                      class="calendar-important-day-card-thumb"
                      *ngIf="getImportantDayImageUrl(importantDay) as imageUrl"
                      (click)="openImportantDayImage(importantDay, $event)"
                      [attr.aria-label]="'View image for ' + importantDay.label"
                    >
                      <img [src]="imageUrl" alt="" />
                    </button>
                  </div>
                  <div class="calendar-important-day-card-copy">
                    <div class="calendar-important-day-card-heading">
                      <strong>{{ importantDay.label }}</strong>
                      <span>{{ formatImportantDaySummaryLabel(importantDay) }}</span>
                    </div>
                    <p class="calendar-important-day-card-note" *ngIf="importantDay.note">
                      {{ importantDay.note }}
                    </p>
                    <div class="calendar-important-day-card-meta">
                      <span>{{ getImportantDayRecurrenceLabel(importantDay) }}</span>
                      <span>{{ getImportantDayElapsedLabel(importantDay) }}</span>
                    </div>
                  </div>
                </article>
              </div>
            </section>
          </ng-container>

          <div class="selected-day-banner" *ngIf="selectedDay && displayMode === 'cards'">
            <div>
              <strong>{{ getSelectedDayLabel() }}</strong>
              <span>{{ totalEntries }} matching entr{{ totalEntries === 1 ? 'y' : 'ies' }}</span>
              <div
                class="selected-day-important-days"
                *ngIf="getSelectedDayImportantDays().length > 0"
              >
                <span
                  class="selected-day-important-chip"
                  *ngFor="let importantDay of getSelectedDayImportantDays()"
                >
                  <mat-icon aria-hidden="true">{{
                    getImportantDayIcon(importantDay)
                  }}</mat-icon>
                  {{ importantDay.label }}
                </span>
              </div>
              <div
                class="selected-day-important-days"
                *ngIf="getSelectedDayPublicHolidays().length > 0"
              >
                <span
                  class="selected-day-important-chip selected-day-holiday-chip"
                  *ngFor="let holiday of getSelectedDayPublicHolidays()"
                >
                  <mat-icon aria-hidden="true">{{
                    getPublicHolidayIcon(holiday)
                  }}</mat-icon>
                  {{ holiday.localName || holiday.name }}
                </span>
              </div>
            </div>
            <button
              mat-stroked-button
              type="button"
              class="selected-day-return"
              (click)="clearSelectedDay()"
            >
              Back to calendar
            </button>
          </div>

          <ng-container *ngIf="displayMode === 'cards'; else calendarMode">
            <!-- Top Pagination -->
            <div class="pagination-container">
              <mat-paginator
                [length]="totalEntries"
                [pageSize]="pageSize"
                [pageSizeOptions]="[8, 16, 32]"
                [pageIndex]="currentPage"
                [showFirstLastButtons]="true"
                (page)="onPageChange($event)"
                aria-label="Select page"
              >
              </mat-paginator>
            </div>

            <!-- No entries message -->
            <div class="no-entries-message" *ngIf="!isLoadingEntries && !entriesLoadError && paginatedEntries.length === 0">
              <mat-card class="no-entries-card">
                <mat-card-content>
                  <mat-icon class="no-entries-icon">calendar_today</mat-icon>
                  <h3>{{ getEmptyStateHeading() }}</h3>
                  <p>{{ getEmptyStateMessage() }}</p>
                  <button
                    mat-raised-button
                    color="primary"
                    (click)="navigateToCreateEntry()"
                  >
                    <mat-icon>add</mat-icon>
                    Add Entry Now
                  </button>
                </mat-card-content>
              </mat-card>
            </div>

            <!-- Entry cards grid -->
            <div
              class="entries-grid"
              [class.one-entry]="paginatedEntries.length === 1"
              [class.two-entries]="paginatedEntries.length === 2"
              [class.three-entries]="paginatedEntries.length === 3"
              *ngIf="paginatedEntries.length > 0"
            >
              <mat-card
                class="entry-card"
                *ngFor="let entry of paginatedEntries"
              >
                <mat-card-header>
                  <mat-icon mat-card-avatar>
                    {{ getCardItemIcon(entry) }}
                  </mat-icon>
                  <mat-card-title>{{
                    getEntryTitle(entry)
                  }}</mat-card-title>
                  <mat-card-subtitle>{{
                    getEntryDateTimeSubtitle(entry)
                  }}</mat-card-subtitle>
                  <mat-icon
                    class="entry-attachment-indicator"
                    *ngIf="hasEntryAttachments(entry)"
                    aria-hidden="true"
                  >
                    attach_file
                  </mat-icon>
                </mat-card-header>

                <mat-card-content>
                  <div
                    class="entry-card-image"
                    *ngIf="getEntryCardImageUrl(entry) as entryImageUrl; else entryCardPlaceholder"
                  >
                    <img [src]="entryImageUrl" alt="" />
                    <div
                      class="entry-ai-badge"
                      *ngIf="isAiGeneratedEntryImage(entry)"
                    >
                      <mat-icon>auto_awesome</mat-icon>
                    </div>
                  </div>
                  <ng-template #entryCardPlaceholder>
                    <div
                      class="entry-image-placeholder"
                      [class.thought-record-placeholder]="entry.type === 'thought_record'"
                    >
                      <mat-icon>{{ entry.type === "thought_record" ? "psychology_alt" : "pie_chart" }}</mat-icon>
                    </div>
                  </ng-template>
                  <div class="entry-card-copy">
                    <p class="entry-snippet">{{ getEntrySnippet(entry) }}</p>
                    <mat-chip-set *ngIf="getTags(entry).length > 0">
                      <mat-chip
                        *ngFor="let tag of getTags(entry).slice(0, 2)"
                        [class.duplicate-tag-chip]="isDuplicateTag(tag)"
                        (click)="searchForTag(tag, $event)"
                        >{{ tag }}</mat-chip
                      >
                      <mat-chip
                        *ngIf="getTags(entry).length > 2"
                        class="tag-overflow-chip"
                        [attr.aria-label]="
                          getTags(entry).length - 2 + ' more tags'
                        "
                      >
                        +{{ getTags(entry).length - 2 }}
                      </mat-chip>
                    </mat-chip-set>
                  </div>
                </mat-card-content>

                <mat-card-actions>
                  <button
                    mat-button
                    color="primary"
                    (click)="openEntryDetail(entry, $event)"
                    [attr.aria-label]="'Open ' + getEntryTitle(entry)"
                  >
                    {{ entry.type === "thought_record" ? "REVIEW RECORD" : "VIEW ENTRY" }}
                  </button>
                </mat-card-actions>
              </mat-card>
            </div>

            <!-- Bottom Pagination -->
            <div class="pagination-container">
              <mat-paginator
                [length]="totalEntries"
                [pageSize]="pageSize"
                [pageSizeOptions]="[8, 16, 32]"
                [pageIndex]="currentPage"
                [showFirstLastButtons]="true"
                (page)="onPageChange($event)"
                aria-label="Select page"
              >
              </mat-paginator>
            </div>
          </ng-container>

          <ng-template #calendarMode>
            <section class="calendar-shell" aria-label="Diary adherence calendar">
              <div class="calendar-summary">
                <div>
                  <h3>{{ getCalendarHeading() }}</h3>
                  <p>
                    Select a day to review entries or create one when a day is
                    empty.
                  </p>
                </div>
                <div class="calendar-legend" aria-label="Calendar legend">
                  <span
                    class="legend-item"
                    *ngIf="isContentFilterActive('thought-records')"
                  >
                    <mat-icon class="legend-thought-record-icon" aria-hidden="true">
                      psychology_alt
                    </mat-icon>
                    Thought record
                  </span>
                  <span
                    class="legend-item"
                    *ngIf="isContentFilterActive('important-days')"
                  >
                    <mat-icon class="legend-important-day-icon" aria-hidden="true">
                      event
                    </mat-icon>
                    Important day
                  </span>
                  <span class="legend-item" *ngIf="shouldShowOnThisDay()">
                    <mat-icon class="legend-on-this-day-icon" aria-hidden="true">
                      history
                    </mat-icon>
                    On this day
                  </span>
                </div>
              </div>

              <div
                class="calendar-board"
                tabindex="0"
                aria-label="Calendar grid. Scroll horizontally on smaller screens."
              >
                <div class="calendar-weekdays" aria-hidden="true">
                  <span *ngFor="let weekday of weekdays">{{ weekday }}</span>
                </div>

                <div class="calendar-grid">
                  <div
                    class="calendar-day"
                    *ngFor="let day of calendarDays; let dayIndex = index"
                    [class.outside-month]="!day.isCurrentMonth"
                    [class.unavailable]="day.isFuture"
                    [class.today]="day.isToday"
                    [class.has-entries]="day.status !== 'none'"
                    [class.status-daily]="day.status === 'daily'"
                    [class.status-dream]="day.status === 'dream'"
                    [class.status-complete]="day.status === 'complete'"
                    [class.has-hidden-filtered]="day.hiddenItemCount > 0"
                    [style.grid-column-start]="dayIndex === 0 ? getCalendarGridColumnStart(day) : null"
                  >
                    <div
                      class="calendar-day-inner"
                      [class.is-flipped]="isCalendarDayFlipped(day)"
                    >
                      <section
                        class="calendar-day-face calendar-day-front"
                        [style.background]="getCalendarDayFaceBackground(day, 'front')"
                        [attr.aria-hidden]="isCalendarDayFlipped(day)"
                        [attr.inert]="isCalendarDayFlipped(day) ? '' : null"
                        (click)="addEntryFromCalendarFace(day, $event)"
                      >
                        <button
                          *ngIf="day.isCurrentMonth && !day.isFuture; else unavailableDayNumber"
                          type="button"
                          class="calendar-day-action"
                          [attr.aria-label]="'Add an item for ' + getCalendarDayDateLabel(day)"
                          matTooltip="Add entry"
                          (click)="addEntryForCalendarDay(day, $event)"
                        >
                          <span class="calendar-day-action-number">{{ day.dayNumber }}</span>
                          <span class="calendar-day-action-add" aria-hidden="true">
                            <mat-icon>add</mat-icon>
                          </span>
                        </button>
                        <ng-template #unavailableDayNumber>
                          <span class="calendar-day-number" aria-hidden="true">{{ day.dayNumber }}</span>
                        </ng-template>
                        <button
                          *ngIf="hasCalendarDayBack(day)"
                          type="button"
                          class="calendar-day-flip"
                          [attr.aria-label]="'Show more items for ' + getCalendarDayDateLabel(day)"
                          matTooltip="Show more"
                          (click)="toggleCalendarDayFace(day, $event)"
                        >
                          <mat-icon>touch_app</mat-icon>
                        </button>
                        <span
                          *ngIf="day.hiddenItemCount > 0"
                          class="calendar-filtered-indicator"
                          [matTooltip]="day.hiddenItemLabel"
                          aria-hidden="true"
                        >
                          <mat-icon>visibility_off</mat-icon>
                          <span>{{ day.hiddenItemCount }}</span>
                        </span>
                        <div class="calendar-day-icons calendar-day-icons--front">
                          <div
                            class="calendar-day-icon-row calendar-day-icon-row--primary"
                            *ngIf="getFrontPrimaryCalendarDayMetrics(day).length > 0"
                          >
                            <button
                              *ngFor="let metric of getFrontPrimaryCalendarDayMetrics(day); trackBy: trackCalendarDayMetric"
                              type="button"
                              class="calendar-entry-icon"
                              [ngClass]="metric.cssClass"
                              [class.preview-active]="isCalendarDayMetricActive(day, metric.type)"
                              [attr.aria-label]="metric.label"
                              [attr.data-testid]="metric.testId || null"
                              [matTooltip]="metric.label"
                              (click)="activateCalendarDayMetric(day, metric.type, $event)"
                            >
                              <mat-icon>{{ metric.icon }}</mat-icon>
                              <span class="calendar-entry-count">{{ metric.count }}</span>
                            </button>
                          </div>
                          <div
                            class="calendar-day-icon-row calendar-day-icon-row--secondary"
                            *ngIf="getFrontSecondaryCalendarDayMetrics(day).length > 0"
                          >
                            <button
                              *ngFor="let metric of getFrontSecondaryCalendarDayMetrics(day); trackBy: trackCalendarDayMetric"
                              type="button"
                              class="calendar-entry-icon"
                              [ngClass]="metric.cssClass"
                              [class.preview-active]="isCalendarDayMetricActive(day, metric.type)"
                              [attr.aria-label]="metric.label"
                              [attr.data-testid]="metric.testId || null"
                              [matTooltip]="metric.label"
                              (click)="activateCalendarDayMetric(day, metric.type, $event)"
                            >
                              <mat-icon>{{ metric.icon }}</mat-icon>
                              <span class="calendar-entry-count">{{ metric.count }}</span>
                            </button>
                          </div>
                        </div>
                      </section>

                      <section
                        class="calendar-day-face calendar-day-back"
                        [style.background]="getCalendarDayFaceBackground(day, 'back')"
                        [attr.aria-hidden]="!isCalendarDayFlipped(day)"
                        [attr.inert]="isCalendarDayFlipped(day) ? null : ''"
                        (click)="addEntryFromCalendarFace(day, $event)"
                      >
                        <button
                          *ngIf="day.isCurrentMonth && !day.isFuture; else unavailableBackDayNumber"
                          type="button"
                          class="calendar-day-action"
                          [attr.aria-label]="'Add an item for ' + getCalendarDayDateLabel(day)"
                          matTooltip="Add entry"
                          (click)="addEntryForCalendarDay(day, $event)"
                        >
                          <span class="calendar-day-action-number">{{ day.dayNumber }}</span>
                          <span class="calendar-day-action-add" aria-hidden="true">
                            <mat-icon>add</mat-icon>
                          </span>
                        </button>
                        <ng-template #unavailableBackDayNumber>
                          <span class="calendar-day-number" aria-hidden="true">{{ day.dayNumber }}</span>
                        </ng-template>
                        <button
                          type="button"
                          class="calendar-day-flip"
                          [attr.aria-label]="'Show first items for ' + getCalendarDayDateLabel(day)"
                          matTooltip="Show first items"
                          (click)="toggleCalendarDayFace(day, $event)"
                        >
                          <mat-icon>touch_app</mat-icon>
                        </button>
                        <span
                          *ngIf="day.hiddenItemCount > 0"
                          class="calendar-filtered-indicator"
                          [matTooltip]="day.hiddenItemLabel"
                          aria-hidden="true"
                        >
                          <mat-icon>visibility_off</mat-icon>
                          <span>{{ day.hiddenItemCount }}</span>
                        </span>
                        <div class="calendar-day-icons calendar-day-secondary-content">
                          <button
                            *ngFor="let metric of getSecondaryCalendarDayMetrics(day); trackBy: trackCalendarDayMetric"
                            type="button"
                            class="calendar-entry-icon"
                            [ngClass]="metric.cssClass"
                            [class.preview-active]="isCalendarDayMetricActive(day, metric.type)"
                            [attr.aria-label]="metric.label"
                            [attr.data-testid]="metric.testId || null"
                            [matTooltip]="metric.label"
                            (click)="activateCalendarDayMetric(day, metric.type, $event)"
                          >
                            <mat-icon>{{ metric.icon }}</mat-icon>
                            <span class="calendar-entry-count">{{ metric.count }}</span>
                          </button>
                        </div>
                      </section>
                    </div>
                  </div>
                </div>
              </div>
              <section
                id="on-this-day-preview"
                class="calendar-preview-deck on-this-day-preview-deck"
                *ngIf="onThisDayPreview"
                [class.preview-left-to-right]="onThisDayPreview.direction === 'left-to-right'"
                [class.preview-right-to-left]="onThisDayPreview.direction === 'right-to-left'"
                [class.preview-below]="onThisDayPreview.placement === 'below'"
                [class.preview-above]="onThisDayPreview.placement === 'above'"
                [class.closing]="onThisDayPreview.phase === 'closing'"
                [style.top.px]="onThisDayPreview.top"
                [style.left.px]="onThisDayPreview.left"
                (click)="$event.stopPropagation()"
                aria-label="On this day preview deck"
                data-testid="on-this-day-preview"
              >
                <header class="calendar-preview-header">
                  <div>
                    <strong>{{ onThisDayPreview.heading }}</strong>
                    <span>{{ onThisDayPreview.dateLabel }}</span>
                  </div>
                  <button
                    type="button"
                    class="calendar-preview-close"
                    aria-label="Close On this day preview"
                    (click)="closeOnThisDayPreview($event)"
                  >
                    <mat-icon>close</mat-icon>
                  </button>
                </header>
                <div class="calendar-preview-cards">
                  <article
                    class="calendar-preview-card on-this-day-preview-card"
                    *ngFor="let entry of onThisDayPreview.entries; let previewIndex = index"
                    [style.--preview-index]="previewIndex"
                    [class.has-preview-image]="entry.image_url"
                    data-testid="on-this-day-card"
                  >
                    <div
                      class="calendar-preview-card-image"
                      *ngIf="entry.image_url"
                      [style.background-image]="getOnThisDayImageStyle(entry)"
                      aria-hidden="true"
                    ></div>
                    <button
                      type="button"
                      class="on-this-day-card-open"
                      (click)="openOnThisDayEntry(entry, $event)"
                      [attr.aria-label]="'View ' + entry.title"
                    >
                      <div class="calendar-preview-card-title">
                        <mat-icon aria-hidden="true">{{ getOnThisDayIcon(entry) }}</mat-icon>
                        <div>
                          <span>{{ entry.title }}</span>
                          <small>{{ getOnThisDayEntryDateLabel(entry) }}</small>
                        </div>
                      </div>
                      <div class="calendar-preview-card-tags" *ngIf="entry.tags.length">
                        <span
                          class="calendar-preview-tag"
                          *ngFor="let tag of entry.tags.slice(0, 3)"
                        >{{ tag }}</span>
                      </div>
                      <div class="calendar-preview-card-copy">
                        <div class="calendar-preview-copy-block">
                          <span class="calendar-preview-copy-label">Memory</span>
                          <p>{{ entry.preview || 'No preview available.' }}</p>
                        </div>
                      </div>
                    </button>
                    <button
                      mat-icon-button
                      type="button"
                      class="on-this-day-hide"
                      data-testid="on-this-day-hide"
                      (click)="hideOnThisDayEntry(entry, $event)"
                      [attr.aria-label]="'Hide ' + entry.title + ' from On this day'"
                      matTooltip="Hide this memory"
                    >
                      <mat-icon>visibility_off</mat-icon>
                    </button>
                  </article>
                  <button
                    *ngIf="shouldShowOnThisDayMoreCard()"
                    type="button"
                    class="calendar-preview-card calendar-preview-card-more"
                    [style.--preview-index]="onThisDayPreview.entries.length"
                    (click)="openOnThisDayFullView($event)"
                    [attr.aria-label]="getOnThisDayMoreLabel()"
                  >
                    <mat-icon>arrow_forward</mat-icon>
                    <span>{{ getOnThisDayMoreLabel() }}</span>
                  </button>
                </div>
              </section>
              <section
                class="calendar-preview-deck"
                *ngIf="calendarPreview"
                [class.preview-left-to-right]="getCalendarPreviewDirection() === 'left-to-right'"
                [class.preview-right-to-left]="getCalendarPreviewDirection() === 'right-to-left'"
                [class.preview-below]="calendarPreview.placement === 'below'"
                [class.preview-above]="calendarPreview.placement === 'above'"
                [class.closing]="calendarPreview.phase === 'closing'"
                [style.top.px]="calendarPreview.top"
                [style.left.px]="calendarPreview.left"
                (click)="$event.stopPropagation()"
                aria-label="Entry preview deck"
              >
                <header class="calendar-preview-header">
                  <div>
                    <strong>{{ getCalendarPreviewHeading() }}</strong>
                    <span>{{ calendarPreview.dateLabel }}</span>
                  </div>
                  <button
                    type="button"
                    class="calendar-preview-close"
                    aria-label="Close preview"
                    (click)="closeCalendarPreview($event)"
                  >
                    <mat-icon>close</mat-icon>
                  </button>
                </header>
                <div class="calendar-preview-cards">
                  <button
                    type="button"
                    class="calendar-preview-card"
                    *ngFor="let entry of getCalendarPreviewEntries(); let previewIndex = index"
                    [style.--preview-index]="previewIndex"
                    [class.has-preview-image]="hasCalendarPreviewImage(entry)"
                    (click)="openEntryDetail(entry, $event)"
                  >
                    <div
                      class="calendar-preview-card-image"
                      *ngIf="hasCalendarPreviewImage(entry)"
                      [style.background-image]="getCalendarPreviewImageStyle(entry)"
                      aria-hidden="true"
                    ></div>
                    <div class="calendar-preview-card-title">
                      <mat-icon>{{
                        entry.type === "dream" ? "nights_stay" : "book"
                      }}</mat-icon>
                      <div>
                        <span>
                          {{ getEntryTitle(entry) }}
                          <mat-icon
                            class="calendar-preview-attachment-indicator"
                            *ngIf="hasEntryAttachments(entry)"
                            aria-hidden="true"
                          >
                            attach_file
                          </mat-icon>
                        </span>
                        <small *ngIf="getEntryTimeLabel(entry)">{{
                          getEntryTimeLabel(entry)
                        }}</small>
                      </div>
                    </div>
                    <div
                      class="calendar-preview-card-tags"
                      *ngIf="getTags(entry).length > 0"
                    >
                      <span
                        class="calendar-preview-tag"
                        *ngFor="let tag of getTags(entry).slice(0, 3)"
                      >
                        {{ tag }}
                      </span>
                    </div>
                    <div class="calendar-preview-card-copy">
                      <div class="calendar-preview-copy-block">
                        <span class="calendar-preview-copy-label">{{
                          getCalendarPreviewPrimaryLabel(entry)
                        }}</span>
                        <p>{{ getCalendarPreviewPrimaryText(entry) }}</p>
                      </div>
                      <div
                        class="calendar-preview-copy-block"
                        *ngIf="getCalendarPreviewSecondaryText(entry)"
                      >
                        <span class="calendar-preview-copy-label">{{
                          getCalendarPreviewSecondaryLabel(entry)
                        }}</span>
                        <p>{{ getCalendarPreviewSecondaryText(entry) }}</p>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="calendar-preview-card calendar-preview-card-more"
                    [style.--preview-index]="getCalendarPreviewEntries().length"
                    (click)="openCalendarPreviewFullView($event)"
                    [attr.aria-label]="getCalendarPreviewMoreLabel()"
                  >
                    <mat-icon>arrow_forward</mat-icon>
                    <span>{{ getCalendarPreviewMoreLabel() }}</span>
                  </button>
                </div>
              </section>
              <section
                id="thought-record-preview"
                class="calendar-preview-deck cbt-preview-deck"
                *ngIf="cbtPreview"
                [class.preview-left-to-right]="cbtPreview.direction === 'left-to-right'"
                [class.preview-right-to-left]="cbtPreview.direction === 'right-to-left'"
                [class.preview-below]="cbtPreview.placement === 'below'"
                [class.preview-above]="cbtPreview.placement === 'above'"
                [class.closing]="cbtPreview.phase === 'closing'"
                [style.top.px]="cbtPreview.top"
                [style.left.px]="cbtPreview.left"
                (click)="$event.stopPropagation()"
                aria-label="Thought record preview deck"
                data-testid="calendar-thought-record-preview"
              >
                <header class="calendar-preview-header">
                  <div>
                    <strong>{{ cbtPreview.heading }}</strong>
                    <span>{{ cbtPreview.dateLabel }}</span>
                  </div>
                  <button
                    type="button"
                    class="calendar-preview-close"
                    aria-label="Close thought record preview"
                    (click)="closeCbtPreview($event)"
                  >
                    <mat-icon>close</mat-icon>
                  </button>
                </header>
                <div class="calendar-preview-cards">
                  <button
                    type="button"
                    class="calendar-preview-card cbt-calendar-preview-card"
                    *ngFor="let record of getCbtPreviewRecords(); let previewIndex = index"
                    [style.--preview-index]="previewIndex"
                    (click)="openThoughtRecord(record, $event)"
                  >
                    <div class="calendar-preview-card-title">
                      <mat-icon>psychology_alt</mat-icon>
                      <div>
                        <span>{{ getThoughtRecordTitle(record) }}</span>
                        <small>{{ getThoughtRecordPreviewMeta(record) }}</small>
                      </div>
                    </div>
                    <div class="calendar-preview-card-copy">
                      <div class="calendar-preview-copy-block">
                        <span class="calendar-preview-copy-label">Situation</span>
                        <p>{{ record.situation || 'No situation added yet.' }}</p>
                      </div>
                      <div class="calendar-preview-copy-block" *ngIf="record.balanced_thought">
                        <span class="calendar-preview-copy-label">Balanced thought</span>
                        <p>{{ record.balanced_thought }}</p>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    class="calendar-preview-card calendar-preview-card-more"
                    [style.--preview-index]="getCbtPreviewRecords().length"
                    (click)="openThoughtRecordsDashboard($event)"
                    aria-label="View all thought records"
                  >
                    <mat-icon>arrow_forward</mat-icon>
                    <span>{{ getCbtPreviewMoreLabel() }}</span>
                  </button>
                </div>
              </section>
              <section
                id="important-day-preview"
                class="calendar-preview-deck important-day-preview-deck"
                *ngIf="importantDayPreview"
                [class.monthly-important-day-preview]="importantDayPreview.scope === 'month'"
                [class.monthly-preview-single]="importantDayPreview.scope === 'month' && importantDayPreview.importantDays.length === 1"
                [class.monthly-preview-double]="importantDayPreview.scope === 'month' && importantDayPreview.importantDays.length === 2"
                [class.preview-left-to-right]="getImportantDayPreviewDirection() === 'left-to-right'"
                [class.preview-right-to-left]="getImportantDayPreviewDirection() === 'right-to-left'"
                [class.preview-below]="importantDayPreview.placement === 'below'"
                [class.preview-above]="importantDayPreview.placement === 'above'"
                [class.closing]="importantDayPreview.phase === 'closing'"
                [style.top.px]="importantDayPreview.top"
                [style.left.px]="importantDayPreview.left"
                (click)="$event.stopPropagation()"
                aria-label="Important day preview deck"
                data-testid="calendar-important-day-preview"
              >
                <header class="calendar-preview-header">
                  <div>
                    <strong>{{ importantDayPreview.heading }}</strong>
                    <span>{{ importantDayPreview.dateLabel }}</span>
                  </div>
                  <button
                    type="button"
                    class="calendar-preview-close"
                    aria-label="Close important day preview"
                    (click)="closeImportantDayPreview($event)"
                  >
                    <mat-icon>close</mat-icon>
                  </button>
                </header>
                <div class="calendar-important-day-preview-cards">
                  <article
                    class="calendar-important-day-card"
                    *ngFor="let importantDay of importantDayPreview.importantDays"
                    [class.has-preview-image]="getImportantDayImageUrl(importantDay)"
                    [ngClass]="'accent-' + importantDay.accent_color"
                  >
                    <div class="calendar-important-day-card-media">
                      <div class="calendar-important-day-card-icon" aria-hidden="true">
                        <mat-icon>{{ getImportantDayIcon(importantDay) }}</mat-icon>
                      </div>
                      <button
                        type="button"
                        class="calendar-important-day-card-thumb"
                        *ngIf="getImportantDayImageUrl(importantDay) as imageUrl"
                        (click)="openImportantDayImage(importantDay, $event)"
                        [attr.aria-label]="'View image for ' + importantDay.label"
                      >
                        <img [src]="imageUrl" alt="" />
                      </button>
                    </div>
                    <div class="calendar-important-day-card-copy">
                      <div class="calendar-important-day-card-heading">
                        <strong>{{ importantDay.label }}</strong>
                        <span>{{ formatImportantDaySummaryLabel(importantDay) }}</span>
                      </div>
                      <p class="calendar-important-day-card-note" *ngIf="importantDay.note">
                        {{ importantDay.note }}
                      </p>
                      <div class="calendar-important-day-card-meta">
                        <span>{{ getImportantDayRecurrenceLabel(importantDay) }}</span>
                        <span>{{ getImportantDayElapsedLabel(importantDay) }}</span>
                        <span>{{ getImportantDayMatchingEntryCountLabel(importantDay) }}</span>
                      </div>
                    </div>
                  </article>
                </div>
              </section>
              <section
                class="calendar-preview-deck important-day-preview-deck"
                *ngIf="occasionPreview"
                [class.preview-left-to-right]="getOccasionPreviewDirection() === 'left-to-right'"
                [class.preview-right-to-left]="getOccasionPreviewDirection() === 'right-to-left'"
                [class.preview-below]="occasionPreview.placement === 'below'"
                [class.preview-above]="occasionPreview.placement === 'above'"
                [class.closing]="occasionPreview.phase === 'closing'"
                [style.top.px]="occasionPreview.top"
                [style.left.px]="occasionPreview.left"
                (click)="$event.stopPropagation()"
                aria-label="Occasion preview deck"
              >
                <header class="calendar-preview-header">
                  <div>
                    <strong>{{ occasionPreview.heading }}</strong>
                    <span>{{ occasionPreview.dateLabel }}</span>
                  </div>
                  <button
                    type="button"
                    class="calendar-preview-close"
                    aria-label="Close occasion preview"
                    (click)="closeOccasionPreview($event)"
                  >
                    <mat-icon>close</mat-icon>
                  </button>
                </header>
                <div class="calendar-important-day-preview-cards">
                  <article
                    class="calendar-important-day-card"
                    *ngFor="let occasion of occasionPreview.occasions"
                    [class.has-preview-image]="occasion.imageUrl"
                    [ngClass]="occasion.accentClass"
                  >
                    <div class="calendar-important-day-card-media">
                      <div class="calendar-important-day-card-icon" aria-hidden="true">
                        <mat-icon>{{ occasion.icon }}</mat-icon>
                      </div>
                      <button
                        type="button"
                        class="calendar-important-day-card-thumb"
                        *ngIf="occasion.imageUrl"
                        (click)="openOccasionImage(occasion, $event)"
                        [attr.aria-label]="'View image for ' + occasion.label"
                      >
                        <img [src]="occasion.imageUrl" alt="" />
                      </button>
                    </div>
                    <div class="calendar-important-day-card-copy">
                      <div class="calendar-important-day-card-heading">
                        <strong>{{ occasion.label }}</strong>
                        <span>{{ occasion.subtitle }}</span>
                      </div>
                      <p class="calendar-important-day-card-note" *ngIf="occasion.note">
                        {{ occasion.note }}
                      </p>
                      <div class="calendar-important-day-card-meta">
                        <span *ngFor="let metaItem of occasion.meta">{{ metaItem }}</span>
                      </div>
                    </div>
                  </article>
                </div>
              </section>
            </section>
          </ng-template>
        </ng-container>
      </ng-container>

      <div
        class="important-day-image-modal"
        *ngIf="importantDayImageModal"
        (click)="closeImportantDayImage()"
        role="dialog"
        aria-modal="true"
        [attr.aria-label]="'Image for ' + importantDayImageModal.label"
        data-testid="important-day-image-modal"
      >
        <div class="important-day-image-modal-dialog" (click)="$event.stopPropagation()">
          <header class="important-day-image-modal-header">
            <div>
              <strong>{{ importantDayImageModal.label }}</strong>
              <span>{{ importantDayImageModal.dateLabel }}</span>
            </div>
            <button
              mat-icon-button
              type="button"
              (click)="closeImportantDayImage()"
              aria-label="Close important day image"
            >
              <mat-icon>close</mat-icon>
            </button>
          </header>
          <div class="important-day-image-modal-body">
            <img [src]="importantDayImageModal.imageUrl" [alt]="importantDayImageModal.label" />
          </div>
          <div class="important-day-image-modal-actions">
            <button mat-stroked-button type="button" (click)="closeImportantDayImage()">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class ListComponent implements OnInit, OnDestroy {
  private entriesService = inject(EntriesService);
  private cbtService = inject(CbtService);
  private importantDaysService = inject(ImportantDaysService);
  private publicHolidaysService = inject(PublicHolidaysService);
  private onThisDayService = inject(OnThisDayService);
  private appDialog = inject(AppDialogService);
  private themeService = inject(ThemeService);
  private authService = inject(AuthService);
  protected readonly searchService = inject(SearchService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  // Timeline properties
  allMonths: TimelineMonth[] = [];
  visibleMonths: TimelineMonth[] = [];
  timelineScrollIndex = 0;
  maxScrollIndex = 0;
  minScrollIndex = 0;
  selectedMonth: TimelineMonth | null = null;

  // Timeline animation properties
  private isAnimating = false;
  private animationFrameId?: number;

  // Pagination properties
  pageSize = 8; // 2 rows of 4 cards
  currentPage = 0;
  totalEntries = 0;
  paginatedEntries: CardItem[] = [];
  displayMode: "cards" | "calendar" = "calendar";
  selectedDay: string | null = null;
  calendarDays: CalendarDay[] = [];
  readonly weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  private readonly displayModeStorageKey = "openmynd.entries.displayMode";
  private readonly legacyDisplayModeStorageKey = "aidiary.entries.displayMode";

  // Current data
  readonly contentFilterOptions: Array<{
    value: ContentFilter;
    label: string;
    icon: string;
  }> = [
    { value: "daily", label: "Diary", icon: "book" },
    { value: "dreams", label: "Dreams", icon: "nights_stay" },
    {
      value: "thought-records",
      label: "Thought records",
      icon: "psychology_alt",
    },
    { value: "important-days", label: "Important days", icon: "event" },
    { value: "on-this-day", label: "On this day", icon: "history" },
  ];
  activeContentFilters = new Set<ContentFilter>([
    "daily",
    "dreams",
    "important-days",
  ]);
  private hasExplicitContentFilters = false;
  isLoadingEntries = false;
  entriesLoadError = "";
  dailyEntries: EntryItem[] = [];
  dreamEntries: EntryItem[] = [];
  thoughtRecords: CbtWorksheet[] = [];
  importantDays: ImportantDay[] = [];
  publicHolidays: PublicHoliday[] = [];
  publicHolidayCountryCode = "";
  publicHolidaysEnabled = false;
  onThisDayFeed: OnThisDayFeed | null = null;
  onThisDayMonthFeed: OnThisDayFeed | null = null;
  private publicHolidaysByYear = new Map<number, PublicHoliday[]>();
  private publicHolidaySettingsLoaded = false;
  private entriesLoadRequestId = 0;
  filteredEntries: CardItem[] = [];
  private hasExplicitMonthSelection = false;
  private pendingMonthSelection: { monthIndex: number; year: number } | null =
    null;
  calendarPreview: CalendarPreviewState | null = null;
  cbtPreview: CbtPreviewState | null = null;
  importantDayPreview: ImportantDayPreviewState | null = null;
  importantDayImageModal: {
    imageUrl: string;
    label: string;
    dateLabel: string;
  } | null = null;
  occasionPreview: OccasionPreviewState | null = null;
  onThisDayPreview: OnThisDayPreviewState | null = null;
  private loadedHolidayYears = new Set<number>();
  private previewCloseTimerId: number | null = null;
  private cbtPreviewCloseTimerId: number | null = null;
  private importantDayPreviewCloseTimerId: number | null = null;
  private occasionPreviewCloseTimerId: number | null = null;
  private onThisDayPreviewCloseTimerId: number | null = null;
  private calendarFlipTimerId: number | null = null;
  private flippedCalendarDays = new Set<string>();
  private ignorePreviewScrollUntil = 0;
  private readonly capturedScrollHandler = (event: Event): void => {
    if (performance.now() < this.ignorePreviewScrollUntil) {
      return;
    }
    const target = event.target;
    if (
      target instanceof Element &&
      target.closest(".calendar-preview-deck")
    ) {
      return;
    }
    this.closeAllCalendarPreviewsImmediately();
  };

  exitSearch(): void {
    this.searchService.clear();
    this.router.navigate(["/entries"], {
      queryParams: this.getListQueryParamsWithoutSearch(),
      replaceUrl: true,
    });
  }

  ngOnInit(): void {
    document.addEventListener("scroll", this.capturedScrollHandler, true);

    // Initialize timeline
    this.initializeTimeline();

    this.route.queryParamMap.subscribe((params) => {
      const type = params.get("type");
      this.applyContentFiltersFromQuery(params.get("show"), type);
      this.displayMode = this.resolveDisplayMode(params.get("display"));

      const monthParam = Number(params.get("month"));
      const yearParam = Number(params.get("year"));
      if (
        Number.isInteger(monthParam) &&
        monthParam >= 1 &&
        monthParam <= 12 &&
        Number.isInteger(yearParam) &&
        yearParam > 0
      ) {
        this.pendingMonthSelection = {
          monthIndex: monthParam - 1,
          year: yearParam,
        };
        this.hasExplicitMonthSelection = true;
      } else if (!params.has("month") && !params.has("year")) {
        this.pendingMonthSelection = null;
        this.hasExplicitMonthSelection = false;
      }

      // Handle search query parameter
      const searchQuery = params.get("search");
      if (searchQuery) {
        this.searchService
          .search(searchQuery, this.parseSearchFilters(params.get("filters")))
          .subscribe({
            next: () => {},
            error: (error) => {
              console.error("Search failed:", error);
            },
          });
      } else {
        this.searchService.clear();
      }

      this.loadEntries();
    });
  }

  initializeTimeline(): void {
    // Wait for entries to load before generating timeline
    // Timeline will be generated in loadEntries() after we have the data
    this.allMonths = [];
    this.visibleMonths = [];
  }

  generateTimelineFromEntries(): void {
    // Get all entries to determine date range
    const allEntries = [
      ...this.dailyEntries,
      ...this.dreamEntries,
      ...this.thoughtRecords.map((record) => ({ entry_date: record.record_date })),
    ];

    if (allEntries.length === 0) {
      // No entries yet, generate basic timeline around current month
      this.allMonths = this.generateBasicTimeline();
    } else {
      // Generate timeline based on actual entry dates
      this.allMonths = this.generateDynamicTimeline(allEntries);
    }

    this.centerTimelineOnCurrentMonth();
    this.updateVisibleMonths();
    this.calculateEntryCountsForTimeline();
  }

  generateBasicTimeline(): TimelineMonth[] {
    const months: TimelineMonth[] = [];
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();

    // Generate 6 months back, current month, and 2 months forward for basic timeline
    for (let i = -6; i <= 2; i++) {
      const date = new Date(currentYear, currentMonth + i, 1);
      const isCurrentMonth = i === 0;
      const isFutureMonth = i > 0;

      const month: TimelineMonth = {
        label: date.toLocaleString("default", { month: "long" }),
        year: date.getFullYear(),
        isCurrent: isCurrentMonth,
        isSelected: isCurrentMonth,
        isFuture: isFutureMonth,
        isActive: !isFutureMonth,
        entryCount: undefined,
      };
      (month as any).monthIndex = date.getMonth();
      months.push(month);
    }

    return months;
  }

  generateDynamicTimeline(entries: any[]): TimelineMonth[] {
    // Find earliest and latest entry dates
    const entryDates = entries.map((e) => new Date(e.entry_date));
    const earliestDate = new Date(
      Math.min(...entryDates.map((d) => d.getTime())),
    );
    const latestDate = new Date(
      Math.max(...entryDates.map((d) => d.getTime())),
    );
    const now = new Date();

    // Determine timeline range - only go 2 months ahead of today
    const startDate = new Date(
      earliestDate.getFullYear(),
      earliestDate.getMonth(),
      1,
    );
    const endDate = new Date(now.getFullYear(), now.getMonth() + 2, 1);

    const months: TimelineMonth[] = [];
    const current = new Date(startDate);

    while (current <= endDate) {
      const isCurrentMonth =
        current.getMonth() === now.getMonth() &&
        current.getFullYear() === now.getFullYear();
      const isFutureMonth = current > now;

      // For future months beyond current month, replace with em-dash
      if (current > now) {
        const month: TimelineMonth = {
          label: "—", // Em-dash instead of month name
          year: current.getFullYear(),
          isCurrent: false,
          isSelected: false,
          isFuture: true,
          isActive: false,
          entryCount: undefined,
        };
        (month as any).monthIndex = current.getMonth();
        (month as any).isEmDash = true; // Flag for styling
        months.push(month);
      } else {
        const month: TimelineMonth = {
          label: current.toLocaleString("default", { month: "long" }),
          year: current.getFullYear(),
          isCurrent: isCurrentMonth,
          isSelected: false,
          isFuture: isFutureMonth,
          isActive: !isFutureMonth,
          entryCount: undefined,
        };
        (month as any).monthIndex = current.getMonth();
        months.push(month);
      }

      // Move to next month
      current.setMonth(current.getMonth() + 1);
    }

    // Preserve existing selection if we already have one, otherwise select current month
    if (this.selectedMonth) {
      // Find the corresponding month in the new timeline and preserve selection
      const existingSelectedMonth = months.find(
        (m) =>
          m.year === this.selectedMonth!.year &&
          (m as any).monthIndex === (this.selectedMonth as any).monthIndex,
      );
      if (existingSelectedMonth) {
        existingSelectedMonth.isSelected = true;
        this.selectedMonth = existingSelectedMonth;
      } else {
        // If previously selected month no longer exists, fallback to current month
        const currentMonth = months.find((m) => m.isCurrent);
        if (currentMonth) {
          currentMonth.isSelected = true;
          this.selectedMonth = currentMonth;
        }
      }
    } else {
      // Initial load - select current month if available
      const currentMonth = months.find((m) => m.isCurrent);
      if (currentMonth) {
        currentMonth.isSelected = true;
        this.selectedMonth = currentMonth;
      } else {
        // Only if current month not available, select earliest month with entries
        const earliestMonth = months.find((m) => !m.isFuture);
        if (earliestMonth) {
          earliestMonth.isSelected = true;
          this.selectedMonth = earliestMonth;
        }
      }
    }

    return months;
  }

  centerTimelineOnCurrentMonth(): void {
    if (this.selectedMonth) {
      const selectedIndex = this.allMonths.findIndex(
        (m) => m === this.selectedMonth,
      );
      this.timelineScrollIndex = Math.max(0, selectedIndex - 2); // Show selected month in center (3rd position)
    } else {
      const currentIndex = this.allMonths.findIndex((m) => m.isCurrent);
      this.timelineScrollIndex = Math.max(0, currentIndex - 2);
    }
    this.updateScrollLimits();
  }

  centerTimelineAnimated(targetIndex: number): void {
    const targetScrollIndex = Math.max(
      0,
      Math.min(targetIndex - 2, this.maxScrollIndex),
    );

    if (this.timelineScrollIndex === targetScrollIndex || this.isAnimating) {
      return; // Already at target or animation in progress
    }

    this.animateToScrollIndex(targetScrollIndex);
  }

  private animateToScrollIndex(targetIndex: number): void {
    if (this.isAnimating) {
      if (this.animationFrameId) {
        cancelAnimationFrame(this.animationFrameId);
      }
    }

    this.isAnimating = true;
    const startIndex = this.timelineScrollIndex;
    const difference = targetIndex - startIndex;
    const duration = 300; // 300ms animation
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function (ease-out)
      const easeOut = 1 - Math.pow(1 - progress, 3);

      this.timelineScrollIndex = Math.round(startIndex + difference * easeOut);
      this.updateVisibleMonths();

      if (progress < 1) {
        this.animationFrameId = requestAnimationFrame(animate);
      } else {
        this.isAnimating = false;
        this.timelineScrollIndex = targetIndex; // Ensure exact final position
        this.updateVisibleMonths();
      }
    };

    this.animationFrameId = requestAnimationFrame(animate);
  }

  updateScrollLimits(): void {
    // Calculate max scroll index (show 5 months at a time)
    this.maxScrollIndex = Math.max(0, this.allMonths.length - 5);

    // Calculate min scroll index based on earliest entry with data
    const activityDates = this.getCalendarActivityDates();
    if (activityDates.length > 0) {
      const earliestDate = new Date(
        Math.min(...activityDates.map((activityDate) => activityDate.getTime())),
      );
      const earliestMonthIndex = this.allMonths.findIndex(
        (m) =>
          m.year === earliestDate.getFullYear() &&
          (m as any).monthIndex === earliestDate.getMonth(),
      );

      // Allow scrolling to show earliest entry month in the center (position 2)
      this.minScrollIndex = Math.max(0, earliestMonthIndex - 2);
    } else {
      this.minScrollIndex = 0;
    }
  }

  updateVisibleMonths(): void {
    this.visibleMonths = this.allMonths.slice(
      this.timelineScrollIndex,
      this.timelineScrollIndex + 5,
    );
  }

  scrollTimeline(direction: number): void {
    const newIndex = this.timelineScrollIndex + direction;
    if (newIndex >= this.minScrollIndex && newIndex <= this.maxScrollIndex) {
      this.timelineScrollIndex = newIndex;
      this.updateVisibleMonths();
    }
  }

  getTimelineMonthAriaLabel(month: TimelineMonth): string {
    const parts = [`${month.label} ${month.year}`];

    if (month.isCurrent) {
      parts.push("current month");
    }
    if (month.isSelected) {
      parts.push("selected");
    }
    if (month.entryCount) {
      parts.push(
        `${month.entryCount} ${month.entryCount === 1 ? "entry" : "entries"}`,
      );
    }
    if (month.isFuture) {
      parts.push("unavailable");
    }

    return parts.join(", ");
  }

  selectMonth(month: TimelineMonth): void {
    // Allow clicking on current month always, block only future months beyond today
    if (month.isFuture) return;

    this.hasExplicitMonthSelection = true;
    this.selectedDay = null;
    this.flippedCalendarDays.clear();

    // Update selection state
    this.allMonths.forEach((m) => (m.isSelected = false));
    month.isSelected = true;
    this.selectedMonth = month;
    this.syncPublicHolidaysForSelectedYear();

    // Update active states - current month is always active, future months remain inactive
    const selectedIndex = this.allMonths.findIndex((m) => m === month);
    const currentIndex = this.allMonths.findIndex((m) => m.isCurrent);

    this.allMonths.forEach((m, index) => {
      // Keep future months inactive, but allow past and current months to be active
      if (index > currentIndex) {
        m.isActive = false; // Future months stay inactive
      } else {
        m.isActive = true; // Past and current months are active
      }
    });

    // Center timeline on selected month with animation if not visible in middle position
    const selectedVisibleIndex = this.visibleMonths.findIndex(
      (m) => m === month,
    );
    if (selectedVisibleIndex === -1 || selectedVisibleIndex !== 2) {
      // Month not visible in center position, animate to center it
      this.centerTimelineAnimated(selectedIndex);
    }

    // Filter entries and reset pagination
    this.filterEntries();
    this.currentPage = 0;
    this.updatePaginatedEntries();
    this.updateListQueryParams();
  }

  loadEntries(): void {
    const requestId = ++this.entriesLoadRequestId;
    this.isLoadingEntries = true;
    this.entriesLoadError = "";
    let hadLoadFailure = false;

    const markLoadFailure = (): void => {
      hadLoadFailure = true;
    };

    forkJoin({
      daily: this.entriesService.getDailyEntries().pipe(
        catchError(() => {
          markLoadFailure();
          return of([]);
        }),
      ),
      dreams: this.entriesService.getDreamEntries().pipe(
        catchError(() => {
          markLoadFailure();
          return of([]);
        }),
      ),
      thoughtRecords: this.cbtService.listWorksheets().pipe(
        catchError(() => {
          markLoadFailure();
          return of([]);
        }),
      ),
      importantDays: this.importantDaysService.getImportantDays().pipe(
        catchError(() => {
          markLoadFailure();
          return of([]);
        }),
      ),
    }).subscribe({
      next: ({ daily, dreams, thoughtRecords, importantDays }) => {
        if (requestId !== this.entriesLoadRequestId) {
          return;
        }

        this.dailyEntries = daily.map((e) => ({ ...e, type: "daily" }));
        this.dreamEntries = dreams.map((e) => ({ ...e, type: "dream" }));
        this.thoughtRecords = thoughtRecords;
        this.importantDays = importantDays;

        this.entriesLoadError = hadLoadFailure
          ? "Some journal data is temporarily unavailable. Retry once the connection settles."
          : "";
        this.generateTimelineFromEntries();
        this.applyInitialMonthSelection();
        this.syncPublicHolidaysForSelectedYear();
        this.filterEntries();
        this.updatePaginatedEntries();
        this.isLoadingEntries = false;
        this.loadOnThisDayFeed(requestId);
      },
      error: () => {
        if (requestId !== this.entriesLoadRequestId) {
          return;
        }
        this.dailyEntries = [];
        this.dreamEntries = [];
        this.thoughtRecords = [];
        this.importantDays = [];
        this.publicHolidays = [];
        this.publicHolidaysEnabled = false;
        this.publicHolidayCountryCode = "";
        this.publicHolidaysByYear.clear();
        this.loadedHolidayYears.clear();
        this.onThisDayFeed = null;
        this.syncOnThisDayFilterAvailability(false);
        this.entriesLoadError =
          "Some journal data is temporarily unavailable. Retry once the connection settles.";
        this.generateTimelineFromEntries();
        this.applyInitialMonthSelection();
        this.filterEntries();
        this.updatePaginatedEntries();
        this.isLoadingEntries = false;
        this.loadOnThisDayFeed(requestId);
      },
    });
  }

  isContentFilterActive(filter: ContentFilter): boolean {
    return this.activeContentFilters.has(filter);
  }

  isContentFilterDisabled(filter: ContentFilter): boolean {
    return filter === "on-this-day" && !this.isOnThisDayEnabled();
  }

  setContentFilter(filter: ContentFilter, selected: boolean): void {
    if (this.isContentFilterDisabled(filter)) return;

    this.closeCalendarPreview();
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);
    const next = new Set(this.activeContentFilters);
    if (selected) {
      next.add(filter);
    } else {
      next.delete(filter);
    }
    this.activeContentFilters = next;
    this.hasExplicitContentFilters = true;
    this.selectedDay = null;

    this.filterEntries();
    this.currentPage = 0;
    this.updatePaginatedEntries();
    this.updateListQueryParams();
  }

  navigateToCreateEntry(): void {
    this.navigateToCreateEntryForDate(this.getCreateTargetDate());
  }

  setDisplayMode(mode: "cards" | "calendar"): void {
    this.closeCalendarPreview();
    this.closeCbtPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.displayMode = mode;
    this.persistDisplayMode(mode);
    if (mode === "calendar") {
      this.selectedDay = null;
      this.filterEntries();
      this.currentPage = 0;
      this.updatePaginatedEntries();
    }
    this.updateListQueryParams();
  }

  clearSelectedDay(): void {
    this.closeCalendarPreview();
    this.closeCbtPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.selectedDay = null;
    this.displayMode = "calendar";
    this.persistDisplayMode("calendar");
    this.filterEntries();
    this.currentPage = 0;
    this.updatePaginatedEntries();
  }

  private resolveDisplayMode(
    displayParam: string | null,
  ): "cards" | "calendar" {
    if (displayParam === "cards" || displayParam === "calendar") {
      this.persistDisplayMode(displayParam);
      return displayParam;
    }

    return this.getPersistedDisplayMode();
  }

  private getPersistedDisplayMode(): "cards" | "calendar" {
    try {
      const savedMode =
        window.localStorage.getItem(this.displayModeStorageKey) ??
        window.localStorage.getItem(this.legacyDisplayModeStorageKey);
      if (savedMode === "cards" || savedMode === "calendar") {
        this.persistDisplayMode(savedMode);
        window.localStorage.removeItem(this.legacyDisplayModeStorageKey);
        return savedMode;
      }
      return "calendar";
    } catch {
      return "calendar";
    }
  }

  private persistDisplayMode(mode: "cards" | "calendar"): void {
    try {
      window.localStorage.setItem(this.displayModeStorageKey, mode);
    } catch {
      // Storage can be unavailable in private browsing or locked-down contexts.
    }
  }

  getSelectedDayLabel(): string {
    if (!this.selectedDay) {
      return "";
    }

    const date = new Date(`${this.selectedDay}T12:00:00`);
    return date.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  getCalendarHeading(): string {
    if (!this.selectedMonth) {
      return "Current month";
    }

    return `${this.selectedMonth.label} ${this.selectedMonth.year}`;
  }

  getCalendarStatusLabel(status: CalendarStatus): string {
    if (status === "daily") {
      return "Daily";
    }
    if (status === "dream") {
      return "Dream";
    }
    if (status === "complete") {
      return "Complete";
    }
    return "Open";
  }

  getCalendarDayDateLabel(day: CalendarDay): string {
    return day.date.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  getCalendarDayLabel(day: CalendarDay): string {
    const dateLabel = this.getCalendarDayDateLabel(day);
    const statusLabel = this.getCalendarStatusLabel(day.status);
    const entryCountLabel =
      day.entries.length > 0
        ? `${day.entries.length} entr${day.entries.length === 1 ? "y" : "ies"}`
        : "no entries";
    const thoughtRecordLabel =
      day.thoughtRecords.length > 0
        ? ` ${day.thoughtRecords.length} thought record${day.thoughtRecords.length === 1 ? "" : "s"}.`
        : "";
    const importantDayLabel =
      day.importantDays.length > 0
        ? ` Important day${day.importantDays.length === 1 ? "" : "s"}: ${day.importantDays
            .map((importantDay) => importantDay.label)
            .join(", ")}.`
        : "";
    const publicHolidayLabel =
      day.publicHolidays.length > 0
        ? ` Public holiday${day.publicHolidays.length === 1 ? "" : "s"}: ${day.publicHolidays
            .map((holiday) => holiday.localName || holiday.name)
            .join(", ")}.`
        : "";
    const hiddenLabel =
      day.hiddenItemCount > 0 ? ` ${day.hiddenItemLabel}.` : "";

    return `${dateLabel}. ${statusLabel}. ${entryCountLabel}.${thoughtRecordLabel}${importantDayLabel}${publicHolidayLabel}${hiddenLabel}`;
  }

  getCurrentMonthImportantDays(): ImportantDay[] {
    if (
      !this.selectedMonth ||
      !this.isContentFilterActive("important-days")
    ) {
      return [];
    }

    return this.importantDays
      .filter((importantDay) => {
        if (importantDay.month !== (this.selectedMonth as any).monthIndex + 1) {
          return false;
        }

        if (importantDay.recurrence === "once") {
          return importantDay.original_year === this.selectedMonth?.year;
        }

        return (
          !importantDay.original_year ||
          importantDay.original_year <= this.selectedMonth!.year
        );
      })
      .sort((left, right) => {
        if (left.day !== right.day) {
          return left.day - right.day;
        }
        return left.label.localeCompare(right.label);
      });
  }

  getCurrentMonthImportantDaysSummaryLabel(): string {
    const count = this.getCurrentMonthImportantDays().length;
    return `${count} important ${count === 1 ? "date" : "dates"}`;
  }

  getSelectedDayImportantDays(): ImportantDay[] {
    if (
      !this.selectedDay ||
      !this.isContentFilterActive("important-days")
    ) {
      return [];
    }

    const [yearText, monthText, dayText] = this.selectedDay.split("-");
    const month = Number(monthText);
    const day = Number(dayText);
    if (!yearText || Number.isNaN(month) || Number.isNaN(day)) {
      return [];
    }

    return this.importantDays.filter(
      (importantDay) => importantDay.month === month && importantDay.day === day,
    );
  }

  getSelectedDayPublicHolidays(): PublicHoliday[] {
    if (!this.selectedDay) {
      return [];
    }

    const [yearText] = this.selectedDay.split("-");
    const year = Number(yearText);
    const holidaysForYear =
      this.publicHolidaysByYear.get(year) ?? this.publicHolidays;
    return holidaysForYear.filter((holiday) => holiday.date === this.selectedDay);
  }

  getImportantDayAriaLabel(day: CalendarDay): string {
    return `Important day${day.importantDays.length === 1 ? "" : "s"}: ${day.importantDays
      .map((importantDay) => importantDay.label)
      .join(", ")}`;
  }

  getImportantDayIcon(importantDay: ImportantDay): string {
    return importantDay.icon_name || "event";
  }

  formatImportantDaySummaryLabel(importantDay: ImportantDay): string {
    const year =
      importantDay.recurrence === "once"
        ? importantDay.original_year || 2024
        : 2024;
    const date = new Date(year, importantDay.month - 1, importantDay.day);
    const dateLabel = date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    });
    return importantDay.recurrence === "once" && importantDay.original_year
      ? `${dateLabel} ${importantDay.original_year}`
      : dateLabel;
  }

  getImportantDayRecurrenceLabel(importantDay: ImportantDay): string {
    return importantDay.recurrence === "once"
      ? "One-time date"
      : "Repeats yearly";
  }

  getImportantDayElapsedLabel(importantDay: ImportantDay): string {
    if (
      !importantDay.original_year ||
      !this.selectedMonth ||
      importantDay.original_year > this.selectedMonth.year
    ) {
      return "No elapsed years yet";
    }

    const yearsElapsed = this.selectedMonth.year - importantDay.original_year;
    if (yearsElapsed <= 0) {
      return "First year";
    }

    return `${yearsElapsed} year${yearsElapsed === 1 ? "" : "s"} since`;
  }

  getImportantDayMatchingEntryCountLabel(importantDay: ImportantDay): string {
    if (!this.selectedMonth) {
      return "No linked entries";
    }

    const matchingEntries = [...this.dailyEntries, ...this.dreamEntries].filter((entry) => {
      const entryDate = new Date(entry.entry_date);
      return (
        entryDate.getFullYear() === this.selectedMonth!.year &&
        entryDate.getMonth() + 1 === importantDay.month &&
        entryDate.getDate() === importantDay.day
      );
    });

    return `${matchingEntries.length} entr${matchingEntries.length === 1 ? "y" : "ies"} on this date`;
  }

  openImportantDayImage(importantDay: ImportantDay, event: Event): void {
    event.stopPropagation();
    const imageUrl = this.getImportantDayImageUrl(importantDay);
    if (!imageUrl) return;
    this.importantDayImageModal = {
      imageUrl,
      label: importantDay.label,
      dateLabel: this.formatImportantDaySummaryLabel(importantDay),
    };
  }

  openOccasionImage(occasion: OccasionPreviewItem, event: Event): void {
    event.stopPropagation();
    const imageUrl = String(occasion.imageUrl || "").trim();
    if (!imageUrl) return;
    this.importantDayImageModal = {
      imageUrl,
      label: occasion.label,
      dateLabel: occasion.subtitle,
    };
  }

  closeImportantDayImage(): void {
    this.importantDayImageModal = null;
  }

  getImportantDayImageUrl(importantDay: ImportantDay): string | null {
    const imageUrl = String(importantDay.image_url || "").trim();
    return imageUrl || null;
  }

  toggleMonthlyImportantDaysPreview(event: MouseEvent): void {
    event.stopPropagation();
    this.ignorePreviewScrollUntil = performance.now() + 250;
    const importantDays = this.getCurrentMonthImportantDays();
    if (!this.selectedMonth || importantDays.length === 0) return;

    const previewKey = `month:${this.selectedMonth.year}:${(this.selectedMonth as any).monthIndex}`;
    if (
      this.importantDayPreview?.dayKey === previewKey &&
      this.importantDayPreview.phase === "open"
    ) {
      this.closeImportantDayPreview();
      return;
    }

    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);
    if (this.importantDayPreviewCloseTimerId) {
      window.clearTimeout(this.importantDayPreviewCloseTimerId);
      this.importantDayPreviewCloseTimerId = null;
    }

    const anchor = event.currentTarget as HTMLElement;
    const position = this.getCalendarPreviewPosition(
      anchor,
      Math.min(importantDays.length, 3),
    );
    this.importantDayPreview = {
      dayKey: previewKey,
      scope: "month",
      heading: "Important days this month",
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      importantDays,
      dateLabel: this.getCalendarHeading(),
      top: position.top,
      left: position.left,
      placement: position.placement,
    };
  }

  getVisibleDayImportantDays(day: CalendarDay): ImportantDay[] {
    return day.importantDays.slice(0, 2);
  }

  getCompactImportantDayBadgeText(importantDay: ImportantDay): string {
    return this.truncatePreviewText(importantDay.label, 14);
  }

  getCurrentMonthPublicHolidays(): PublicHoliday[] {
    if (!this.selectedMonth || !this.publicHolidaysEnabled) {
      return [];
    }

    const holidaysForYear =
      this.publicHolidaysByYear.get(this.selectedMonth.year) ?? this.publicHolidays;

    return holidaysForYear
      .filter((holiday) => {
        const holidayDate = new Date(`${holiday.date}T12:00:00`);
        return (
          holidayDate.getMonth() === (this.selectedMonth as any).monthIndex &&
          holidayDate.getFullYear() === this.selectedMonth!.year
        );
      })
      .sort((left, right) => left.date.localeCompare(right.date));
  }

  formatPublicHolidaySummaryLabel(holiday: PublicHoliday): string {
    const date = new Date(`${holiday.date}T12:00:00`);
    const dateLabel = date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    });
    return `${dateLabel} ${holiday.localName || holiday.name}`;
  }

  getPublicHolidayIcon(_holiday: PublicHoliday): string {
    return "flag";
  }

  truncatePublicHolidayLabel(holiday: PublicHoliday): string {
    return this.truncatePreviewText(holiday.localName || holiday.name, 14);
  }

  isHolidayLeadingOccasion(day: CalendarDay): boolean {
    return day.importantDays.length === 0 && day.publicHolidays.length > 0;
  }

  hasDayOccasions(day: CalendarDay): boolean {
    return day.importantDays.length > 0 || day.publicHolidays.length > 0;
  }

  getDayOccasionCount(day: CalendarDay): number {
    return day.importantDays.length + day.publicHolidays.length;
  }

  getOccasionAriaLabel(day: CalendarDay): string {
    const labels = [
      ...day.importantDays.map((importantDay) => importantDay.label),
      ...day.publicHolidays.map((holiday) => holiday.localName || holiday.name),
    ];
    return `Occasions: ${labels.join(", ")}`;
  }

  getOccasionTriggerIcon(day: CalendarDay): string {
    return day.importantDays[0]
      ? this.getImportantDayIcon(day.importantDays[0])
      : this.getPublicHolidayIcon(day.publicHolidays[0]);
  }

  getOccasionTooltip(day: CalendarDay): string {
    const importantLabels = day.importantDays.map((importantDay) => importantDay.label);
    const holidayLabels = day.publicHolidays.map(
      (holiday) => holiday.localName || holiday.name,
    );
    const labels = [...importantLabels, ...holidayLabels];
    if (labels.length === 0) {
      return "";
    }
    return labels.length === 1
      ? labels[0]
      : `${labels[0]} and ${labels.length - 1} more`;
  }

  getImportantDayPreviewDirection(): "left-to-right" | "right-to-left" {
    return this.importantDayPreview?.direction ?? "left-to-right";
  }

  toggleImportantDayPreview(day: CalendarDay, event: MouseEvent): void {
    event.stopPropagation();
    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);

    if (!day.isCurrentMonth || day.importantDays.length === 0) {
      return;
    }

    const dayKey = this.toDateKey(day.date);
    if (
      this.importantDayPreview?.dayKey === dayKey &&
      this.importantDayPreview.phase === "open"
    ) {
      this.closeImportantDayPreview();
      return;
    }

    if (this.importantDayPreviewCloseTimerId) {
      window.clearTimeout(this.importantDayPreviewCloseTimerId);
      this.importantDayPreviewCloseTimerId = null;
    }

    const overlayPosition = this.getCalendarPreviewPosition(
      event.currentTarget as HTMLElement,
      Math.min(day.importantDays.length, 3),
    );

    this.importantDayPreview = {
      dayKey,
      scope: "day",
      heading: "Important days",
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      importantDays: day.importantDays,
      dateLabel: this.getCalendarDayDateLabel(day),
      top: overlayPosition.top,
      left: overlayPosition.left,
      placement: overlayPosition.placement,
    };
  }

  onOccasionBadgeKeydown(
    event: Event,
    day: CalendarDay,
    anchorElement: HTMLElement,
  ): void {
    event.preventDefault();
    event.stopPropagation();
    this.toggleOccasionPreview(day, anchorElement, event);
  }

  getVisibleDayOccasionBadges(
    day: CalendarDay,
  ): Array<{ label: string; accentClass: string }> {
    const importantBadges = day.importantDays.map((importantDay) => ({
      label: this.truncatePreviewText(importantDay.label, 14),
      accentClass: `accent-${importantDay.accent_color}`,
    }));
    const holidayBadges = day.publicHolidays.map((holiday) => ({
      label: this.truncatePreviewText(holiday.localName || holiday.name, 14),
      accentClass: "holiday-chip",
    }));

    if (importantBadges.length > 0 && holidayBadges.length > 0) {
      return [importantBadges[0], holidayBadges[0]];
    }

    return [...importantBadges, ...holidayBadges].slice(0, 2);
  }

  getOccasionPreviewHeading(day: CalendarDay): string {
    if (day.importantDays.length > 0 && day.publicHolidays.length > 0) {
      return "Important days and holidays";
    }
    if (day.publicHolidays.length > 0) {
      return "Public holidays";
    }
    return "Important days";
  }

  getOccasionPreviewItems(day: CalendarDay): OccasionPreviewItem[] {
    const importantItems = day.importantDays.map((importantDay) => ({
      kind: "important" as const,
      label: importantDay.label,
      subtitle: this.formatImportantDaySummaryLabel(importantDay),
      note: importantDay.note,
      meta: [
        this.getImportantDayRecurrenceLabel(importantDay),
        this.getImportantDayElapsedLabel(importantDay),
        this.getImportantDayMatchingEntryCountLabel(importantDay),
      ],
      icon: this.getImportantDayIcon(importantDay),
      accentClass: `accent-${importantDay.accent_color}`,
      imageUrl: this.getImportantDayImageUrl(importantDay),
    }));

    const holidayItems = day.publicHolidays.map((holiday) => ({
      kind: "holiday" as const,
      label: holiday.localName || holiday.name,
      subtitle: new Date(`${holiday.date}T12:00:00`).toLocaleDateString("en-GB", {
        weekday: "short",
        day: "numeric",
        month: "short",
      }),
      note:
        holiday.localName && holiday.localName !== holiday.name
          ? holiday.name
          : undefined,
      meta: [
        `Country: ${holiday.countryCode}`,
        holiday.global ? "National holiday" : "Regional holiday",
        ...(holiday.types || []).slice(0, 2),
      ],
      icon: this.getPublicHolidayIcon(holiday),
      accentClass: "holiday-card",
    }));

    return [...importantItems, ...holidayItems];
  }

  getEntryCountByType(day: CalendarDay, type: "daily" | "dream"): number {
    return day.entries.filter((entry) => entry.type === type).length;
  }

  getThoughtRecordTitle(record: CbtWorksheet): string {
    return record.title || record.situation || "Untitled thought record";
  }

  getThoughtRecordPreviewMeta(record: CbtWorksheet): string {
    const date = new Date(`${record.record_date}T12:00:00`).toLocaleDateString(
      "en-GB",
      { day: "numeric", month: "long", year: "numeric" },
    );
    const status =
      record.status === "completed"
        ? "Completed"
        : `Draft · Step ${record.current_step} of 7`;
    return `${date} · ${status}`;
  }

  getCbtPreviewRecords(): CbtWorksheet[] {
    return this.cbtPreview?.records ?? [];
  }

  getCbtPreviewMoreLabel(): string {
    return (this.cbtPreview?.totalCount ?? 0) > 3
      ? "View all records"
      : "Thought records";
  }

  isCbtPreviewActive(day: CalendarDay): boolean {
    return (
      this.cbtPreview?.dayKey === this.toDateKey(day.date) &&
      this.cbtPreview.phase === "open"
    );
  }

  toggleCbtPreview(day: CalendarDay, event: MouseEvent): void {
    event.stopPropagation();
    this.closeCalendarPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);

    if (!day.isCurrentMonth || day.thoughtRecords.length === 0) return;

    const dayKey = this.toDateKey(day.date);
    if (
      this.cbtPreview?.dayKey === dayKey &&
      this.cbtPreview.phase === "open"
    ) {
      this.closeCbtPreview();
      return;
    }

    if (this.cbtPreviewCloseTimerId) {
      window.clearTimeout(this.cbtPreviewCloseTimerId);
      this.cbtPreviewCloseTimerId = null;
    }

    const records = day.thoughtRecords.slice(0, 3);
    const overlayPosition = this.getCalendarPreviewPosition(
      event.currentTarget as HTMLElement,
      records.length,
    );
    this.cbtPreview = {
      dayKey,
      heading: "Thought records",
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      records,
      totalCount: day.thoughtRecords.length,
      dateLabel: this.getCalendarDayDateLabel(day),
      top: overlayPosition.top,
      left: overlayPosition.left,
      placement: overlayPosition.placement,
    };
  }

  getCurrentMonthThoughtRecords(): CbtWorksheet[] {
    if (
      !this.selectedMonth ||
      !this.isContentFilterActive("thought-records")
    ) {
      return [];
    }
    return this.thoughtRecords.filter((record) => {
      const date = new Date(`${record.record_date}T12:00:00`);
      return (
        date.getMonth() === (this.selectedMonth as any).monthIndex &&
        date.getFullYear() === this.selectedMonth!.year
      );
    });
  }

  getCurrentMonthThoughtRecordsKey(): string {
    if (!this.selectedMonth) return "thought-records:month";
    return `thought-records:${this.selectedMonth.year}-${(this.selectedMonth as any).monthIndex + 1}`;
  }

  getCurrentMonthThoughtRecordsSummaryLabel(): string {
    const count = this.getCurrentMonthThoughtRecords().length;
    return `${count} ${count === 1 ? "record" : "records"}`;
  }

  toggleMonthlyCbtPreview(event: MouseEvent): void {
    event.stopPropagation();
    this.ignorePreviewScrollUntil = performance.now() + 250;
    const records = this.getCurrentMonthThoughtRecords();
    if (!records.length) return;

    const monthKey = this.getCurrentMonthThoughtRecordsKey();
    if (this.cbtPreview?.dayKey === monthKey && this.cbtPreview.phase === "open") {
      this.closeCbtPreview();
      return;
    }

    this.closeCalendarPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);
    if (this.cbtPreviewCloseTimerId) {
      window.clearTimeout(this.cbtPreviewCloseTimerId);
      this.cbtPreviewCloseTimerId = null;
    }

    const visibleRecords = records.slice(0, 3);
    const position = this.getCalendarPreviewPosition(
      event.currentTarget as HTMLElement,
      visibleRecords.length,
    );
    this.cbtPreview = {
      dayKey: monthKey,
      heading: "Thought records this month",
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      records: visibleRecords,
      totalCount: records.length,
      dateLabel: this.getCalendarHeading(),
      top: position.top,
      left: position.left,
      placement: position.placement,
    };
  }

  openThoughtRecord(record: CbtWorksheet, event?: Event): void {
    event?.stopPropagation();
    this.closeCbtPreview(undefined, true);
    const queryParams: Record<string, string | number> = {
      returnTo: this.displayMode === "calendar" ? "calendar" : "entries",
      display: this.displayMode,
      show: this.getSerialisedContentFilters(),
    };
    if (this.selectedMonth) {
      queryParams["month"] = (this.selectedMonth as any).monthIndex + 1;
      queryParams["year"] = this.selectedMonth.year;
    }
    void this.router.navigate(["/cbt", record.id], { queryParams });
  }

  openThoughtRecordsDashboard(event?: Event): void {
    event?.stopPropagation();
    this.closeCbtPreview(undefined, true);
    void this.router.navigate(["/cbt"]);
  }

  getCalendarPreviewEntries(): EntryItem[] {
    return this.calendarPreview?.entries ?? [];
  }

  getCalendarPreviewHeading(): string {
    if (!this.calendarPreview) {
      return "Entries";
    }

    const count = this.calendarPreview.totalCount;
    const typeLabel = this.calendarPreview.type === "daily" ? "Daily" : "Dream";
    return `${typeLabel} entr${count === 1 ? "y" : "ies"}`;
  }

  getCalendarPreviewMoreLabel(): string {
    return "View more";
  }

  getCalendarPreviewDirection(): "left-to-right" | "right-to-left" {
    return this.calendarPreview?.direction ?? "left-to-right";
  }

  isCalendarPreviewActive(day: CalendarDay, type: CalendarPreviewType): boolean {
    return (
      this.calendarPreview?.dayKey === this.toDateKey(day.date) &&
      this.calendarPreview.type === type &&
      this.calendarPreview.phase === "open"
    );
  }

  onCalendarDaySelect(day: CalendarDay, event?: Event): void {
    const target = this.getEventTargetElement(event);
    if (
      target?.closest(
        ".calendar-important-day-badge, .calendar-entry-icon",
      )
    ) {
      return;
    }

    this.closeCalendarPreview();
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);
    if (!day.isCurrentMonth) {
      return;
    }

    if (day.isFuture) {
      return;
    }

    if (day.entries.length === 0) {
      this.navigateToCreateEntryForDate(day.date);
      return;
    }

    this.selectedDay = this.toDateKey(day.date);
    this.displayMode = "cards";
    this.currentPage = 0;
    this.filterEntries();
    this.updatePaginatedEntries();
  }

  getOccasionPreviewDirection(): "left-to-right" | "right-to-left" {
    return this.occasionPreview?.direction ?? "left-to-right";
  }

  toggleOccasionPreview(
    day: CalendarDay,
    anchorElement: HTMLElement,
    event: Event,
  ): void {
    event.stopPropagation();
    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);

    if (!day.isCurrentMonth || !this.hasDayOccasions(day)) {
      return;
    }

    const dayKey = this.toDateKey(day.date);
    if (
      this.occasionPreview?.dayKey === dayKey &&
      this.occasionPreview.phase === "open"
    ) {
      this.closeOccasionPreview();
      return;
    }

    if (this.occasionPreviewCloseTimerId) {
      window.clearTimeout(this.occasionPreviewCloseTimerId);
      this.occasionPreviewCloseTimerId = null;
    }

    const overlayPosition = this.getCalendarPreviewPosition(
      anchorElement,
      Math.min(this.getDayOccasionCount(day), 3),
    );

    this.occasionPreview = {
      dayKey,
      phase: "open",
      direction: this.getPreviewDirectionFromEvent(event as MouseEvent | KeyboardEvent, anchorElement),
      heading: this.getOccasionPreviewHeading(day),
      occasions: this.getOccasionPreviewItems(day),
      dateLabel: this.getCalendarDayDateLabel(day),
      top: overlayPosition.top,
      left: overlayPosition.left,
      placement: overlayPosition.placement,
    };
  }

  togglePublicHolidayPreview(day: CalendarDay, event: MouseEvent): void {
    event.stopPropagation();
    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);

    if (!day.isCurrentMonth || day.publicHolidays.length === 0) {
      return;
    }

    const dayKey = `${this.toDateKey(day.date)}:holiday`;
    if (
      this.occasionPreview?.dayKey === dayKey &&
      this.occasionPreview.phase === "open"
    ) {
      this.closeOccasionPreview();
      return;
    }

    if (this.occasionPreviewCloseTimerId) {
      window.clearTimeout(this.occasionPreviewCloseTimerId);
      this.occasionPreviewCloseTimerId = null;
    }

    const anchor = event.currentTarget as HTMLElement;
    const overlayPosition = this.getCalendarPreviewPosition(
      anchor,
      Math.min(day.publicHolidays.length, 3),
    );
    this.occasionPreview = {
      dayKey,
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      heading: "Public holidays",
      occasions: this.getOccasionPreviewItems(day).filter(
        (occasion) => occasion.kind === "holiday",
      ),
      dateLabel: this.getCalendarDayDateLabel(day),
      top: overlayPosition.top,
      left: overlayPosition.left,
      placement: overlayPosition.placement,
    };
  }

  openCalendarPreviewFullView(event: Event): void {
    event.stopPropagation();

    if (!this.calendarPreview) {
      return;
    }

    const selectedType: ContentFilter =
      this.calendarPreview.type === "daily" ? "daily" : "dreams";
    const next = new Set(this.activeContentFilters);
    next.delete("daily");
    next.delete("dreams");
    next.delete("thought-records");
    next.add(selectedType);
    this.activeContentFilters = next;
    this.hasExplicitContentFilters = true;
    this.selectedDay = this.calendarPreview.dayKey;
    this.displayMode = "cards";
    this.currentPage = 0;
    this.closeCalendarPreview(undefined, true);
    this.filterEntries();
    this.updatePaginatedEntries();
    this.updateListQueryParams();
  }

  toggleCalendarPreview(
    day: CalendarDay,
    type: CalendarPreviewType,
    event: MouseEvent,
  ): void {
    event.stopPropagation();
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);

    if (!day.isCurrentMonth || day.isFuture) {
      return;
    }

    const dayKey = this.toDateKey(day.date);
    const isSamePreview =
      this.calendarPreview?.dayKey === dayKey && this.calendarPreview.type === type;

    if (isSamePreview && this.calendarPreview?.phase === "open") {
      this.closeCalendarPreview();
      return;
    }

    if (this.previewCloseTimerId) {
      window.clearTimeout(this.previewCloseTimerId);
      this.previewCloseTimerId = null;
    }

    const typedEntries = day.entries.filter((entry) => entry.type === type);
    const deckEntries = typedEntries.slice(0, 3);
    const overlayPosition = this.getCalendarPreviewPosition(
      event.currentTarget as HTMLElement,
      deckEntries.length,
    );

    this.calendarPreview = {
      dayKey,
      type,
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      entries: deckEntries,
      totalCount: typedEntries.length,
      dateLabel: this.getCalendarDayDateLabel(day),
      top: overlayPosition.top,
      left: overlayPosition.left,
      placement: overlayPosition.placement,
    };
  }

  private getCreateTargetDate(): Date {
    if (this.selectedDay) {
      return new Date(`${this.selectedDay}T12:00:00`);
    }

    // Calculate the appropriate date based on selected month
    let targetDate: Date;
    const today = new Date();

    if (this.selectedMonth) {
      // If selected month is current month, use today's exact date
      if (this.selectedMonth.isCurrent) {
        targetDate = today;
      } else {
        // Use first day of selected month with today's day if possible
        const selectedMonthIndex = (this.selectedMonth as any).monthIndex;
        const selectedYear = this.selectedMonth.year;
        const todayDay = today.getDate();

        // Try to use today's day, but ensure it's valid for the selected month
        const daysInSelectedMonth = new Date(
          selectedYear,
          selectedMonthIndex + 1,
          0,
        ).getDate();
        const dayToUse = Math.min(todayDay, daysInSelectedMonth);

        targetDate = new Date(selectedYear, selectedMonthIndex, dayToUse);
      }
    } else {
      // Fallback to today's date
      targetDate = today;
    }

    return targetDate;
  }

  private navigateToCreateEntryForDate(targetDate: Date): void {
    // Format date as DD/MM/YYYY for UK format
    const day = targetDate.getDate().toString().padStart(2, "0");
    const month = (targetDate.getMonth() + 1).toString().padStart(2, "0");
    const year = targetDate.getFullYear();
    const formattedDate = `${day}/${month}/${year}`;

    // Navigate to create entry with pre-populated date and type
    const queryParams: any = {
      date: formattedDate,
      display: this.displayMode,
      month: targetDate.getMonth() + 1,
      year: targetDate.getFullYear(),
    };

    // Prefer the only selected entry type; otherwise use the Daily default.
    if (
      this.isContentFilterActive("dreams") &&
      !this.isContentFilterActive("daily")
    ) {
      queryParams.type = "dream";
    } else {
      queryParams.type = "daily";
    }
    queryParams.show = this.getSerialisedContentFilters();

    this.router.navigate(["/entries/create"], {
      queryParams,
    });
  }

  resetToCurrentMonth(): void {
    this.flippedCalendarDays.clear();
    // Clear previous selection
    this.allMonths.forEach((m) => (m.isSelected = false));

    // Select current month
    const currentMonth = this.allMonths.find((m) => m.isCurrent);
    if (currentMonth) {
      currentMonth.isSelected = true;
      this.selectedMonth = currentMonth;
      this.syncPublicHolidaysForSelectedYear();

      // Center timeline on current month
      const currentIndex = this.allMonths.findIndex((m) => m.isCurrent);
      this.timelineScrollIndex = Math.max(
        0,
        Math.min(currentIndex - 2, this.maxScrollIndex),
      );
      this.updateVisibleMonths();
    }
  }

  hasEntries(): boolean {
    return this.getFilteredActivityItems().length > 0;
  }

  getEmptyStateHeading(): string {
    return this.activeContentFilters.size === 0
      ? "No content selected"
      : "No entries found";
  }

  getEmptyStateMessage(): string {
    return this.activeContentFilters.size === 0
      ? "Choose one or more content filters to show entries."
      : "No matching entries for this time period.";
  }

  jumpToFirstEntry(): void {
    const activityDates = this.getCalendarActivityDates();
    if (activityDates.length === 0) return;

    const earliestDate = new Date(
      Math.min(...activityDates.map((activityDate) => activityDate.getTime())),
    );

    // Find corresponding month in timeline
    const earliestMonth = this.allMonths.find(
      (m) =>
        m.year === earliestDate.getFullYear() &&
        (m as any).monthIndex === earliestDate.getMonth(),
    );

    if (earliestMonth) {
      this.hasExplicitMonthSelection = true;
      this.selectedDay = null;

      // Update selection state
      this.allMonths.forEach((m) => (m.isSelected = false));
      earliestMonth.isSelected = true;
      this.selectedMonth = earliestMonth;
      this.syncPublicHolidaysForSelectedYear();

      // Center timeline on earliest month with animation
      const earliestIndex = this.allMonths.findIndex(
        (m) => m === earliestMonth,
      );
      this.centerTimelineAnimated(earliestIndex);

      // Filter entries and reset pagination
      this.filterEntries();
      this.currentPage = 0;
      this.updatePaginatedEntries();
      this.updateListQueryParams();
    }
  }

  jumpToToday(): void {
    // Find current month in timeline
    const currentMonth = this.allMonths.find((m) => m.isCurrent);
    if (currentMonth) {
      this.hasExplicitMonthSelection = true;
      this.selectedDay = null;

      // Update selection state
      this.allMonths.forEach((m) => (m.isSelected = false));
      currentMonth.isSelected = true;
      this.selectedMonth = currentMonth;
      this.syncPublicHolidaysForSelectedYear();

      // Center timeline on current month with animation
      const currentIndex = this.allMonths.findIndex((m) => m === currentMonth);
      this.centerTimelineAnimated(currentIndex);

      // Filter entries and reset pagination
      this.filterEntries();
      this.currentPage = 0;
      this.updatePaginatedEntries();
      this.updateListQueryParams();
    }
  }

  filterEntries(): void {
    this.calculateEntryCountsForTimeline();
    let entries = this.getFilteredActivityItems();

    // Then filter by selected month/timeline if one is selected
    if (this.selectedMonth) {
      entries = entries.filter((entry) => {
        const entryDate = new Date(this.getCardItemDate(entry));
        return (
          entryDate.getMonth() === (this.selectedMonth as any).monthIndex &&
          entryDate.getFullYear() === this.selectedMonth!.year
        );
      });
    }

    this.buildCalendarDays(
      entries.filter((entry): entry is EntryItem => entry.type !== "thought_record"),
    );

    if (this.selectedDay) {
      entries = entries.filter(
        (entry) =>
          this.toDateKey(new Date(this.getCardItemDate(entry))) === this.selectedDay,
      );
    }

    // Sort by date (newest first)
    this.filteredEntries = entries.sort(
      (a, b) => this.getCardItemSortTimestamp(b) - this.getCardItemSortTimestamp(a),
    );

    this.totalEntries = this.filteredEntries.length;
  }

  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.updatePaginatedEntries();
  }

  updatePaginatedEntries(): void {
    const startIndex = this.currentPage * this.pageSize;
    const endIndex = startIndex + this.pageSize;
    this.paginatedEntries = this.filteredEntries.slice(startIndex, endIndex);
  }

  calculateEntryCountsForTimeline(): void {
    const entriesForCount: EntryItem[] = [
      ...(this.isContentFilterActive("daily") ? this.dailyEntries : []),
      ...(this.isContentFilterActive("dreams") ? this.dreamEntries : []),
    ];

    this.allMonths.forEach((month) => {
      const entryCount = entriesForCount.filter((entry) => {
        const entryDate = new Date(entry.entry_date);
        return (
          entryDate.getMonth() === (month as any).monthIndex &&
          entryDate.getFullYear() === month.year
        );
      }).length;
      const thoughtRecordCount = this.isContentFilterActive("thought-records")
        ? this.thoughtRecords.filter((record) => {
              const recordDate = new Date(`${record.record_date}T12:00:00`);
              return (
                recordDate.getMonth() === (month as any).monthIndex &&
                recordDate.getFullYear() === month.year
              );
            }).length
        : 0;
      const count = entryCount + thoughtRecordCount;

      month.entryCount = count > 0 ? count : undefined;
    });

    this.updateVisibleMonths();
  }

  private getCalendarActivityDates(): Date[] {
    return [
      ...(this.isContentFilterActive("daily")
        ? this.dailyEntries.map((entry) => new Date(entry.entry_date))
        : []),
      ...(this.isContentFilterActive("dreams")
        ? this.dreamEntries.map((entry) => new Date(entry.entry_date))
        : []),
      ...(this.isContentFilterActive("thought-records")
        ? this.thoughtRecords.map(
            (record) => new Date(`${record.record_date}T12:00:00`),
          )
        : []),
    ].filter((activityDate) => !Number.isNaN(activityDate.getTime()));
  }

  private getFilteredActivityItems(): CardItem[] {
    return [
      ...(this.isContentFilterActive("daily") ? this.dailyEntries : []),
      ...(this.isContentFilterActive("dreams") ? this.dreamEntries : []),
      ...(this.isContentFilterActive("thought-records")
        ? this.thoughtRecords.map((record) => ({
            ...record,
            type: "thought_record" as const,
          }))
        : []),
    ];
  }

  getWritingRhythmStats(): WritingRhythmStats | null {
    const user = this.authService.getCurrentUser();
    if (!user?.writing_rhythm_progress_enabled) {
      return null;
    }

    const recordDates = this.getWritingRhythmRecordDates();
    const uniqueDates = [...new Set(recordDates)].sort();
    const weekStartKey = this.getStartOfWeekKey();
    const monthStartKey = this.getStartOfMonthKey();
    const weeklyGoal = Math.min(
      Math.max(Number(user.writing_rhythm_weekly_goal || 4), 1),
      21,
    );
    const weekCount = recordDates.filter((dateKey) => dateKey >= weekStartKey).length;
    const monthCount = recordDates.filter(
      (dateKey) => dateKey >= monthStartKey,
    ).length;
    const currentRunDays = this.getCurrentWritingRunDays(uniqueDates);
    const weeklyProgress = Math.min(Math.round((weekCount / weeklyGoal) * 100), 100);

    return {
      currentRunDays,
      weekCount,
      monthCount,
      weeklyGoal,
      weeklyProgress,
      includedLabel: `Counting ${this.getWritingRhythmIncludedLabel()}.`,
      message: this.getWritingRhythmMessage(currentRunDays, weekCount, weeklyGoal),
    };
  }

  private getWritingRhythmRecordDates(): string[] {
    const selectedTypes = this.getWritingRhythmRecordTypes();
    return [
      ...(selectedTypes.includes("daily")
        ? this.dailyEntries.map((entry) => this.toRecordDate(entry.entry_date))
        : []),
      ...(selectedTypes.includes("dream")
        ? this.dreamEntries.map((entry) => this.toRecordDate(entry.entry_date))
        : []),
      ...(selectedTypes.includes("thought_record")
        ? this.thoughtRecords.map((record) => this.toRecordDate(record.record_date))
        : []),
    ].filter((dateKey): dateKey is string => Boolean(dateKey));
  }

  private getWritingRhythmRecordTypes(): WritingRhythmRecordType[] {
    const user = this.authService.getCurrentUser();
    const selectedTypes = String(user?.writing_reminder_entry_types || "daily,dream")
      .split(",")
      .map((entryType) => entryType.trim().toLowerCase().replace("-", "_"))
      .filter((entryType): entryType is WritingRhythmRecordType =>
        ["daily", "dream", "thought_record"].includes(entryType),
      );
    return selectedTypes.length > 0 ? selectedTypes : ["daily", "dream"];
  }

  private getCurrentWritingRunDays(uniqueDateKeys: string[]): number {
    const activeDates = new Set(uniqueDateKeys);
    const today = new Date();
    const todayKey = this.toDateKey(today);
    const startDate = new Date(today);
    if (!activeDates.has(todayKey)) {
      startDate.setDate(startDate.getDate() - 1);
    }

    let runDays = 0;
    const cursor = new Date(startDate);
    while (activeDates.has(this.toDateKey(cursor))) {
      runDays += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return runDays;
  }

  private getWritingRhythmIncludedLabel(): string {
    const labels: Record<WritingRhythmRecordType, string> = {
      daily: "Diary",
      dream: "Dreams",
      thought_record: "Thought records",
    };
    return this.getWritingRhythmRecordTypes()
      .map((type) => labels[type])
      .join(", ");
  }

  private getWritingRhythmMessage(
    currentRunDays: number,
    weekCount: number,
    weeklyGoal: number,
  ): string {
    if (weekCount >= weeklyGoal) {
      return "Weekly rhythm goal reached.";
    }
    if (currentRunDays > 1) {
      return "A steady rhythm is building.";
    }
    if (currentRunDays === 1) {
      return "You have written recently.";
    }
    return "No pressure. Start with one useful note.";
  }

  private toRecordDate(value: string | undefined | null): string | null {
    const dateKey = String(value || "").slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(dateKey) ? dateKey : null;
  }

  private getStartOfWeekKey(): string {
    const date = new Date();
    const offset = (date.getDay() + 6) % 7;
    date.setDate(date.getDate() - offset);
    return this.toDateKey(date);
  }

  private getStartOfMonthKey(): string {
    const date = new Date();
    date.setDate(1);
    return this.toDateKey(date);
  }

  getEntryTitle(entry: CardItem): string {
    if (entry.type === "thought_record") {
      return this.getThoughtRecordTitle(entry);
    }
    if (entry.type === "dream" && entry.title) {
      return `"${entry.title}"`;
    }
    if (entry.type === "daily") {
      const dailyEntry = entry as DailyEntry & { type: "daily" };
      // Use the title field from database if available
      if (dailyEntry.title) {
        return dailyEntry.title;
      }
      // Fallback to old logic for entries without titles
      const [title] = this.splitDailyMessage(dailyEntry.user_message || "");
      return title || "Daily Entry";
    }
    return "Dream Entry";
  }

  getEntrySnippet(entry: CardItem): string {
    if (entry.type === "thought_record") {
      return [entry.situation, entry.balanced_thought]
        .filter(Boolean)
        .join(" · ")
        .replace(/\s+/g, " ")
        .trim();
    }
    const rawText =
      entry.type === "daily"
        ? this.splitDailyMessage(
            (entry as DailyEntry & { type: "daily" }).user_message || "",
          )[1]
        : (entry as DreamEntry & { type: "dream" }).plot || "";

    return rawText.replace(/\s+/g, " ").trim();
  }

  getCardItemIcon(entry: CardItem): string {
    if (entry.type === "thought_record") return "psychology_alt";
    return entry.type === "dream" ? "nights_stay" : "book";
  }

  hasEntryAttachments(entry: CardItem): boolean {
    if (entry.type === "thought_record") return false;
    return Array.isArray(entry.attachments) && entry.attachments.length > 0;
  }

  getCalendarPreviewPrimaryLabel(entry: EntryItem): string {
    return entry.type === "dream" ? "Plot" : "User entry";
  }

  getCalendarPreviewSecondaryLabel(entry: EntryItem): string {
    return entry.type === "dream" ? "AI interpretation" : "AI response";
  }

  getCalendarPreviewPrimaryText(entry: EntryItem): string {
    if (this.isDreamEntry(entry)) {
      return this.truncatePreviewText(entry.plot || "", 120);
    }

    const dailyEntry = entry as DailyEntry & { type: "daily" };
    return this.truncatePreviewText(
      this.splitDailyMessage(dailyEntry.user_message || "")[1],
      120,
    );
  }

  getCalendarPreviewSecondaryText(entry: EntryItem): string {
    if (this.isDreamEntry(entry)) {
      return this.truncatePreviewText(
        entry.interpretation || entry.summary || "",
        100,
      );
    }

    const dailyEntry = entry as DailyEntry & { type: "daily" };
    return this.truncatePreviewText(dailyEntry.ai_response || "", 100);
  }

  getEntryDateTimeSubtitle(entry: CardItem): string {
    if (entry.type === "thought_record") {
      const dateLabel = new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      }).format(new Date(`${entry.record_date}T12:00:00`));
      return `${dateLabel} • ${entry.status === "completed" ? "Completed" : `Draft · Step ${entry.current_step} of 7`}`;
    }
    const dateLabel = new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(new Date(`${entry.entry_date}T00:00:00`));
    const timeLabel = this.getEntryTimeLabel(entry);
    return timeLabel ? `${dateLabel} • ${timeLabel}` : dateLabel;
  }

  getEntryTimeLabel(entry: EntryItem): string {
    const rawValue = typeof entry.entry_time === "string" ? entry.entry_time.trim() : "";
    const value = rawValue || this.getFallbackEntryTime(entry);
    if (!/^\d{2}:\d{2}$/.test(value)) {
      return "";
    }

    const [hoursText, minutesText] = value.split(":");
    const hours = Number(hoursText);
    const minutes = Number(minutesText);
    if (
      Number.isNaN(hours) ||
      Number.isNaN(minutes) ||
      hours < 0 ||
      hours > 23 ||
      minutes < 0 ||
      minutes > 59
    ) {
      return "";
    }

    return new Intl.DateTimeFormat("en-GB", {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(2000, 0, 1, hours, minutes));
  }

  getTags(entry: CardItem): string[] {
    if (entry.type === "thought_record") return [];
    return (entry.tags || "")
      .split(",")
      .map((tag: string) => tag.trim())
      .filter((tag: string) => tag);
  }

  isDuplicateTag(tag: string): boolean {
    return tag.trim() === "*Duplicate*";
  }

  searchForTag(tag: string, event?: Event): void {
    event?.stopPropagation();
    // Navigate to entries with search query - the route parameter handler will trigger search
    this.router.navigate(["/entries"], { queryParams: { search: tag } });
  }

  private buildCalendarDays(entries: EntryItem[]): void {
    const baseMonth = this.selectedMonth
      ? new Date(this.selectedMonth.year, (this.selectedMonth as any).monthIndex, 1)
      : new Date(new Date().getFullYear(), new Date().getMonth(), 1);
    const year = baseMonth.getFullYear();
    const monthIndex = baseMonth.getMonth();
    const firstDayOfMonth = new Date(year, monthIndex, 1);
    const visibleStartDate = new Date(firstDayOfMonth);
    visibleStartDate.setDate(firstDayOfMonth.getDate() - 2);
    const lastDayOfMonth = new Date(year, monthIndex + 1, 0);
    const visibleEndDate = new Date(lastDayOfMonth);
    visibleEndDate.setDate(lastDayOfMonth.getDate() + 2);
    const todayKey = this.toDateKey(new Date());
    const entriesByDate = new Map<string, EntryItem[]>();
    const allEntriesByDate = new Map<string, EntryItem[]>();
    const thoughtRecordsByDate = new Map<string, CbtWorksheet[]>();
    const allThoughtRecordsByDate = new Map<string, CbtWorksheet[]>();
    const importantDaysByDate = new Map<string, ImportantDay[]>();
    const allImportantDaysByDate = new Map<string, ImportantDay[]>();
    const publicHolidaysByDate = new Map<string, PublicHoliday[]>();

    entries.forEach((entry) => {
      const key = this.toDateKey(new Date(entry.entry_date));
      const dateEntries = entriesByDate.get(key) ?? [];
      dateEntries.push(entry);
      entriesByDate.set(key, dateEntries);
    });

    [...this.dailyEntries, ...this.dreamEntries].forEach((entry) => {
      const key = this.toDateKey(new Date(entry.entry_date));
      const dateEntries = allEntriesByDate.get(key) ?? [];
      dateEntries.push(entry);
      allEntriesByDate.set(key, dateEntries);
    });

    this.thoughtRecords.forEach((record) => {
      const records = allThoughtRecordsByDate.get(record.record_date) ?? [];
      records.push(record);
      allThoughtRecordsByDate.set(record.record_date, records);
    });

    this.importantDays.forEach((importantDay) => {
      const key = this.toMonthDayKey(importantDay.month, importantDay.day);
      const matchingImportantDays = allImportantDaysByDate.get(key) ?? [];
      matchingImportantDays.push(importantDay);
      allImportantDaysByDate.set(key, matchingImportantDays);
    });

    if (this.isContentFilterActive("thought-records")) {
      this.thoughtRecords.forEach((record) => {
        const records = thoughtRecordsByDate.get(record.record_date) ?? [];
        records.push(record);
        thoughtRecordsByDate.set(record.record_date, records);
      });
    }

    if (this.isContentFilterActive("important-days")) {
      this.importantDays.forEach((importantDay) => {
        const key = this.toMonthDayKey(importantDay.month, importantDay.day);
        const matchingImportantDays = importantDaysByDate.get(key) ?? [];
        matchingImportantDays.push(importantDay);
        importantDaysByDate.set(key, matchingImportantDays);
      });
    }

    const yearHolidays = this.publicHolidaysByYear.get(year) ?? this.publicHolidays;

    yearHolidays.forEach((holiday) => {
      const holidayDate = new Date(`${holiday.date}T12:00:00`);
      if (holidayDate.getFullYear() !== year) {
        return;
      }
      const key = this.toDateKey(holidayDate);
      const matchingHolidays = publicHolidaysByDate.get(key) ?? [];
      matchingHolidays.push(holiday);
      publicHolidaysByDate.set(key, matchingHolidays);
    });

    const visibleDayCount =
      Math.round(
        (visibleEndDate.getTime() - visibleStartDate.getTime()) /
          (24 * 60 * 60 * 1000),
      ) + 1;

    this.calendarDays = Array.from({ length: visibleDayCount }, (_, index) => {
      const date = new Date(visibleStartDate);
      date.setDate(visibleStartDate.getDate() + index);
      const key = this.toDateKey(date);
      const isCurrentMonth = date.getMonth() === monthIndex;
      const dateEntries = entriesByDate.get(key) ?? [];
      const dateThoughtRecords = thoughtRecordsByDate.get(key) ?? [];
      const allDateEntries = allEntriesByDate.get(key) ?? [];
      const allDateThoughtRecords = allThoughtRecordsByDate.get(key) ?? [];
      const matchingImportantDays = (
        importantDaysByDate.get(this.toMonthDayKey(date.getMonth() + 1, date.getDate())) ?? []
      ).filter((importantDay) => {
        if (importantDay.recurrence === "once") {
          return importantDay.original_year === date.getFullYear();
        }
        return (
          !importantDay.original_year ||
          importantDay.original_year <= date.getFullYear()
        );
      });
      const allMatchingImportantDays = (
        allImportantDaysByDate.get(this.toMonthDayKey(date.getMonth() + 1, date.getDate())) ?? []
      ).filter((importantDay) => {
        if (importantDay.recurrence === "once") {
          return importantDay.original_year === date.getFullYear();
        }
        return (
          !importantDay.original_year ||
          importantDay.original_year <= date.getFullYear()
        );
      });
      const matchingPublicHolidays = publicHolidaysByDate.get(key) ?? [];
      const hiddenState = this.getCalendarHiddenState(
        date,
        allDateEntries,
        allDateThoughtRecords,
        allMatchingImportantDays,
      );

      return {
        date,
        dayNumber: date.getDate(),
        isCurrentMonth,
        isToday: key === todayKey,
        isFuture: date.getTime() > new Date().setHours(23, 59, 59, 999),
        status: this.getCalendarStatus(dateEntries),
        entries: dateEntries,
        thoughtRecords: dateThoughtRecords,
        importantDays: matchingImportantDays,
        publicHolidays: matchingPublicHolidays,
        hiddenItemCount: hiddenState.count,
        hiddenItemLabel: hiddenState.label,
      };
    });
  }

  getCalendarGridColumnStart(day: CalendarDay): number {
    return ((day.date.getDay() + 6) % 7) + 1;
  }

  private getCalendarHiddenState(
    date: Date,
    allDateEntries: EntryItem[],
    allDateThoughtRecords: CbtWorksheet[],
    allMatchingImportantDays: ImportantDay[],
  ): { count: number; label: string } {
    const hiddenParts: string[] = [];
    let hiddenItemCount = 0;

    const hiddenDailyCount = this.isContentFilterActive("daily")
      ? 0
      : allDateEntries.filter((entry) => entry.type === "daily").length;
    const hiddenDreamCount = this.isContentFilterActive("dreams")
      ? 0
      : allDateEntries.filter((entry) => entry.type === "dream").length;
    const hiddenThoughtCount = this.isContentFilterActive("thought-records")
      ? 0
      : allDateThoughtRecords.length;
    const hiddenImportantDayCount = this.isContentFilterActive("important-days")
      ? 0
      : allMatchingImportantDays.length;
    const hiddenOnThisDayCount =
      this.isContentFilterActive("on-this-day") ||
      !this.onThisDayFeed?.enabled ||
      !this.selectedMonth?.isCurrent ||
      this.toDateKey(date) !== this.toDateKey(new Date())
        ? 0
        : this.getVisibleOnThisDayEntries(this.onThisDayFeed.entries).length;

    const addHiddenPart = (count: number, singular: string, plural: string) => {
      if (count <= 0) {
        return;
      }
      hiddenItemCount += count;
      hiddenParts.push(`${count} ${count === 1 ? singular : plural}`);
    };

    addHiddenPart(hiddenDailyCount, "diary entry", "diary entries");
    addHiddenPart(hiddenDreamCount, "dream entry", "dream entries");
    addHiddenPart(hiddenThoughtCount, "thought record", "thought records");
    addHiddenPart(hiddenImportantDayCount, "important day", "important days");
    addHiddenPart(hiddenOnThisDayCount, "On this day memory", "On this day memories");

    return {
      count: hiddenItemCount,
      label:
        hiddenItemCount > 0
          ? `Hidden by current filters: ${hiddenParts.join(", ")}`
          : "",
    };
  }

  private getCalendarStatus(entries: EntryItem[]): CalendarStatus {
    const hasDaily = entries.some((entry) => entry.type === "daily");
    const hasDream = entries.some((entry) => entry.type === "dream");

    if (hasDaily && hasDream) {
      return "complete";
    }
    if (hasDaily) {
      return "daily";
    }
    if (hasDream) {
      return "dream";
    }
    return "none";
  }

  private toDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, "0");
    const day = `${date.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  private toMonthDayKey(month: number, day: number): string {
    return `${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  openEntryDetail(entry: CardItem, event?: Event): void {
    this.closeCalendarPreview();
    this.closeOccasionPreview(undefined, true);
    event?.stopPropagation();
    if (entry.type === "thought_record") {
      const queryParams: Record<string, string | number> = {
        returnTo: "entries",
        display: this.displayMode,
        show: this.getSerialisedContentFilters(),
      };
      if (this.selectedMonth) {
        queryParams["month"] = (this.selectedMonth as any).monthIndex + 1;
        queryParams["year"] = this.selectedMonth.year;
      }
      void this.router.navigate(["/cbt", entry.id], { queryParams });
      return;
    }
    this.router.navigate(["/entries", entry.id], {
      queryParams: this.getDetailContextParams(entry),
    });
  }

  private getDetailContextParams(
    entry?: EntryItem,
  ): Record<string, string | number> {
    const params: Record<string, string | number> = {};

    if (entry?.type) {
      params["entryType"] = entry.type;
    }
    params["show"] = this.getSerialisedContentFilters();
    params["display"] = this.displayMode;

    if (this.selectedMonth) {
      params["month"] = (this.selectedMonth as any).monthIndex + 1;
      params["year"] = this.selectedMonth.year;
    }

    return params;
  }

  private updateListQueryParams(): void {
    const queryParams: Record<string, string | number> = {
      ...this.getListQueryParamsWithoutSearch(),
    };

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }

  private getListQueryParamsWithoutSearch(): Record<string, string | number> {
    return {
      ...this.getDetailContextParams(),
      ...(this.displayMode === "calendar" ? { display: "calendar" } : {}),
    };
  }

  private parseSearchFilters(value: string | null): SearchFilters | undefined {
    if (!value) {
      return undefined;
    }

    const selected = new Set(value.split(",").map((filter) => filter.trim()));
    return {
      tags: selected.has("tags"),
      date: selected.has("date"),
      keywords: selected.has("keywords"),
      people: selected.has("people"),
    };
  }

  private applyContentFiltersFromQuery(
    showValue: string | null,
    legacyType: string | null,
  ): void {
    const validFilters = new Set(
      this.contentFilterOptions.map((option) => option.value),
    );

    if (showValue !== null) {
      this.hasExplicitContentFilters = true;
      this.activeContentFilters = new Set(
        showValue
          .split(",")
          .map((filter) => filter.trim() as ContentFilter)
          .filter((filter) => validFilters.has(filter)),
      );
      if (this.onThisDayFeed && !this.onThisDayFeed.enabled) {
        this.activeContentFilters.delete("on-this-day");
      }
      return;
    }

    this.hasExplicitContentFilters = false;
    const defaults = new Set<ContentFilter>([
      "daily",
      "dreams",
      "important-days",
    ]);
    if (legacyType === "daily" || legacyType === "dreams") {
      defaults.delete("daily");
      defaults.delete("dreams");
      defaults.add(legacyType);
    }
    this.activeContentFilters = defaults;
  }

  private getSerialisedContentFilters(): string {
    return this.contentFilterOptions
      .map((option) => option.value)
      .filter((filter) => this.activeContentFilters.has(filter))
      .join(",");
  }

  private isOnThisDayEnabled(): boolean {
    return Boolean(
      this.onThisDayFeed?.enabled || this.onThisDayMonthFeed?.enabled,
    );
  }

  private getVisibleOnThisDayEntries(
    entries: OnThisDayEntry[],
  ): OnThisDayEntry[] {
    return entries.filter((entry) => {
      if (entry.type === "daily") {
        return this.isContentFilterActive("daily");
      }
      if (entry.type === "dream") {
        return this.isContentFilterActive("dreams");
      }
      return this.isContentFilterActive("thought-records");
    });
  }

  private syncOnThisDayFilterAvailability(enabled: boolean): void {
    const next = new Set(this.activeContentFilters);
    if (!enabled) {
      next.delete("on-this-day");
    }
    this.activeContentFilters = next;
    if (this.allMonths.length > 0) {
      this.filterEntries();
      this.updatePaginatedEntries();
    }
  }

  private applyInitialMonthSelection(): void {
    if (this.pendingMonthSelection) {
      const monthFromQuery = this.allMonths.find(
        (month) =>
          (month as any).monthIndex ===
            this.pendingMonthSelection!.monthIndex &&
          month.year === this.pendingMonthSelection!.year,
      );

      if (monthFromQuery && !monthFromQuery.isFuture) {
        this.allMonths.forEach((m) => (m.isSelected = false));
        monthFromQuery.isSelected = true;
        this.selectedMonth = monthFromQuery;
      }

      this.pendingMonthSelection = null;
      this.syncPublicHolidaysForSelectedYear();
      return;
    }

    if (!this.hasExplicitMonthSelection) {
      this.selectCurrentMonth(false);
    }
  }

  private selectCurrentMonth(explicit: boolean): void {
    const now = new Date();
    this.selectMonthByDate(now, explicit);
  }

  private selectMonthByDate(date: Date, explicit: boolean, animate = false): void {
    this.flippedCalendarDays.clear();
    const monthToSelect = this.allMonths.find(
      (month) =>
        (month as any).monthIndex === date.getMonth() &&
        month.year === date.getFullYear() &&
        !month.isFuture,
    );

    if (!monthToSelect) {
      return;
    }

    this.hasExplicitMonthSelection = explicit;
    this.allMonths.forEach((m) => (m.isSelected = false));
    monthToSelect.isSelected = true;
    this.selectedMonth = monthToSelect;
    this.syncPublicHolidaysForSelectedYear();

    const selectedIndex = this.allMonths.findIndex((m) => m === monthToSelect);
    if (animate) {
      this.centerTimelineAnimated(selectedIndex);
      return;
    }

    this.timelineScrollIndex = Math.max(0, Math.min(selectedIndex - 2, this.maxScrollIndex));
    this.updateVisibleMonths();
  }

  private splitDailyMessage(message: string): [string, string] {
    const [title, ...rest] = message.split(/\n\n?/);
    if (rest.length === 0) {
      return ["", title];
    }
    return [title, rest.join("\n\n")];
  }

  private truncatePreviewText(text: string, maxLength: number): string {
    const collapsed = text.replace(/\s+/g, " ").trim();
    if (collapsed.length <= maxLength) {
      return collapsed;
    }

    return `${collapsed.slice(0, maxLength - 1).trimEnd()}…`;
  }

  private isDreamEntry(
    entry: EntryItem,
  ): entry is DreamEntry & { type: "dream" } {
    return entry.type === "dream";
  }

  hasCalendarPreviewImage(entry: EntryItem): boolean {
    return this.getCalendarPreviewImageUrl(entry) !== null;
  }

  shouldShowOnThisDay(): boolean {
    if (
      !this.isContentFilterActive("on-this-day") ||
      !this.onThisDayFeed?.enabled ||
      this.getVisibleOnThisDayEntries(this.onThisDayFeed.entries).length === 0
    ) {
      return false;
    }
    const today = new Date();
    return Boolean(
      this.selectedMonth?.isCurrent &&
        this.selectedMonth.year === today.getFullYear(),
    );
  }

  shouldShowOnThisDayForDay(day: CalendarDay): boolean {
    return day.isToday && this.shouldShowOnThisDay();
  }

  getCalendarDayMetrics(day: CalendarDay): CalendarDayMetric[] {
    const dateLabel = this.getCalendarDayDateLabel(day);
    const metrics: CalendarDayMetric[] = [];
    const dailyCount = this.getEntryCountByType(day, "daily");
    const dreamCount = this.getEntryCountByType(day, "dream");

    if (dailyCount > 0) {
      metrics.push({
        type: "daily",
        icon: "book",
        count: dailyCount,
        label: `Preview ${dailyCount} daily ${dailyCount === 1 ? "entry" : "entries"} for ${dateLabel}`,
        cssClass: "daily",
      });
    }
    if (dreamCount > 0) {
      metrics.push({
        type: "dream",
        icon: "nights_stay",
        count: dreamCount,
        label: `Preview ${dreamCount} dream ${dreamCount === 1 ? "entry" : "entries"} for ${dateLabel}`,
        cssClass: "dream",
      });
    }
    if (day.thoughtRecords.length > 0) {
      metrics.push({
        type: "thought_record",
        icon: "psychology_alt",
        count: day.thoughtRecords.length,
        label: `Preview ${day.thoughtRecords.length} thought ${day.thoughtRecords.length === 1 ? "record" : "records"} for ${dateLabel}`,
        cssClass: "thought-record",
        testId: "calendar-thought-record-marker",
      });
    }
    if (day.importantDays.length > 0) {
      const firstImportantDay = day.importantDays[0];
      metrics.push({
        type: "important_day",
        icon: this.getImportantDayIcon(firstImportantDay),
        count: day.importantDays.length,
        label: `Preview ${day.importantDays.length} important ${day.importantDays.length === 1 ? "day" : "days"} for ${dateLabel}`,
        cssClass: `important-day accent-${firstImportantDay.accent_color}`,
        testId: "calendar-occasion-marker",
      });
    }
    if (day.publicHolidays.length > 0) {
      metrics.push({
        type: "public_holiday",
        icon: this.getPublicHolidayIcon(day.publicHolidays[0]),
        count: day.publicHolidays.length,
        label: `Preview ${day.publicHolidays.length} public ${day.publicHolidays.length === 1 ? "holiday" : "holidays"} for ${dateLabel}`,
        cssClass: "public-holiday",
        testId: "calendar-public-holiday-marker",
      });
    }
    if (this.shouldShowOnThisDayForDay(day) && this.onThisDayFeed) {
      const visibleMemories = this.getVisibleOnThisDayEntries(
        this.onThisDayFeed.entries,
      );
      metrics.push({
        type: "on_this_day",
        icon: "history",
        count: visibleMemories.length,
        label: `Preview ${visibleMemories.length} On this day ${visibleMemories.length === 1 ? "memory" : "memories"}`,
        cssClass: "on-this-day",
        testId: "calendar-on-this-day-marker",
      });
    }

    return metrics;
  }

  getPrimaryCalendarDayMetrics(day: CalendarDay): CalendarDayMetric[] {
    return this.getCalendarDayMetrics(day)
      .filter((metric) => metric.type !== "public_holiday")
      .slice(0, 5);
  }

  getFrontPrimaryCalendarDayMetrics(day: CalendarDay): CalendarDayMetric[] {
    return this.getPrimaryCalendarDayMetrics(day).filter((metric) =>
      ["daily", "dream"].includes(metric.type),
    );
  }

  getFrontSecondaryCalendarDayMetrics(day: CalendarDay): CalendarDayMetric[] {
    return this.getPrimaryCalendarDayMetrics(day).filter(
      (metric) => !["daily", "dream"].includes(metric.type),
    );
  }

  getSecondaryCalendarDayMetrics(day: CalendarDay): CalendarDayMetric[] {
    const metrics = this.getCalendarDayMetrics(day);
    const overflowMetrics = metrics
      .filter((metric) => metric.type !== "public_holiday")
      .slice(5);
    const holidayMetrics = metrics.filter(
      (metric) => metric.type === "public_holiday",
    );
    return [...overflowMetrics, ...holidayMetrics].slice(0, 5);
  }

  getCalendarDayFaceBackground(
    day: CalendarDay,
    face: "front" | "back",
  ): string {
    const theme = this.themeService.isDark() ? "dark" : "light";
    const metrics =
      face === "front"
        ? this.getPrimaryCalendarDayMetrics(day)
        : this.getSecondaryCalendarDayMetrics(day);
    const colours = metrics
      .map((metric) => this.getCalendarMetricFaceColour(metric, theme))
      .filter(
        (colour, index, list): colour is string =>
          Boolean(colour) && list.indexOf(colour) === index,
      )
      .slice(0, 3);

    if (colours.length === 0) {
      return "transparent";
    }

    if (colours.length === 1) {
      const endColour =
        theme === "dark" ? "var(--colour-surface)" : "var(--colour-surface-elevated)";
      return `linear-gradient(180deg, ${colours[0]} 0%, ${endColour} 100%)`;
    }

    const stops = colours
      .map((colour, index) => {
        const position =
          colours.length === 1
            ? 0
            : Math.round((index / (colours.length - 1)) * 100);
        return `${colour} ${position}%`;
      })
      .join(", ");

    return `linear-gradient(45deg, ${stops})`;
  }

  private getCalendarMetricFaceColour(
    metric: CalendarDayMetric,
    theme: "light" | "dark",
  ): string {
    const lightColours: Record<CalendarDayMetricType, string> = {
      daily: "var(--calendar-gradient-daily)",
      dream: "var(--calendar-gradient-dream)",
      thought_record: "var(--calendar-gradient-thought)",
      important_day: "var(--calendar-gradient-important)",
      public_holiday: "var(--calendar-gradient-holiday)",
      on_this_day: "var(--calendar-gradient-on-this-day)",
    };
    const darkColours: Record<CalendarDayMetricType, string> = {
      daily: "var(--calendar-gradient-daily-dark)",
      dream: "var(--calendar-gradient-dream-dark)",
      thought_record: "var(--calendar-gradient-thought-dark)",
      important_day: "var(--calendar-gradient-important-dark)",
      public_holiday: "var(--calendar-gradient-holiday-dark)",
      on_this_day: "var(--calendar-gradient-on-this-day-dark)",
    };

    return theme === "dark" ? darkColours[metric.type] : lightColours[metric.type];
  }

  trackCalendarDayMetric(
    _index: number,
    metric: CalendarDayMetric,
  ): CalendarDayMetricType {
    return metric.type;
  }

  hasCalendarDayBack(day: CalendarDay): boolean {
    return this.getSecondaryCalendarDayMetrics(day).length > 0;
  }

  isCalendarDayMetricActive(
    day: CalendarDay,
    type: CalendarDayMetricType,
  ): boolean {
    const dayKey = this.toDateKey(day.date);
    switch (type) {
      case "daily":
      case "dream":
        return this.isCalendarPreviewActive(day, type);
      case "thought_record":
        return this.isCbtPreviewActive(day);
      case "important_day":
        return (
          this.importantDayPreview?.dayKey === dayKey &&
          this.importantDayPreview.phase === "open"
        );
      case "public_holiday":
        return (
          this.occasionPreview?.dayKey === `${dayKey}:holiday` &&
          this.occasionPreview.phase === "open"
        );
      case "on_this_day":
        return this.onThisDayPreview?.phase === "open";
    }
  }

  activateCalendarDayMetric(
    day: CalendarDay,
    type: CalendarDayMetricType,
    event: MouseEvent,
  ): void {
    this.ignorePreviewScrollUntil = performance.now() + 250;
    switch (type) {
      case "daily":
      case "dream":
        this.toggleCalendarPreview(day, type, event);
        return;
      case "thought_record":
        this.toggleCbtPreview(day, event);
        return;
      case "important_day":
        this.toggleImportantDayPreview(day, event);
        return;
      case "public_holiday":
        this.togglePublicHolidayPreview(day, event);
        return;
      case "on_this_day":
        this.toggleOnThisDayPreview(event);
        return;
    }
  }

  isCalendarDayFlipped(day: CalendarDay): boolean {
    return this.flippedCalendarDays.has(this.toDateKey(day.date));
  }

  toggleCalendarDayFace(day: CalendarDay, event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    this.closeOnThisDayPreview(undefined, true);

    const dayKey = this.toDateKey(day.date);
    if (this.calendarFlipTimerId) {
      window.clearTimeout(this.calendarFlipTimerId);
      this.calendarFlipTimerId = null;
    }
    if (this.flippedCalendarDays.has(dayKey)) {
      this.flippedCalendarDays.delete(dayKey);
    } else {
      this.flippedCalendarDays.clear();
      this.flippedCalendarDays.add(dayKey);
      this.calendarFlipTimerId = window.setTimeout(() => {
        this.flippedCalendarDays.delete(dayKey);
        this.calendarFlipTimerId = null;
      }, 6000);
    }
  }

  addEntryForCalendarDay(day: CalendarDay, event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.closeAllCalendarPreviewsImmediately();
    this.navigateToCreateEntryForDate(day.date);
  }

  addEntryFromCalendarFace(day: CalendarDay, event: MouseEvent): void {
    const target = event.target;
    if (
      target instanceof Element &&
      target.closest(
        'button, a, input, textarea, select, [role="button"], [role="link"]',
      )
    ) {
      return;
    }

    this.addEntryForCalendarDay(day, event);
  }

  getOnThisDaySummaryLabel(): string {
    const count = this.getVisibleOnThisDayEntries(
      this.onThisDayFeed?.entries ?? [],
    ).length;
    return `${count} ${count === 1 ? "memory" : "memories"} from earlier years`;
  }

  toggleOnThisDayPreview(event: MouseEvent): void {
    event.stopPropagation();
    this.ignorePreviewScrollUntil = performance.now() + 250;
    if (!this.shouldShowOnThisDay() || !this.onThisDayFeed) return;

    if (
      this.onThisDayPreview?.scope === "day" &&
      this.onThisDayPreview.phase === "open"
    ) {
      this.closeOnThisDayPreview();
      return;
    }

    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    if (this.onThisDayPreviewCloseTimerId) {
      window.clearTimeout(this.onThisDayPreviewCloseTimerId);
      this.onThisDayPreviewCloseTimerId = null;
    }

    const entries = this.getVisibleOnThisDayEntries(this.onThisDayFeed.entries);
    const previewEntries = entries.slice(0, 3);
    const anchor = event.currentTarget as HTMLElement;
    const position = this.getCalendarPreviewPosition(
      anchor,
      previewEntries.length,
    );
    const targetDate = new Date(`${this.onThisDayFeed.date}T12:00:00`);
    this.onThisDayPreview = {
      scope: "day",
      heading: "On this day",
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      entries: previewEntries,
      totalCount: entries.length,
      dateLabel: targetDate.toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
      }),
      top: position.top,
      left: position.left,
      placement: position.placement,
    };
  }

  getCurrentMonthOnThisDayEntries(): OnThisDayEntry[] {
    if (
      !this.isContentFilterActive("on-this-day") ||
      !this.onThisDayMonthFeed?.enabled
    ) {
      return [];
    }
    return this.getVisibleOnThisDayEntries(this.onThisDayMonthFeed.entries);
  }

  getCurrentMonthOnThisDaySummaryLabel(): string {
    const count = this.getCurrentMonthOnThisDayEntries().length;
    return `${count} ${count === 1 ? "memory" : "memories"}`;
  }

  toggleMonthlyOnThisDayPreview(event: MouseEvent): void {
    event.stopPropagation();
    this.ignorePreviewScrollUntil = performance.now() + 250;
    const entries = this.getCurrentMonthOnThisDayEntries();
    if (!entries.length) return;

    if (
      this.onThisDayPreview?.scope === "month" &&
      this.onThisDayPreview.phase === "open"
    ) {
      this.closeOnThisDayPreview();
      return;
    }

    this.closeCalendarPreview(undefined, true);
    this.closeCbtPreview(undefined, true);
    this.closeImportantDayPreview(undefined, true);
    this.closeOccasionPreview(undefined, true);
    if (this.onThisDayPreviewCloseTimerId) {
      window.clearTimeout(this.onThisDayPreviewCloseTimerId);
      this.onThisDayPreviewCloseTimerId = null;
    }

    const position = this.getCalendarPreviewPosition(
      event.currentTarget as HTMLElement,
      Math.min(entries.length, 3),
    );
    const previewEntries = entries.slice(0, 3);
    this.onThisDayPreview = {
      scope: "month",
      heading: "On this day this month",
      phase: "open",
      direction: this.getPreviewDirectionFromClick(event),
      entries: previewEntries,
      totalCount: entries.length,
      dateLabel: this.getCalendarHeading(),
      top: position.top,
      left: position.left,
      placement: position.placement,
    };
  }

  getOnThisDayIcon(entry: OnThisDayEntry): string {
    if (entry.type === "dream") return "nights_stay";
    if (entry.type === "thought_record") return "psychology_alt";
    return "book";
  }

  getOnThisDayEntryDateLabel(entry: OnThisDayEntry): string {
    return new Date(`${entry.entry_date}T12:00:00`).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  getOnThisDayImageStyle(entry: OnThisDayEntry): string | null {
    const imageUrl = String(entry.image_url || "").trim();
    return imageUrl ? `url("${imageUrl.replace(/"/g, '\\"')}")` : null;
  }

  shouldShowOnThisDayMoreCard(): boolean {
    return Boolean(
      this.onThisDayPreview &&
        this.onThisDayPreview.totalCount > this.onThisDayPreview.entries.length,
    );
  }

  getOnThisDayMoreLabel(): string {
    return (this.onThisDayPreview?.totalCount ?? 0) > 3
      ? "View all memories"
      : "On this day";
  }

  openOnThisDayFullView(event: Event): void {
    event.stopPropagation();
    if (!this.onThisDayPreview) {
      return;
    }

    const entries =
      this.onThisDayPreview.scope === "month"
        ? this.getCurrentMonthOnThisDayEntries()
        : this.getVisibleOnThisDayEntries(this.onThisDayFeed?.entries ?? []);

    this.onThisDayPreview = {
      ...this.onThisDayPreview,
      entries,
      totalCount: entries.length,
    };
  }

  openOnThisDayEntry(entry: OnThisDayEntry, event: Event): void {
    event.stopPropagation();
    this.closeOnThisDayPreview(undefined, true);
    const date = new Date(`${this.onThisDayFeed?.date || entry.entry_date}T12:00:00`);
    const returnParams = {
      display: this.displayMode,
      show: this.getSerialisedContentFilters(),
      month: date.getMonth() + 1,
      year: date.getFullYear(),
    };
    if (entry.type === "thought_record") {
      void this.router.navigate(["/cbt", entry.id], {
        queryParams: { ...returnParams, returnTo: "calendar" },
      });
      return;
    }
    void this.router.navigate(["/entries", entry.id], {
      queryParams: { ...returnParams, entryType: entry.type },
    });
  }

  async hideOnThisDayEntry(entry: OnThisDayEntry, event: Event): Promise<void> {
    event.stopPropagation();
    const confirmed = await this.appDialog.confirm({
      title: "Hide this memory?",
      message: "It will no longer appear in On this day.",
      confirmText: "Hide memory",
      cancelText: "Keep showing",
      variant: "danger",
    });
    if (!confirmed) return;

    this.onThisDayService.hideEntry(entry.type, entry.id).subscribe({
      next: () => {
        if (this.onThisDayFeed) {
          this.onThisDayFeed = {
            ...this.onThisDayFeed,
            entries: this.onThisDayFeed.entries.filter(
              (item) => item.id !== entry.id || item.type !== entry.type,
            ),
          };
        }
        if (this.onThisDayMonthFeed) {
          this.onThisDayMonthFeed = {
            ...this.onThisDayMonthFeed,
            entries: this.onThisDayMonthFeed.entries.filter(
              (item) => item.id !== entry.id || item.type !== entry.type,
            ),
          };
        }
        if (this.onThisDayPreview) {
          const entries =
            this.onThisDayPreview.scope === "month"
              ? this.getVisibleOnThisDayEntries(
                  this.onThisDayMonthFeed?.entries ?? [],
                )
              : this.getVisibleOnThisDayEntries(
                  this.onThisDayFeed?.entries ?? [],
                );
          if (entries.length === 0) {
            this.closeOnThisDayPreview(undefined, true);
          } else {
            this.onThisDayPreview = { ...this.onThisDayPreview, entries };
          }
        }
      },
      error: () => {
        void this.appDialog.alert({
          title: "Memory could not be hidden",
          message: "Try again in a moment.",
          confirmText: "Close",
          cancelText: "",
          variant: "warning",
        });
      },
    });
  }

  getCalendarPreviewImageStyle(entry: EntryItem): string | null {
    const imageUrl = this.getCalendarPreviewImageUrl(entry);
    return imageUrl ? `url("${imageUrl.replace(/"/g, '\\"')}")` : null;
  }

  getEntryCardImageUrl(entry: CardItem): string | null {
    if (entry.type === "thought_record") return null;
    return this.getCalendarPreviewImageUrl(entry);
  }

  isAiGeneratedEntryImage(entry: CardItem): boolean {
    if (entry.type === "thought_record") return false;
    return (entry.image_source || "").trim() === "ai";
  }

  private getCalendarPreviewImageUrl(entry: EntryItem): string | null {
    const raw = typeof entry.image_url === "string" ? entry.image_url.trim() : "";
    return raw.length > 0 ? raw : null;
  }

  private syncPublicHolidaysForSelectedYear(): void {
    this.syncOnThisDayForSelectedMonth();
    if (!this.selectedMonth) {
      return;
    }

    if (!this.publicHolidaysEnabled && this.publicHolidaySettingsLoaded) {
      return;
    }

    const selectedYear = this.selectedMonth.year;
    if (this.publicHolidaysEnabled && this.loadedHolidayYears.has(selectedYear)) {
      return;
    }

    this.publicHolidaysService.getPublicHolidays(selectedYear).subscribe({
      next: (feed) => {
        this.publicHolidaySettingsLoaded = true;
        this.publicHolidaysEnabled = Boolean(feed.enabled);
        this.publicHolidayCountryCode = feed.countryCode || "";
        if (feed.enabled) {
          this.publicHolidaysByYear.set(feed.year, feed.holidays || []);
          this.publicHolidays = this.publicHolidaysByYear.get(selectedYear) ?? [];
          this.loadedHolidayYears.add(feed.year);
        } else {
          this.publicHolidays = [];
          this.publicHolidaysByYear.clear();
          this.loadedHolidayYears.clear();
        }
        this.filterEntries();
        this.updatePaginatedEntries();
      },
      error: () => {
        this.publicHolidaysByYear.delete(selectedYear);
        this.publicHolidays = this.publicHolidaysByYear.get(selectedYear) ?? [];
        this.loadedHolidayYears.delete(selectedYear);
        this.filterEntries();
        this.updatePaginatedEntries();
      },
    });
  }

  private loadOnThisDayFeed(requestId: number): void {
    this.onThisDayService.getFeed().subscribe({
      next: (feed) => {
        if (requestId !== this.entriesLoadRequestId) {
          return;
        }
        this.onThisDayFeed = feed;
        this.syncOnThisDayFilterAvailability(feed.enabled);
      },
      error: () => {
        if (requestId !== this.entriesLoadRequestId) {
          return;
        }
        this.onThisDayFeed = null;
        this.syncOnThisDayFilterAvailability(false);
      },
    });
  }

  private syncOnThisDayForSelectedMonth(): void {
    if (!this.selectedMonth) {
      this.onThisDayMonthFeed = null;
      return;
    }
    this.onThisDayService
      .getMonthFeed(
        this.selectedMonth.year,
        (this.selectedMonth as any).monthIndex + 1,
      )
      .subscribe({
        next: (feed) => {
          this.onThisDayMonthFeed = feed;
          this.syncOnThisDayFilterAvailability(feed.enabled);
        },
        error: () => {
          this.onThisDayMonthFeed = null;
          this.syncOnThisDayFilterAvailability(
            Boolean(this.onThisDayFeed?.enabled),
          );
        },
      });
  }

  private getEntrySortTimestamp(entry: EntryItem): number {
    const timeValue =
      typeof entry.entry_time === "string" && /^\d{2}:\d{2}$/.test(entry.entry_time.trim())
        ? entry.entry_time.trim()
        : this.getFallbackEntryTime(entry);
    return new Date(`${entry.entry_date}T${timeValue}:00`).getTime();
  }

  private getCardItemDate(entry: CardItem): string {
    return entry.type === "thought_record" ? entry.record_date : entry.entry_date;
  }

  private getCardItemSortTimestamp(entry: CardItem): number {
    if (entry.type === "thought_record") {
      return new Date(`${entry.record_date}T12:00:00`).getTime();
    }
    return this.getEntrySortTimestamp(entry);
  }

  private getFallbackEntryTime(entry: EntryItem): string {
    return entry.type === "dream" ? "08:00" : "19:00";
  }

  private generateTimelineMonths(count = 4): TimelineMonth[] {
    // This method is now replaced by generateAllMonths()
    // Keeping for backward compatibility but not used
    const months: TimelineMonth[] = [];
    const now = new Date();
    for (let i = count - 1; i >= 0; i--) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push({
        label: date.toLocaleString("default", { month: "long" }),
        year: date.getFullYear(),
        isCurrent: i === 0,
        isSelected: i === 0,
        isFuture: false,
        isActive: true,
      });
    }
    return months;
  }

  private getPreviewDirectionFromClick(
    event: MouseEvent,
  ): "left-to-right" | "right-to-left" {
    const viewportMidpoint = window.innerWidth / 2;
    return event.clientX <= viewportMidpoint ? "left-to-right" : "right-to-left";
  }

  private getPreviewDirectionFromEvent(
    event: MouseEvent | KeyboardEvent,
    anchorElement: HTMLElement,
  ): "left-to-right" | "right-to-left" {
    if (event instanceof MouseEvent) {
      return this.getPreviewDirectionFromClick(event);
    }

    const rect = anchorElement.getBoundingClientRect();
    const midpoint = rect.left + rect.width / 2;
    return midpoint <= window.innerWidth / 2
      ? "left-to-right"
      : "right-to-left";
  }

  private getEventTargetElement(event?: Event): HTMLElement | null {
    const target = event?.target;
    if (target instanceof HTMLElement) {
      return target;
    }
    if (target instanceof Element) {
      return target as HTMLElement;
    }
    if (target instanceof Node) {
      return target.parentElement;
    }
    return null;
  }

  private getCalendarPreviewPosition(
    anchorElement: HTMLElement,
    previewCardCount: number,
  ): { top: number; left: number; placement: "above" | "below" } {
    const rect = anchorElement.getBoundingClientRect();
    const cardWidth = window.innerWidth <= 600 ? 200 : 230;
    const halfCardWidth = Math.round(cardWidth * 0.56);
    const gap = 14;
    const horizontalPadding = 28;
    const deckWidth =
      previewCardCount * cardWidth +
      Math.max(0, previewCardCount - 1) * gap +
      halfCardWidth +
      gap +
      horizontalPadding;
    const estimatedHeight = window.innerWidth <= 600 ? 250 : 290;
    const viewportPadding = 16;

    const centeredLeft = rect.left + rect.width / 2 - deckWidth / 2;
    const maxLeft = window.innerWidth - deckWidth - viewportPadding;
    const left = Math.max(viewportPadding, Math.min(centeredLeft, maxLeft));

    const preferBelow = rect.top < estimatedHeight + viewportPadding;
    const placement: "above" | "below" = preferBelow ? "below" : "above";
    const top =
      placement === "below"
        ? Math.min(rect.bottom + 12, window.innerHeight - estimatedHeight - viewportPadding)
        : Math.max(viewportPadding, rect.top - estimatedHeight - 12);

    return { top, left, placement };
  }

  closeCalendarPreview(event?: Event, immediate = false): void {
    event?.stopPropagation();

    if (!this.calendarPreview) {
      return;
    }

    if (this.previewCloseTimerId) {
      window.clearTimeout(this.previewCloseTimerId);
      this.previewCloseTimerId = null;
    }

    if (immediate) {
      this.calendarPreview = null;
      return;
    }

    this.calendarPreview = {
      ...this.calendarPreview,
      phase: "closing",
    };

    const closingPreviewKey = `${this.calendarPreview.dayKey}:${this.calendarPreview.type}`;
    this.previewCloseTimerId = window.setTimeout(() => {
      if (
        this.calendarPreview &&
        `${this.calendarPreview.dayKey}:${this.calendarPreview.type}` ===
          closingPreviewKey
      ) {
        this.calendarPreview = null;
      }
      this.previewCloseTimerId = null;
    }, 180);
  }

  closeOnThisDayPreview(event?: Event, immediate = false): void {
    event?.stopPropagation();
    if (!this.onThisDayPreview) return;

    if (this.onThisDayPreviewCloseTimerId) {
      window.clearTimeout(this.onThisDayPreviewCloseTimerId);
      this.onThisDayPreviewCloseTimerId = null;
    }
    if (immediate) {
      this.onThisDayPreview = null;
      return;
    }
    this.onThisDayPreview = { ...this.onThisDayPreview, phase: "closing" };
    this.onThisDayPreviewCloseTimerId = window.setTimeout(() => {
      this.onThisDayPreview = null;
      this.onThisDayPreviewCloseTimerId = null;
    }, 180);
  }

  closeCbtPreview(event?: Event, immediate = false): void {
    event?.stopPropagation();
    if (!this.cbtPreview) return;

    if (this.cbtPreviewCloseTimerId) {
      window.clearTimeout(this.cbtPreviewCloseTimerId);
      this.cbtPreviewCloseTimerId = null;
    }

    if (immediate) {
      this.cbtPreview = null;
      return;
    }

    this.cbtPreview = { ...this.cbtPreview, phase: "closing" };
    const closingPreviewKey = this.cbtPreview.dayKey;
    this.cbtPreviewCloseTimerId = window.setTimeout(() => {
      if (this.cbtPreview?.dayKey === closingPreviewKey) {
        this.cbtPreview = null;
      }
      this.cbtPreviewCloseTimerId = null;
    }, 180);
  }

  closeImportantDayPreview(event?: Event, immediate = false): void {
    event?.stopPropagation();

    if (!this.importantDayPreview) {
      return;
    }

    if (this.importantDayPreviewCloseTimerId) {
      window.clearTimeout(this.importantDayPreviewCloseTimerId);
      this.importantDayPreviewCloseTimerId = null;
    }

    if (immediate) {
      this.importantDayPreview = null;
      return;
    }

    this.importantDayPreview = {
      ...this.importantDayPreview,
      phase: "closing",
    };

    const closingPreviewKey = this.importantDayPreview.dayKey;
    this.importantDayPreviewCloseTimerId = window.setTimeout(() => {
      if (
        this.importantDayPreview &&
        this.importantDayPreview.dayKey === closingPreviewKey
      ) {
        this.importantDayPreview = null;
      }
      this.importantDayPreviewCloseTimerId = null;
    }, 180);
  }

  closeOccasionPreview(event?: Event, immediate = false): void {
    event?.stopPropagation();

    if (!this.occasionPreview) {
      return;
    }

    if (this.occasionPreviewCloseTimerId) {
      window.clearTimeout(this.occasionPreviewCloseTimerId);
      this.occasionPreviewCloseTimerId = null;
    }

    if (immediate) {
      this.occasionPreview = null;
      return;
    }

    this.occasionPreview = {
      ...this.occasionPreview,
      phase: "closing",
    };

    const closingPreviewKey = this.occasionPreview.dayKey;
    this.occasionPreviewCloseTimerId = window.setTimeout(() => {
      if (
        this.occasionPreview &&
        this.occasionPreview.dayKey === closingPreviewKey
      ) {
        this.occasionPreview = null;
      }
      this.occasionPreviewCloseTimerId = null;
    }, 180);
  }

  @HostListener("document:click", ["$event"])
  onDocumentClick(event: MouseEvent): void {
    const target = this.getEventTargetElement(event);
    if (!target) {
      return;
    }

    if (this.calendarPreview) {
      if (target.closest(".calendar-preview-deck, .calendar-entry-icon")) {
        return;
      }
      this.closeCalendarPreview();
    }

    if (this.cbtPreview) {
      if (
        target.closest(
          ".cbt-preview-deck, .calendar-entry-icon.thought-record, .calendar-thought-records-summary-trigger",
        )
      ) {
        return;
      }
      this.closeCbtPreview();
    }

    if (this.importantDayPreview) {
      if (
        target.closest(
          ".important-day-preview-deck, .calendar-important-day-badge, .calendar-important-days-summary-trigger",
        )
      ) {
        return;
      }
      this.closeImportantDayPreview();
    }

    if (this.occasionPreview) {
      if (
        target.closest(
          ".important-day-preview-deck, .calendar-important-day-badge, .calendar-entry-icon.important-day, .calendar-entry-icon.public-holiday",
        )
      ) {
        return;
      }
      this.closeOccasionPreview();
    }

    if (this.onThisDayPreview) {
      if (
        target.closest(
          ".on-this-day-preview-deck, .on-this-day-summary, .calendar-entry-icon.on-this-day",
        )
      ) {
        return;
      }
      this.closeOnThisDayPreview();
    }
  }

  @HostListener("document:keydown.escape", ["$event"])
  onEscapeKey(event: KeyboardEvent): void {
    if (this.calendarPreview) {
      event.preventDefault();
      this.closeCalendarPreview();
      return;
    }


    if (this.cbtPreview) {
      event.preventDefault();
      this.closeCbtPreview();
      return;
    }

    if (this.importantDayPreview) {
      event.preventDefault();
      this.closeImportantDayPreview();
      return;
    }

    if (this.occasionPreview) {
      event.preventDefault();
      this.closeOccasionPreview();
      return;
    }

    if (this.onThisDayPreview) {
      event.preventDefault();
      this.closeOnThisDayPreview();
    }
  }

  @HostListener("window:scroll")
  onWindowScroll(): void {
    this.closeAllCalendarPreviewsImmediately();
  }

  private closeAllCalendarPreviewsImmediately(): void {
    if (this.calendarPreview) {
      this.closeCalendarPreview(undefined, true);
    }
    if (this.cbtPreview) {
      this.closeCbtPreview(undefined, true);
    }
    if (this.importantDayPreview) {
      this.closeImportantDayPreview(undefined, true);
    }
    if (this.occasionPreview) {
      this.closeOccasionPreview(undefined, true);
    }
    if (this.onThisDayPreview) {
      this.closeOnThisDayPreview(undefined, true);
    }
  }

  @HostListener("window:resize")
  onWindowResize(): void {
    if (this.calendarPreview) {
      this.closeCalendarPreview(undefined, true);
    }
    if (this.cbtPreview) {
      this.closeCbtPreview(undefined, true);
    }
    if (this.importantDayPreview) {
      this.closeImportantDayPreview(undefined, true);
    }
    if (this.occasionPreview) {
      this.closeOccasionPreview(undefined, true);
    }
    if (this.onThisDayPreview) {
      this.closeOnThisDayPreview(undefined, true);
    }
  }

  ngOnDestroy(): void {
    document.removeEventListener("scroll", this.capturedScrollHandler, true);

    // Clean up animation frame to prevent memory leaks
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    if (this.previewCloseTimerId) {
      window.clearTimeout(this.previewCloseTimerId);
    }
    if (this.cbtPreviewCloseTimerId) {
      window.clearTimeout(this.cbtPreviewCloseTimerId);
    }
    if (this.importantDayPreviewCloseTimerId) {
      window.clearTimeout(this.importantDayPreviewCloseTimerId);
    }
    if (this.occasionPreviewCloseTimerId) {
      window.clearTimeout(this.occasionPreviewCloseTimerId);
    }
    if (this.onThisDayPreviewCloseTimerId) {
      window.clearTimeout(this.onThisDayPreviewCloseTimerId);
    }
    if (this.calendarFlipTimerId) {
      window.clearTimeout(this.calendarFlipTimerId);
    }
  }
}
