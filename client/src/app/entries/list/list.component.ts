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
import { ViewToggleComponent } from "../../shared/components/view-toggle/view-toggle.component";
import { SearchResultsComponent } from "../../shared/components/search-results/search-results.component";
import { EntriesService } from "../../core/services/entries.service";
import { SearchService } from "../../core/services/search.service";
import { DailyEntry, DreamEntry } from "../../core/models/entry.model";

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

type CalendarStatus = "none" | "daily" | "dream" | "complete";
type CalendarPreviewType = "daily" | "dream";

type CalendarDay = {
  date: Date;
  dayNumber: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  isFuture: boolean;
  status: CalendarStatus;
  entries: EntryItem[];
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
    ViewToggleComponent,
    SearchResultsComponent,
  ],
  styleUrl: "./list.component.css",
  template: `
    <div class="list-container">
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
              <app-view-toggle
                [value]="currentView"
                [emphasiseActiveFilter]="hasFocusedTypeFilter()"
                (viewChange)="onViewChange($event)"
              ></app-view-toggle>
              <div class="display-mode-toggle" aria-label="Entries display mode">
                <button
                  mat-stroked-button
                  type="button"
                  [class.active]="displayMode === 'cards'"
                  (click)="setDisplayMode('cards')"
                >
                  Cards
                </button>
                <button
                  mat-stroked-button
                  type="button"
                  [class.active]="displayMode === 'calendar'"
                  (click)="setDisplayMode('calendar')"
                >
                  Calendar
                </button>
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
              (click)="scrollTimeline(-1)"
              [disabled]="timelineScrollIndex <= minScrollIndex"
            >
              <mat-icon>chevron_left</mat-icon>
            </button>

            <div class="timeline-months">
              <div
                class="month-item"
                *ngFor="let item of visibleMonths"
                [class.current]="item.isCurrent"
                [class.selected]="item.isSelected"
                [class.future]="item.isFuture"
                [class.clickable]="!item.isFuture"
                (click)="selectMonth(item)"
              >
                <div class="year">{{ item.year }}</div>
                <div class="month">{{ item.label }}</div>
                <div
                  class="entry-count-badge"
                  *ngIf="item.entryCount && !item.isFuture"
                >
                  {{ item.entryCount }}
                </div>
              </div>
            </div>

            <button
              mat-icon-button
              (click)="scrollTimeline(1)"
              [disabled]="timelineScrollIndex >= maxScrollIndex"
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

          <div class="selected-day-banner" *ngIf="selectedDay && displayMode === 'cards'">
            <div>
              <strong>{{ getSelectedDayLabel() }}</strong>
              <span>{{ totalEntries }} matching entr{{ totalEntries === 1 ? 'y' : 'ies' }}</span>
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

          <div
            class="filter-status-banner"
            *ngIf="hasFocusedTypeFilter()"
            [class.filter-status-daily]="currentView === 'daily'"
            [class.filter-status-dreams]="currentView === 'dreams'"
            role="status"
            aria-live="polite"
          >
            <div class="filter-status-copy">
              <mat-icon>{{
                currentView === "daily" ? "book" : "nights_stay"
              }}</mat-icon>
              <div>
                <strong>{{ getFocusedFilterHeading() }}</strong>
                <span>{{ getFocusedFilterDescription() }}</span>
              </div>
            </div>
            <button
              mat-stroked-button
              type="button"
              class="filter-status-clear"
              (click)="onViewChange('all')"
            >
              Show all entries
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
            <div class="no-entries-message" *ngIf="paginatedEntries.length === 0">
              <mat-card class="no-entries-card">
                <mat-card-content>
                  <mat-icon class="no-entries-icon">calendar_today</mat-icon>
                  <h3>No entries found</h3>
                  <p>
                    No entries for this time period. Start documenting your
                    journey!
                  </p>
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
                tabindex="0"
                role="button"
                [attr.aria-label]="'Open ' + getEntryTitle(entry)"
                (click)="openEntryDetail(entry)"
                (keydown.enter)="openEntryDetail(entry)"
                (keydown.space)="onCardSpacebar($event, entry)"
              >
                <mat-card-header>
                  <mat-icon mat-card-avatar>
                    {{ entry.type === "dream" ? "nights_stay" : "book" }}
                  </mat-icon>
                  <mat-card-title>{{ getEntryTitle(entry) }}</mat-card-title>
                  <mat-card-subtitle>{{
                    entry.entry_date | date: "dd/MM/yyyy"
                  }}</mat-card-subtitle>
                </mat-card-header>

                <mat-card-content>
                  <div
                    class="entry-card-image"
                    *ngIf="getEntryCardImageUrl(entry) as entryImageUrl; else entryCardPlaceholder"
                  >
                    <img [src]="entryImageUrl" alt="" />
                  </div>
                  <ng-template #entryCardPlaceholder>
                    <div class="entry-image-placeholder">
                      <mat-icon>pie_chart</mat-icon>
                    </div>
                  </ng-template>
                  <div class="entry-card-copy">
                    <p class="entry-snippet">{{ getEntrySnippet(entry) }}</p>
                    <mat-chip-set *ngIf="getTags(entry).length > 0">
                      <mat-chip
                        *ngFor="let tag of getTags(entry).slice(0, 2)"
                        [class.duplicate-tag-chip]="isDuplicateTag(tag)"
                        (click)="searchForTag(tag)"
                        >{{ tag }}</mat-chip
                      >
                    </mat-chip-set>
                  </div>
                </mat-card-content>

                <mat-card-actions>
                  <button
                    mat-button
                    color="primary"
                    (click)="openEntryDetail(entry, $event)"
                  >
                    VIEW ENTRY
                  </button>
                  <button
                    mat-icon-button
                    [disabled]="true"
                    title="Coming soon"
                    aria-label="Favourite coming soon"
                  >
                    <mat-icon>favorite_border</mat-icon>
                  </button>
                  <button
                    mat-icon-button
                    [disabled]="true"
                    title="Coming soon"
                    aria-label="Share coming soon"
                  >
                    <mat-icon>share</mat-icon>
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
                  <span class="legend-item">
                    <span class="legend-swatch none"></span>
                    No entries
                  </span>
                  <span class="legend-item">
                    <span class="legend-swatch daily"></span>
                    Daily only
                  </span>
                  <span class="legend-item">
                    <span class="legend-swatch dream"></span>
                    Dream only
                  </span>
                  <span class="legend-item">
                    <span class="legend-swatch complete"></span>
                    Daily and dream
                  </span>
                </div>
              </div>

              <div class="calendar-weekdays" aria-hidden="true">
                <span *ngFor="let weekday of weekdays">{{ weekday }}</span>
              </div>

              <div class="calendar-grid">
                <div
                  class="calendar-day"
                  *ngFor="let day of calendarDays"
                  [class.outside-month]="!day.isCurrentMonth"
                  [class.unavailable]="day.isFuture"
                  [class.today]="day.isToday"
                  [class.has-entries]="day.status !== 'none'"
                  [class.status-daily]="day.status === 'daily'"
                  [class.status-dream]="day.status === 'dream'"
                  [class.status-complete]="day.status === 'complete'"
                  [attr.role]="day.isCurrentMonth && !day.isFuture ? 'button' : null"
                  [attr.tabindex]="day.isCurrentMonth && !day.isFuture ? 0 : null"
                  [attr.aria-label]="getCalendarDayLabel(day)"
                  (click)="onCalendarDaySelect(day)"
                  (keydown.enter)="onCalendarDayKeydown($event, day)"
                  (keydown.space)="onCalendarDayKeydown($event, day)"
                >
                  <span class="calendar-day-number">{{ day.dayNumber }}</span>
                  <div class="calendar-day-icons" *ngIf="day.entries.length > 0; else emptyDayAction">
                    <button
                      type="button"
                      class="calendar-entry-icon daily"
                      *ngIf="getEntryCountByType(day, 'daily') > 0"
                      [class.preview-active]="isCalendarPreviewActive(day, 'daily')"
                      [attr.aria-label]="'Preview daily entries for ' + getCalendarDayDateLabel(day)"
                      (click)="toggleCalendarPreview(day, 'daily', $event)"
                    >
                      <mat-icon>book</mat-icon>
                      <span class="calendar-entry-count">{{ getEntryCountByType(day, 'daily') }}</span>
                    </button>
                    <button
                      type="button"
                      class="calendar-entry-icon dream"
                      *ngIf="getEntryCountByType(day, 'dream') > 0"
                      [class.preview-active]="isCalendarPreviewActive(day, 'dream')"
                      [attr.aria-label]="'Preview dream entries for ' + getCalendarDayDateLabel(day)"
                      (click)="toggleCalendarPreview(day, 'dream', $event)"
                    >
                      <mat-icon>nights_stay</mat-icon>
                      <span class="calendar-entry-count">{{ getEntryCountByType(day, 'dream') }}</span>
                    </button>
                  </div>
                  <ng-template #emptyDayAction>
                    <span class="calendar-day-plus" aria-hidden="true">
                      <mat-icon>add</mat-icon>
                    </span>
                  </ng-template>
                </div>
              </div>
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
                      <span>{{ getEntryTitle(entry) }}</span>
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
            </section>
          </ng-template>
        </ng-container>
      </ng-container>
    </div>
  `,
})
export class ListComponent implements OnInit, OnDestroy {
  private entriesService = inject(EntriesService);
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
  paginatedEntries: any[] = [];
  displayMode: "cards" | "calendar" = "cards";
  selectedDay: string | null = null;
  calendarDays: CalendarDay[] = [];
  readonly weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  // Current data
  currentView: "all" | "daily" | "dreams" = "all";
  dailyEntries: EntryItem[] = [];
  dreamEntries: EntryItem[] = [];
  filteredEntries: EntryItem[] = [];
  private hasExplicitMonthSelection = false;
  private pendingMonthSelection: { monthIndex: number; year: number } | null =
    null;
  calendarPreview: CalendarPreviewState | null = null;
  private previewCloseTimerId: number | null = null;

  exitSearch(): void {
    this.searchService.clear();
  }

  ngOnInit(): void {
    // Initialize timeline
    this.initializeTimeline();

    this.route.queryParamMap.subscribe((params) => {
      const type = params.get("type");
      if (type === "daily" || type === "dreams") {
        this.currentView = type;
      } else {
        this.currentView = "all";
      }

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
        this.searchService.search(searchQuery).subscribe({
          next: (response) => {
            console.log("Search completed successfully:", response);
          },
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
    const allEntries = [...this.dailyEntries, ...this.dreamEntries];

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
    const allEntries = [...this.dailyEntries, ...this.dreamEntries];
    if (allEntries.length > 0) {
      const earliestDate = new Date(
        Math.min(...allEntries.map((e) => new Date(e.entry_date).getTime())),
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

  selectMonth(month: TimelineMonth): void {
    // Allow clicking on current month always, block only future months beyond today
    if (month.isFuture) return;

    this.hasExplicitMonthSelection = true;
    this.selectedDay = null;

    // Update selection state
    this.allMonths.forEach((m) => (m.isSelected = false));
    month.isSelected = true;
    this.selectedMonth = month;

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
    let dailyLoaded = false;
    let dreamLoaded = false;

    const checkAndGenerateTimeline = () => {
      if (dailyLoaded && dreamLoaded) {
        this.generateTimelineFromEntries();
        this.applyInitialMonthSelection();
        this.filterEntries();
        this.updatePaginatedEntries();
      }
    };

    this.entriesService.getDailyEntries().subscribe((entries) => {
      this.dailyEntries = entries.map((e) => ({ ...e, type: "daily" }));
      dailyLoaded = true;
      checkAndGenerateTimeline();
    });

    this.entriesService.getDreamEntries().subscribe((entries) => {
      this.dreamEntries = entries.map((e) => ({ ...e, type: "dream" }));
      dreamLoaded = true;
      checkAndGenerateTimeline();
    });
  }

  onViewChange(view: string): void {
    this.closeCalendarPreview();
    this.currentView = view as "all" | "daily" | "dreams";
    this.selectedDay = null;

    // Preserve an explicitly selected month when switching filters.
    if (!this.hasExplicitMonthSelection) {
      this.autoSelectLatestMonthForView(true);
    }

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
    this.displayMode = mode;
    if (mode === "calendar") {
      this.selectedDay = null;
      this.filterEntries();
      this.currentPage = 0;
      this.updatePaginatedEntries();
    }
  }

  clearSelectedDay(): void {
    this.closeCalendarPreview();
    this.selectedDay = null;
    this.displayMode = "calendar";
    this.filterEntries();
    this.currentPage = 0;
    this.updatePaginatedEntries();
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

  hasFocusedTypeFilter(): boolean {
    return this.currentView === "daily" || this.currentView === "dreams";
  }

  getFocusedFilterHeading(): string {
    if (this.currentView === "daily") {
      return "Filtering diary entries";
    }

    if (this.currentView === "dreams") {
      return "Filtering dream entries";
    }

    return "Showing all entries";
  }

  getFocusedFilterDescription(): string {
    if (this.currentView === "daily") {
      return "Cards and calendar are currently limited to Daily entries only.";
    }

    if (this.currentView === "dreams") {
      return "Cards and calendar are currently limited to Dream entries only.";
    }

    return "All entry types are visible.";
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

    return `${dateLabel}. ${statusLabel}. ${entryCountLabel}.`;
  }

  getEntryCountByType(day: CalendarDay, type: "daily" | "dream"): number {
    return day.entries.filter((entry) => entry.type === type).length;
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

  onCalendarDaySelect(day: CalendarDay): void {
    this.closeCalendarPreview();
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

    this.currentView = "all";
    this.selectedDay = this.toDateKey(day.date);
    this.displayMode = "cards";
    this.currentPage = 0;
    this.filterEntries();
    this.updatePaginatedEntries();
  }

  onCalendarDayKeydown(event: Event, day: CalendarDay): void {
    event.preventDefault();
    this.onCalendarDaySelect(day);
  }

  openCalendarPreviewFullView(event: Event): void {
    event.stopPropagation();

    if (!this.calendarPreview) {
      return;
    }

    this.currentView = this.calendarPreview.type === "daily" ? "daily" : "dreams";
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
    const queryParams: any = { date: formattedDate };

    // Add entry type based on current view
    if (this.currentView === "dreams") {
      queryParams.type = "dream";
    } else if (this.currentView === "daily") {
      queryParams.type = "daily";
    }
    // For 'all', let the create component use its default (daily)

    this.router.navigate(["/entries/create"], {
      queryParams,
    });
  }

  resetToCurrentMonth(): void {
    // Clear previous selection
    this.allMonths.forEach((m) => (m.isSelected = false));

    // Select current month
    const currentMonth = this.allMonths.find((m) => m.isCurrent);
    if (currentMonth) {
      currentMonth.isSelected = true;
      this.selectedMonth = currentMonth;

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
    return this.dailyEntries.length + this.dreamEntries.length > 0;
  }

  jumpToFirstEntry(): void {
    const allEntries = [...this.dailyEntries, ...this.dreamEntries];
    if (allEntries.length === 0) return;

    // Find earliest entry
    const earliestEntry = allEntries.reduce((earliest, entry) =>
      new Date(entry.entry_date) < new Date(earliest.entry_date)
        ? entry
        : earliest,
    );
    const earliestDate = new Date(earliestEntry.entry_date);

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
    let entries: EntryItem[] = [];

    // First filter by view type
    if (this.currentView === "daily") {
      entries = this.dailyEntries;
    } else if (this.currentView === "dreams") {
      entries = this.dreamEntries;
    } else {
      entries = [...this.dailyEntries, ...this.dreamEntries];
    }

    // Then filter by selected month/timeline if one is selected
    if (this.selectedMonth) {
      entries = entries.filter((entry) => {
        const entryDate = new Date(entry.entry_date);
        return (
          entryDate.getMonth() === (this.selectedMonth as any).monthIndex &&
          entryDate.getFullYear() === this.selectedMonth!.year
        );
      });
    }

    this.buildCalendarDays(entries);

    if (this.selectedDay) {
      entries = entries.filter(
        (entry) => this.toDateKey(new Date(entry.entry_date)) === this.selectedDay,
      );
    }

    // Sort by date (newest first)
    this.filteredEntries = entries.sort(
      (a, b) =>
        new Date(b.entry_date).getTime() - new Date(a.entry_date).getTime(),
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
    const entriesForCount =
      this.currentView === "daily"
        ? this.dailyEntries
        : this.currentView === "dreams"
          ? this.dreamEntries
          : [...this.dailyEntries, ...this.dreamEntries];

    this.allMonths.forEach((month) => {
      const count = entriesForCount.filter((entry) => {
        const entryDate = new Date(entry.entry_date);
        return (
          entryDate.getMonth() === (month as any).monthIndex &&
          entryDate.getFullYear() === month.year
        );
      }).length;

      month.entryCount = count > 0 ? count : undefined;
    });

    this.updateVisibleMonths();
  }

  getEntryTitle(entry: any): string {
    if (entry.type === "dream" && entry.title) {
      return `"${entry.title}"`;
    }
    if (entry.type === "daily") {
      // Use the title field from database if available
      if (entry.title) {
        return entry.title;
      }
      // Fallback to old logic for entries without titles
      const [title] = this.splitDailyMessage(entry.user_message || "");
      return title || "Daily Entry";
    }
    return "Dream Entry";
  }

  getEntrySnippet(entry: any): string {
    const rawText =
      entry.type === "daily"
        ? this.splitDailyMessage(entry.user_message || "")[1]
        : entry.plot || entry.user_message || "";

    return rawText.replace(/\s+/g, " ").trim();
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

  getTags(entry: any): string[] {
    return (entry.tags || "")
      .split(",")
      .map((tag: string) => tag.trim())
      .filter((tag: string) => tag);
  }

  isDuplicateTag(tag: string): boolean {
    return tag.trim() === "*Duplicate*";
  }

  searchForTag(tag: string): void {
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
    const startOffset = (firstDayOfMonth.getDay() + 6) % 7;
    const gridStartDate = new Date(year, monthIndex, 1 - startOffset);
    const todayKey = this.toDateKey(new Date());
    const entriesByDate = new Map<string, EntryItem[]>();

    entries.forEach((entry) => {
      const key = this.toDateKey(new Date(entry.entry_date));
      const dateEntries = entriesByDate.get(key) ?? [];
      dateEntries.push(entry);
      entriesByDate.set(key, dateEntries);
    });

    this.calendarDays = Array.from({ length: 42 }, (_, index) => {
      const date = new Date(gridStartDate);
      date.setDate(gridStartDate.getDate() + index);
      const key = this.toDateKey(date);
      const dateEntries = entriesByDate.get(key) ?? [];

      return {
        date,
        dayNumber: date.getDate(),
        isCurrentMonth: date.getMonth() === monthIndex,
        isToday: key === todayKey,
        isFuture: date.getTime() > new Date().setHours(23, 59, 59, 999),
        status: this.getCalendarStatus(dateEntries),
        entries: dateEntries,
      };
    });
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

  openEntryDetail(entry: any, event?: Event): void {
    this.closeCalendarPreview();
    event?.stopPropagation();
    this.router.navigate(["/entries", entry.id], {
      queryParams: this.getDetailContextParams(),
    });
  }

  onCardSpacebar(event: Event, entry: any): void {
    event.preventDefault();
    this.openEntryDetail(entry);
  }

  private getDetailContextParams(): Record<string, string | number> {
    const params: Record<string, string | number> = {};

    if (this.currentView !== "all") {
      params["type"] = this.currentView;
    }

    if (this.selectedMonth) {
      params["month"] = (this.selectedMonth as any).monthIndex + 1;
      params["year"] = this.selectedMonth.year;
    }

    return params;
  }

  private updateListQueryParams(): void {
    const queryParams: Record<string, string | number> = {
      ...this.getDetailContextParams(),
    };

    const searchQuery = this.route.snapshot.queryParamMap.get("search");
    if (searchQuery) {
      queryParams["search"] = searchQuery;
    }

    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
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
      return;
    }

    if (this.currentView === "all") {
      if (!this.hasExplicitMonthSelection) {
        this.selectCurrentMonth(false);
      }
      return;
    }

    if (!this.hasExplicitMonthSelection) {
      this.autoSelectLatestMonthForView();
    }
  }

  private autoSelectLatestMonthForView(animate = false): void {
    const entriesForView =
      this.currentView === "daily"
        ? this.dailyEntries
        : this.currentView === "dreams"
          ? this.dreamEntries
          : [...this.dailyEntries, ...this.dreamEntries];

    if (entriesForView.length === 0) {
      return;
    }

    const latestEntry = entriesForView.reduce((latest, candidate) =>
      new Date(candidate.entry_date) > new Date(latest.entry_date)
        ? candidate
        : latest,
    );

    this.selectMonthByDate(new Date(latestEntry.entry_date), false, animate);
  }

  private selectCurrentMonth(explicit: boolean): void {
    const now = new Date();
    this.selectMonthByDate(now, explicit);
  }

  private selectMonthByDate(date: Date, explicit: boolean, animate = false): void {
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

  getCalendarPreviewImageStyle(entry: EntryItem): string | null {
    const imageUrl = this.getCalendarPreviewImageUrl(entry);
    return imageUrl ? `url("${imageUrl.replace(/"/g, '\\"')}")` : null;
  }

  getEntryCardImageUrl(entry: EntryItem): string | null {
    return this.getCalendarPreviewImageUrl(entry);
  }

  private getCalendarPreviewImageUrl(entry: EntryItem): string | null {
    const raw = typeof entry.image_url === "string" ? entry.image_url.trim() : "";
    return raw.length > 0 ? raw : null;
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

  @HostListener("document:click", ["$event"])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement | null;
    if (!target || !this.calendarPreview) {
      return;
    }

    if (target.closest(".calendar-preview-deck, .calendar-entry-icon")) {
      return;
    }

    this.closeCalendarPreview();
  }

  @HostListener("document:keydown.escape", ["$event"])
  onEscapeKey(event: KeyboardEvent): void {
    if (!this.calendarPreview) {
      return;
    }

    event.preventDefault();
    this.closeCalendarPreview();
  }

  @HostListener("window:scroll")
  onWindowScroll(): void {
    if (this.calendarPreview) {
      this.closeCalendarPreview(undefined, true);
    }
  }

  @HostListener("window:resize")
  onWindowResize(): void {
    if (this.calendarPreview) {
      this.closeCalendarPreview(undefined, true);
    }
  }

  ngOnDestroy(): void {
    // Clean up animation frame to prevent memory leaks
    if (this.animationFrameId) {
      cancelAnimationFrame(this.animationFrameId);
    }
    if (this.previewCloseTimerId) {
      window.clearTimeout(this.previewCloseTimerId);
    }
  }
}
