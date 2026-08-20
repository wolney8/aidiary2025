import {
  Component,
  DestroyRef,
  HostListener,
  OnInit,
  inject,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { HttpErrorResponse } from "@angular/common/http";
import { Router, RouterLink } from "@angular/router";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatMenuModule } from "@angular/material/menu";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatTooltipModule } from "@angular/material/tooltip";
import {
  trigger,
  style,
  transition,
  animate,
  query,
  stagger,
} from "@angular/animations";
import { AuthService } from "../core/services/auth.service";
import { DashboardService } from "../core/services/dashboard.service";
import {
  DashboardActivityType,
  DashboardDreamLatest,
  DashboardImportantDayCue,
  DashboardOverview,
  DashboardQuickAction,
  DashboardRange,
  DashboardSeasonOption,
  DashboardSeriesPoint,
  DashboardTheme,
  DashboardThemeDriftItem,
} from "../core/models/dashboard.model";

type DashboardChartMetric = "daily" | "dream" | "mood";

interface DashboardChartSelection {
  point: DashboardSeriesPoint;
  metric: DashboardChartMetric;
}

interface DashboardChartPosition {
  left: number;
  top: number;
}

interface DashboardChartTick {
  x: string;
  label: string;
  fullLabel: string;
}

@Component({
  selector: "app-dashboard",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
  ],
  animations: [
    trigger("dashboardReveal", [
      transition(":enter", [
        query(
          ".dashboard-card, .dashboard-hero-panel",
          [
            style({ opacity: 0, transform: "translateY(14px) scale(0.985)" }),
            stagger(55, [
              animate(
                "320ms cubic-bezier(0.2, 0, 0, 1)",
                style({ opacity: 1, transform: "translateY(0) scale(1)" }),
              ),
            ]),
          ],
          { optional: true },
        ),
      ]),
    ]),
  ],
  template: `
    <section
      class="dashboard-shell"
      [class.is-loading]="isLoading"
      aria-labelledby="dashboard-heading"
      data-testid="dashboard-page"
      @dashboardReveal
    >
      <header class="dashboard-hero-panel" data-testid="dashboard-hero-panel">
        <div class="dashboard-hero-copy">
          <p class="dashboard-eyebrow">OpenMynd Dashboard</p>
          <h1 id="dashboard-heading">{{ greeting }}, {{ displayName }}</h1>
          <p>
            Your private rhythm, themes, dreams, and reflections in one place.
          </p>
        </div>
        <div class="dashboard-hero-actions" aria-label="Dashboard actions">
          <a
            mat-flat-button
            class="dashboard-primary-action"
            routerLink="/entries/create"
            data-testid="dashboard-new-entry-link"
          >
            <mat-icon aria-hidden="true">edit_square</mat-icon>
            <span>New entry</span>
          </a>
          <button
            mat-stroked-button
            type="button"
            class="dashboard-secondary-action"
            (click)="loadOverview()"
            [disabled]="isLoading"
            data-testid="dashboard-refresh-button"
          >
            <mat-icon aria-hidden="true">refresh</mat-icon>
            <span>Refresh</span>
          </button>
        </div>
      </header>

      <div class="dashboard-loading-overlay" *ngIf="isLoading" role="status" aria-live="polite">
        <div class="dashboard-loading-panel">
          <mat-progress-spinner diameter="36" mode="indeterminate"></mat-progress-spinner>
          <span>Building your dashboard…</span>
        </div>
      </div>

      <div class="dashboard-status-card dashboard-card is-error" *ngIf="errorMessage" role="alert">
        <mat-icon aria-hidden="true">error</mat-icon>
        <span>{{ errorMessage }}</span>
      </div>

      <ng-container *ngIf="overview as data">
        <div class="dashboard-grid">
          <article
            class="dashboard-card dashboard-streak-goal-card"
            aria-labelledby="dashboard-streak-heading"
            data-testid="dashboard-streak-card"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">Momentum</p>
                <h2 id="dashboard-streak-heading">Writing rhythm</h2>
              </div>
              <span
                class="dashboard-reward-pill"
                [class.is-active]="data.streak.weekly_progress >= 100"
              >
                <mat-icon aria-hidden="true">
                  {{ data.streak.weekly_progress >= 100 ? "local_fire_department" : "bolt" }}
                </mat-icon>
                {{ data.streak.weekly_progress >= 100 ? "Goal met" : "In progress" }}
              </span>
            </div>

            <div class="dashboard-ring-layout">
              <div
                class="dashboard-progress-ring"
                role="meter"
                aria-label="Weekly writing goal progress"
                aria-valuemin="0"
                aria-valuemax="100"
                [attr.aria-valuenow]="data.streak.weekly_progress"
              >
                <svg viewBox="0 0 96 96" aria-hidden="true">
                  <circle class="ring-track" cx="48" cy="48" r="40"></circle>
                  <circle
                    class="ring-progress"
                    cx="48"
                    cy="48"
                    r="40"
                    [attr.stroke-dasharray]="ringCircumference"
                    [attr.stroke-dashoffset]="getRingOffset(data.streak.weekly_progress)"
                  ></circle>
                </svg>
                <span class="dashboard-ring-value">
                  {{ data.streak.weekly_progress }}%
                </span>
              </div>

              <dl class="dashboard-streak-metrics">
                <div>
                  <dt>Current streak</dt>
                  <dd>{{ data.streak.current_days }}</dd>
                </div>
                <div>
                  <dt>This week</dt>
                  <dd>{{ data.streak.week_count }} / {{ data.streak.weekly_goal }}</dd>
                </div>
                <div>
                  <dt>This month</dt>
                  <dd>{{ data.streak.month_count }}</dd>
                </div>
                <div>
                  <dt>Best run</dt>
                  <dd>{{ data.streak.best_days }}</dd>
                </div>
              </dl>
            </div>
            <p class="dashboard-support-text">
              Counting {{ formatIncludedTypes(data.streak.included_entry_types) }}.
            </p>
          </article>

          <article
            class="dashboard-card dashboard-analytics-chart"
            [class.is-expanded]="isChartExpanded"
            aria-labelledby="dashboard-analytics-heading"
            data-testid="dashboard-analytics-card"
            [attr.aria-busy]="isChartLoading"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">Patterns</p>
                <h2 id="dashboard-analytics-heading">Words and mood</h2>
              </div>
              <div class="dashboard-range-group" aria-label="Dashboard date range">
                <button
                  *ngFor="let option of rangeOptions"
                  type="button"
                  class="dashboard-range-chip"
                  [class.is-selected]="!selectedSeason && selectedRange === option.value"
                  [attr.aria-pressed]="!selectedSeason && selectedRange === option.value"
                  (click)="selectRange(option.value)"
                  [disabled]="isChartLoading"
                  [attr.data-testid]="'dashboard-range-' + option.value"
                >
                  {{ option.label }}
                </button>
                <label class="dashboard-season-select" *ngIf="availableSeasonOptions.length">
                  <span>Season</span>
                  <select
                    [value]="selectedSeason"
                    (change)="selectSeason($event)"
                    [disabled]="isChartLoading"
                    data-testid="dashboard-season-select"
                  >
                    <option value="">None</option>
                    <option *ngFor="let option of availableSeasonOptions" [value]="option.value">
                      {{ option.label }}
                    </option>
                  </select>
                </label>
                <button
                  type="button"
                  class="dashboard-chart-expand"
                  [attr.aria-expanded]="isChartExpanded"
                  [attr.aria-label]="isChartExpanded ? 'Collapse words and mood chart' : 'Expand words and mood chart'"
                  (click)="toggleChartExpanded()"
                  data-testid="dashboard-chart-expand-toggle"
                >
                  <mat-icon aria-hidden="true">
                    {{ isChartExpanded ? "close_fullscreen" : "open_in_full" }}
                  </mat-icon>
                </button>
              </div>
            </div>

            <div
              class="dashboard-chart"
              [class.is-animating]="isChartAnimating"
              [class.is-loading]="isChartLoading"
              role="group"
              [attr.aria-label]="getChartAriaLabel(data.series)"
            >
              <div class="dashboard-chart-loading" *ngIf="isChartLoading" role="status">
                <mat-progress-spinner diameter="30" mode="indeterminate"></mat-progress-spinner>
                <span>Updating chart…</span>
              </div>
              <div
                class="dashboard-chart-empty"
                *ngIf="!isChartLoading && chartSeries.length === 0"
                role="status"
              >
                <mat-icon aria-hidden="true">monitoring</mat-icon>
                <span>No chart data for this selection.</span>
              </div>
              <svg
                viewBox="0 0 640 220"
                preserveAspectRatio="none"
                data-testid="dashboard-word-mood-chart"
              >
                <g class="chart-grid">
                  <line x1="20" y1="46" x2="620" y2="46"></line>
                  <line x1="20" y1="112" x2="620" y2="112"></line>
                  <line x1="20" y1="178" x2="620" y2="178"></line>
                </g>
                <g class="chart-axis-labels" aria-hidden="true">
                  <text x="22" y="28">Words</text>
                  <text x="520" y="28">Mood 1-5</text>
                </g>
                <g class="chart-value-ticks" aria-hidden="true">
                  <text x="22" y="49">{{ chartMaxWords }}</text>
                  <text x="22" y="115">{{ chartMidWords }}</text>
                  <text x="22" y="181">0</text>
                  <text x="618" y="49">5</text>
                  <text x="618" y="115">3</text>
                  <text x="618" y="181">1</text>
                </g>
                <g class="chart-time-ticks" aria-hidden="true">
                  <g *ngFor="let tick of chartTimeTicks; trackBy: trackChartTick">
                    <line [attr.x1]="tick.x" y1="181" [attr.x2]="tick.x" y2="187"></line>
                    <text [attr.x]="tick.x" y="204">{{ tick.label }}</text>
                  </g>
                </g>
                <g *ngFor="let point of chartSeries; let i = index; trackBy: trackSeriesPoint">
                  <rect
                    class="chart-bar daily"
                    role="button"
                    tabindex="0"
                    [attr.x]="getChartX(i)"
                    [attr.y]="getDailyBarY(point)"
                    [attr.width]="getBarWidth()"
                    [attr.height]="getDailyBarHeight(point)"
                    [attr.aria-label]="getChartPointTitle(point, 'daily')"
                    (mouseenter)="selectChartPoint(point, 'daily', $event)"
                    (focus)="selectChartPoint(point, 'daily')"
                    (click)="selectChartPoint(point, 'daily', $event)"
                    (keydown.enter)="selectChartPoint(point, 'daily')"
                    (keydown.space)="selectChartPoint(point, 'daily'); $event.preventDefault()"
                    [attr.data-testid]="'dashboard-chart-daily-' + point.date"
                    rx="6"
                  >
                    <title>{{ getChartPointTitle(point, "daily") }}</title>
                  </rect>
                  <rect
                    class="chart-bar dream"
                    role="button"
                    tabindex="0"
                    [attr.x]="getChartX(i)"
                    [attr.y]="getDreamBarY(point)"
                    [attr.width]="getBarWidth()"
                    [attr.height]="getDreamBarHeight(point)"
                    [attr.aria-label]="getChartPointTitle(point, 'dream')"
                    (mouseenter)="selectChartPoint(point, 'dream', $event)"
                    (focus)="selectChartPoint(point, 'dream')"
                    (click)="selectChartPoint(point, 'dream', $event)"
                    (keydown.enter)="selectChartPoint(point, 'dream')"
                    (keydown.space)="selectChartPoint(point, 'dream'); $event.preventDefault()"
                    [attr.data-testid]="'dashboard-chart-dream-' + point.date"
                    rx="6"
                  >
                    <title>{{ getChartPointTitle(point, "dream") }}</title>
                  </rect>
                </g>
                <polyline
                  *ngIf="chartMoodPolyline"
                  class="chart-mood-line"
                  [attr.points]="chartMoodPolyline"
                ></polyline>
                <circle
                  *ngFor="let point of chartMoodPoints; trackBy: trackMoodPoint"
                  class="chart-mood-point"
                  role="button"
                  tabindex="0"
                  [attr.aria-label]="point.title"
                  [attr.cx]="point.x"
                  [attr.cy]="point.y"
                  (mouseenter)="selectChartPoint(point.source, 'mood', $event)"
                  (focus)="selectChartPoint(point.source, 'mood')"
                  (click)="selectChartPoint(point.source, 'mood', $event)"
                  (keydown.enter)="selectChartPoint(point.source, 'mood')"
                  (keydown.space)="selectChartPoint(point.source, 'mood'); $event.preventDefault()"
                  [attr.data-testid]="'dashboard-chart-mood-' + point.source.date"
                  r="5"
                >
                  <title>{{ point.title }}</title>
                </circle>
              </svg>
              <div
                class="dashboard-chart-detail"
                *ngIf="selectedChartPoint as selected"
                [style.left.%]="selectedChartPosition.left"
                [style.top.%]="selectedChartPosition.top"
                role="dialog"
                aria-live="polite"
                aria-label="Chart point detail"
              >
                <div>
                  <strong>{{ getChartSelectionTitle(selected) }}</strong>
                  <span>{{ getChartSelectionDetail(selected) }}</span>
                </div>
                <button
                  type="button"
                  aria-label="Close chart detail"
                  (click)="clearChartPoint()"
                >
                  <mat-icon aria-hidden="true">close</mat-icon>
                </button>
              </div>
            </div>
            <div
              class="dashboard-chart-meta"
              *ngIf="activeThemeFilter || selectedSeason"
              aria-live="polite"
            >
              <span class="dashboard-chart-pill" *ngIf="selectedSeason">
                {{ getSelectedSeasonLabel() }}
              </span>
              <span class="dashboard-chart-pill" *ngIf="activeThemeFilter">
                Theme: {{ activeThemeFilter.label }}
              </span>
              <button
                *ngIf="activeThemeFilter"
                type="button"
                class="dashboard-chart-clear"
                (click)="clearThemeFocus()"
                [disabled]="isChartLoading"
              >
                Clear chart focus
              </button>
            </div>

            <ul class="dashboard-chart-legend" aria-label="Chart legend">
              <li><span class="legend-swatch daily"></span>Diary words</li>
              <li><span class="legend-swatch dream"></span>Dream words</li>
              <li><span class="legend-line"></span>Mood score</li>
            </ul>
          </article>

          <article
            class="dashboard-card dashboard-theme-cloud"
            aria-labelledby="dashboard-themes-heading"
            data-testid="dashboard-theme-card"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">Language</p>
                <h2 id="dashboard-themes-heading">Recurring themes</h2>
              </div>
            </div>
            <div class="dashboard-empty-state" *ngIf="data.themes.length === 0">
              <mat-icon aria-hidden="true">sell</mat-icon>
              <p>No themes yet. Add entries with tags, people, places, or dream symbols.</p>
            </div>
            <div class="dashboard-theme-list" *ngIf="data.themes.length">
              <button
                *ngFor="let theme of data.themes"
                type="button"
                class="dashboard-theme-pill"
                [class.is-selected]="selectedTheme?.label === theme.label"
                (click)="selectTheme(theme)"
                [matMenuTriggerFor]="themeMenu"
                [attr.aria-label]="getThemeAriaLabel(theme)"
                [attr.data-testid]="'dashboard-theme-' + normaliseTestId(theme.label)"
                [style.--theme-weight]="getThemeWeight(theme, data.themes)"
              >
                <span>{{ theme.label }}</span>
                <strong>{{ theme.count }}</strong>
              </button>
            </div>
            <mat-menu #themeMenu="matMenu" class="dashboard-theme-menu">
              <button mat-menu-item type="button" (click)="searchTheme()">
                <mat-icon aria-hidden="true">search</mat-icon>
                <span>Search for this theme</span>
              </button>
              <button mat-menu-item type="button" (click)="applyThemeFocus()" [disabled]="isChartLoading">
                <mat-icon aria-hidden="true">monitoring</mat-icon>
                <span>Focus dashboard chart</span>
              </button>
            </mat-menu>
          </article>

          <article
            class="dashboard-card dashboard-cbt-insights"
            aria-labelledby="dashboard-cbt-heading"
            data-testid="dashboard-cbt-card"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">CBT</p>
                <h2 id="dashboard-cbt-heading">Emotional insights</h2>
              </div>
              <a class="dashboard-card-link" routerLink="/cbt">Thought records</a>
            </div>
            <div class="dashboard-empty-state" *ngIf="data.cbt.total_records === 0">
              <mat-icon aria-hidden="true">psychology_alt</mat-icon>
              <p>No thought records yet. Use CBT records to track situations and balanced thoughts.</p>
            </div>
            <div class="dashboard-cbt-grid" *ngIf="data.cbt.total_records">
              <div class="dashboard-cbt-meter">
                <strong>{{ formatNullableNumber(data.cbt.average_before) }}</strong>
                <span>Before</span>
              </div>
              <div class="dashboard-cbt-meter">
                <strong>{{ formatNullableNumber(data.cbt.average_after) }}</strong>
                <span>After</span>
              </div>
              <div class="dashboard-cbt-meter is-change">
                <strong>{{ formatSignedNumber(data.cbt.average_change) }}</strong>
                <span>Change</span>
              </div>
            </div>
            <div class="dashboard-pattern-list" *ngIf="data.cbt.common_patterns.length">
              <span
                *ngFor="let pattern of data.cbt.common_patterns"
                class="dashboard-pattern-pill"
              >
                {{ pattern.label }} · {{ pattern.count }}
              </span>
            </div>
            <div class="dashboard-reflection-list" *ngIf="data.cbt.recent_reflections.length">
              <a
                *ngFor="let reflection of data.cbt.recent_reflections"
                class="dashboard-reflection-card"
                [routerLink]="['/cbt', reflection.id]"
              >
                <strong>{{ reflection.title }}</strong>
                <span>{{ reflection.balanced_thought || reflection.situation || "Review thought record" }}</span>
              </a>
            </div>
          </article>

          <article
            class="dashboard-card dashboard-dream-insights"
            aria-labelledby="dashboard-dream-heading"
            data-testid="dashboard-dream-card"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">Dreams</p>
                <h2 id="dashboard-dream-heading">Dream patterns</h2>
              </div>
              <a class="dashboard-card-link" routerLink="/entries" [queryParams]="{ type: 'dreams' }">Dream diary</a>
            </div>
            <div class="dashboard-empty-state" *ngIf="data.dream_insights.total_dreams === 0">
              <mat-icon aria-hidden="true">nights_stay</mat-icon>
              <p>No dreams in this range yet.</p>
            </div>
            <div class="dashboard-dream-layout" *ngIf="data.dream_insights.total_dreams">
              <div class="dashboard-recent-dreams">
                <a
                  *ngFor="let dream of data.dream_insights.recent"
                  class="dashboard-latest-dream-card"
                  [routerLink]="getActivityRouterLink(dream.route)"
                  [queryParams]="getActivityQueryParams(dream.route)"
                >
                  <span
                    class="dashboard-latest-dream-image"
                    [class.has-image]="dream.image_url"
                    [style.background-image]="dream.image_url ? 'url(' + dream.image_url + ')' : null"
                    aria-hidden="true"
                  >
                    <mat-icon *ngIf="!dream.image_url" aria-hidden="true">nights_stay</mat-icon>
                  </span>
                  <span class="dashboard-latest-dream-copy">
                    <small>Dream · {{ formatDate(dream.date) }}</small>
                    <strong>{{ dream.title }}</strong>
                    <span>{{ dream.summary || "Open dream" }}</span>
                    <span class="dashboard-dream-meta" *ngIf="getDreamMeta(dream).length">
                      {{ getDreamMeta(dream).join(" · ") }}
                    </span>
                  </span>
                </a>
              </div>
              <div class="dashboard-dream-groups">
                <div>
                  <h3>Repeating in recent dreams</h3>
                  <div class="dashboard-mini-pill-list">
                    <span *ngFor="let item of data.dream_insights.recent_repeating_patterns" class="dashboard-mini-pill">
                      {{ item.label }} <strong>{{ item.count }}</strong>
                    </span>
                    <span *ngIf="data.dream_insights.recent_repeating_patterns.length === 0" class="dashboard-muted">No pattern appears in 2+ recent dreams yet</span>
                  </div>
                </div>
                <div>
                  <h3>Symbols</h3>
                  <div class="dashboard-mini-pill-list">
                    <span *ngFor="let item of data.dream_insights.top_symbols" class="dashboard-mini-pill">
                      {{ item.label }} <strong>{{ item.count }}</strong>
                    </span>
                    <span *ngIf="data.dream_insights.top_symbols.length === 0" class="dashboard-muted">No symbols yet</span>
                  </div>
                </div>
                <div>
                  <h3>People and places</h3>
                  <div class="dashboard-mini-pill-list">
                    <span *ngFor="let item of getDreamPeoplePlaces(data)" class="dashboard-mini-pill">
                      {{ item.label }} <strong>{{ item.count }}</strong>
                    </span>
                    <span *ngIf="getDreamPeoplePlaces(data).length === 0" class="dashboard-muted">No people or places yet</span>
                  </div>
                </div>
              </div>
            </div>
          </article>

          <article
            class="dashboard-card dashboard-focus-sections"
            aria-labelledby="dashboard-focus-heading"
            data-testid="dashboard-focus-sections"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">Continuity</p>
                <h2 id="dashboard-focus-heading">Patterns over time</h2>
              </div>
            </div>
            <div class="dashboard-focus-grid">
              <section class="dashboard-focus-panel" aria-labelledby="dashboard-year-echo-heading">
                <div class="dashboard-focus-panel-heading">
                  <span class="dashboard-focus-icon memory">
                    <mat-icon aria-hidden="true">history</mat-icon>
                  </span>
                  <div>
                    <h3 id="dashboard-year-echo-heading">This time before</h3>
                    <span>{{ data.focus_sections.memory_echo.count }} memories</span>
                  </div>
                </div>
                <div class="dashboard-focus-list" *ngIf="data.focus_sections.memory_echo.items.length; else noMemoryEcho">
                  <a
                    *ngFor="let item of data.focus_sections.memory_echo.items"
                    [routerLink]="getActivityRouterLink(item.route)"
                    [queryParams]="getActivityQueryParams(item.route)"
                    class="dashboard-focus-link"
                  >
                    <strong>{{ item.title }}</strong>
                    <small>{{ formatDate(item.date) }}</small>
                    <span>{{ item.summary || "Open memory" }}</span>
                  </a>
                </div>
                <ng-template #noMemoryEcho>
                  <p class="dashboard-muted">No nearby prior-year entries yet.</p>
                </ng-template>
              </section>

              <section class="dashboard-focus-panel" aria-labelledby="dashboard-theme-drift-heading">
                <div class="dashboard-focus-panel-heading">
                  <span class="dashboard-focus-icon drift">
                    <mat-icon aria-hidden="true">trending_up</mat-icon>
                  </span>
                  <div>
                    <h3 id="dashboard-theme-drift-heading">Theme drift</h3>
                    <span>Last 30 days vs previous 30</span>
                  </div>
                </div>
                <div class="dashboard-drift-list" *ngIf="data.focus_sections.theme_drift.length; else noThemeDrift">
                  <button
                    *ngFor="let item of data.focus_sections.theme_drift"
                    type="button"
                    class="dashboard-drift-pill"
                    (click)="searchThemeLike(item)"
                    [attr.aria-label]="getThemeDriftLabel(item)"
                    [attr.title]="item.label"
                  >
                    <span>{{ formatCompactThemeLabel(item.label) }}</span>
                    <strong>{{ formatSignedNumber(item.change) }}</strong>
                  </button>
                </div>
                <ng-template #noThemeDrift>
                  <p class="dashboard-muted">Not enough recent theme movement yet.</p>
                </ng-template>
              </section>

              <section class="dashboard-focus-panel" aria-labelledby="dashboard-mood-anchor-heading">
                <div class="dashboard-focus-panel-heading">
                  <span class="dashboard-focus-icon mood">
                    <mat-icon aria-hidden="true">self_improvement</mat-icon>
                  </span>
                  <div>
                    <h3 id="dashboard-mood-anchor-heading">Mood anchors</h3>
                    <span>Themes often linked with higher mood</span>
                  </div>
                </div>
                <div class="dashboard-anchor-list" *ngIf="data.focus_sections.mood_anchors.length; else noMoodAnchors">
                  <button
                    *ngFor="let anchor of data.focus_sections.mood_anchors"
                    type="button"
                    class="dashboard-anchor-card"
                    [ngClass]="getMoodAnchorTone(anchor.average_mood)"
                    (click)="searchThemeLike(anchor)"
                    [attr.title]="anchor.label"
                  >
                    <span>{{ formatCompactThemeLabel(anchor.label) }}</span>
                    <strong>{{ getMoodAnchorLabel(anchor.average_mood) }}</strong>
                    <small>{{ anchor.average_mood | number:'1.1-1' }}/5 · {{ anchor.count }} entries</small>
                    <span
                      class="dashboard-anchor-meter"
                      aria-hidden="true"
                      [attr.title]="getMoodAnchorTitle(anchor.average_mood)"
                      [style.--anchor-score]="getMoodAnchorWidth(anchor.average_mood) + '%'"
                    ></span>
                  </button>
                </div>
                <ng-template #noMoodAnchors>
                  <p class="dashboard-muted">Add mood labels and tags to build anchors.</p>
                </ng-template>
              </section>

              <section class="dashboard-focus-panel" aria-labelledby="dashboard-important-cues-heading">
                <div class="dashboard-focus-panel-heading">
                  <span class="dashboard-focus-icon important">
                    <mat-icon aria-hidden="true">event_upcoming</mat-icon>
                  </span>
                  <div>
                    <h3 id="dashboard-important-cues-heading">Dates ahead</h3>
                    <span>Important days coming up</span>
                  </div>
                </div>
                <div class="dashboard-focus-list" *ngIf="data.focus_sections.important_day_cues.length; else noImportantCues">
                  <a
                    *ngFor="let cue of data.focus_sections.important_day_cues"
                    routerLink="/important-days"
                    class="dashboard-focus-link"
                  >
                    <strong>{{ cue.label }}</strong>
                    <small>{{ formatDate(cue.date) }} · {{ getDaysUntilLabel(cue) }}</small>
                    <span>{{ cue.note || cue.category }}</span>
                  </a>
                </div>
                <ng-template #noImportantCues>
                  <p class="dashboard-muted">No upcoming important days recorded.</p>
                </ng-template>
              </section>
            </div>
          </article>

          <article
            class="dashboard-card dashboard-recent-activity"
            aria-labelledby="dashboard-activity-heading"
            data-testid="dashboard-activity-card"
          >
            <div class="dashboard-card-heading">
              <div>
                <p class="dashboard-card-kicker">Latest</p>
                <h2 id="dashboard-activity-heading">Recent activity</h2>
              </div>
              <a class="dashboard-card-link" routerLink="/entries">All entries</a>
            </div>
            <div class="dashboard-empty-state" *ngIf="data.recent_activity.length === 0">
              <mat-icon aria-hidden="true">auto_stories</mat-icon>
              <p>Start with a diary entry, dream, important day, or thought record.</p>
            </div>
            <div class="dashboard-activity-sections" *ngIf="data.recent_activity.length">
              <section
                *ngFor="let activityType of activityTypes"
                class="dashboard-activity-section"
                [attr.aria-label]="getActivityTypeLabel(activityType)"
              >
                <div class="dashboard-activity-section-heading">
                  <span class="dashboard-activity-icon" [ngClass]="activityType">
                    <mat-icon aria-hidden="true">{{ getActivityIcon(activityType) }}</mat-icon>
                  </span>
                  <h3>{{ getActivityTypeLabel(activityType) }}</h3>
                </div>
                <div class="dashboard-activity-list">
                  <a
                    *ngFor="let item of getGroupedActivity(data, activityType)"
                    class="dashboard-activity-item"
                    [routerLink]="getActivityRouterLink(item.route)"
                    [queryParams]="getActivityQueryParams(item.route)"
                  >
                    <span class="dashboard-activity-copy">
                      <strong>{{ item.title }}</strong>
                      <small>{{ formatDate(item.date) }}</small>
                      <span>{{ item.summary || getActivityFallback(item.type) }}</span>
                    </span>
                  </a>
                  <p class="dashboard-muted" *ngIf="getGroupedActivity(data, activityType).length === 0">
                    No recent {{ getActivityTypeLabel(activityType).toLowerCase() }}.
                  </p>
                </div>
                <a
                  class="dashboard-see-more-link"
                  [routerLink]="getActivityMoreLink(activityType)"
                  [queryParams]="getActivityMoreQueryParams(activityType)"
                >
                  See more {{ getActivityTypeLabel(activityType).toLowerCase() }}
                </a>
              </section>
            </div>
          </article>
        </div>

        <div class="dashboard-quick-log" data-testid="dashboard-quick-log">
          <button
            type="button"
            class="dashboard-quick-log-trigger"
            [attr.aria-expanded]="isQuickLogOpen"
            aria-controls="dashboard-quick-log-menu"
            aria-label="Open quick log actions"
            (click)="toggleQuickLog($event)"
          >
            <mat-icon aria-hidden="true">add</mat-icon>
          </button>
          <div
            id="dashboard-quick-log-menu"
            class="dashboard-quick-log-menu"
            *ngIf="isQuickLogOpen"
            role="menu"
            aria-label="Quick log"
          >
            <button
              *ngFor="let action of data.quick_actions"
              type="button"
              role="menuitem"
              class="dashboard-quick-action"
            (click)="openQuickAction(action)"
            >
              <mat-icon aria-hidden="true">{{ action.icon }}</mat-icon>
              <span>{{ action.label }}</span>
            </button>
          </div>
        </div>
        <button
          type="button"
          class="dashboard-back-to-top"
          (click)="scrollToTop()"
          data-testid="dashboard-back-to-top"
        >
          <mat-icon aria-hidden="true">arrow_upward</mat-icon>
          <span>Back to top</span>
        </button>
      </ng-container>
    </section>
  `,
  styles: [`
    :host {
      --dashboard-glow: rgba(29, 78, 216, 0.28);
      --dashboard-ring-track: color-mix(in srgb, var(--colour-border) 72%, transparent);
      --dashboard-daily: #1d4ed8;
      --dashboard-dream: #7c3aed;
      --dashboard-cbt: #059669;
      display: block;
    }

    :host-context(html[data-theme="dark"]) {
      --dashboard-glow: rgba(155, 184, 255, 0.22);
      --dashboard-ring-track: rgba(148, 163, 184, 0.24);
      --dashboard-daily: #9bb8ff;
      --dashboard-dream: #c4b5fd;
      --dashboard-cbt: #86efac;
    }

    .dashboard-shell {
      position: relative;
      isolation: isolate;
      display: flex;
      flex-direction: column;
      gap: var(--spacing-md);
      min-height: calc(100vh - 160px);
    }

    .dashboard-shell.is-loading .dashboard-grid,
    .dashboard-shell.is-loading .dashboard-hero-panel {
      filter: saturate(0.92);
      opacity: 0.72;
      transition:
        opacity var(--motion-standard),
        filter var(--motion-standard);
    }

    .dashboard-shell::before {
      content: "";
      position: fixed;
      inset: 80px 0 auto;
      height: 540px;
      z-index: -1;
      background:
        radial-gradient(circle at 18% 16%, color-mix(in srgb, var(--colour-primary) 24%, transparent), transparent 34%),
        radial-gradient(circle at 82% 8%, color-mix(in srgb, var(--colour-violet-border) 24%, transparent), transparent 32%),
        radial-gradient(circle at 54% 44%, color-mix(in srgb, var(--colour-accent) 18%, transparent), transparent 46%),
        linear-gradient(180deg, transparent 0%, color-mix(in srgb, var(--colour-background) 92%, transparent) 86%, var(--colour-background) 100%);
      filter: blur(12px);
      pointer-events: none;
    }

    .dashboard-hero-panel,
    .dashboard-card,
    .dashboard-status-card {
      border: 1px solid var(--colour-border);
      border-radius: 28px;
      background: color-mix(in srgb, var(--colour-surface-elevated) 92%, transparent);
      box-shadow: 0 18px 42px var(--colour-shadow-soft);
      backdrop-filter: blur(18px);
    }

    .dashboard-loading-overlay {
      position: absolute;
      inset: 0;
      z-index: 20;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding-top: clamp(160px, 22vh, 260px);
      background: color-mix(in srgb, var(--colour-background) 18%, transparent);
      pointer-events: none;
    }

    .dashboard-loading-panel {
      display: inline-flex;
      align-items: center;
      gap: 0.8rem;
      min-height: 58px;
      padding: 0 1.15rem;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, var(--colour-surface-elevated) 94%, transparent);
      color: var(--colour-text-primary);
      box-shadow: 0 18px 42px var(--colour-shadow-strong);
      backdrop-filter: blur(18px);
      font-weight: 900;
    }

    .dashboard-hero-panel {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-md);
      padding: clamp(24px, 4vw, 44px);
      overflow: hidden;
    }

    .dashboard-eyebrow,
    .dashboard-card-kicker {
      margin: 0 0 0.35rem;
      color: var(--colour-primary);
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .dashboard-hero-copy h1 {
      margin: 0;
      color: var(--colour-text-primary);
      font-size: clamp(2.25rem, 6vw, 4.8rem);
      line-height: 0.95;
      letter-spacing: -0.06em;
    }

    .dashboard-hero-copy p:last-child {
      max-width: 56ch;
      margin: var(--spacing-sm) 0 0;
      color: var(--colour-text-secondary);
      font-size: clamp(1rem, 2vw, 1.2rem);
      font-weight: 700;
    }

    .dashboard-hero-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: var(--spacing-xs);
      flex-wrap: wrap;
    }

    .dashboard-primary-action,
    .dashboard-secondary-action,
    .dashboard-card-link,
    .dashboard-range-chip,
    .dashboard-theme-pill,
    .dashboard-pattern-pill {
      border-radius: var(--radius-pill);
    }

    .dashboard-primary-action {
      min-height: 48px;
      box-shadow: 0 10px 24px var(--dashboard-glow);
    }

    .dashboard-secondary-action {
      min-height: 48px;
      border-color: var(--colour-border);
      color: var(--colour-text-primary);
    }

    .dashboard-grid {
      display: grid;
      grid-template-columns: minmax(280px, 0.9fr) minmax(360px, 1.4fr);
      gap: var(--spacing-md);
      align-items: stretch;
    }

    .dashboard-card,
    .dashboard-status-card {
      padding: var(--spacing-md);
    }

    .dashboard-card {
      transition:
        transform var(--motion-emphasized),
        box-shadow var(--motion-emphasized),
        border-color var(--motion-standard);
    }

    .dashboard-card:hover {
      transform: translateY(-3px) rotate(-0.15deg);
      border-color: color-mix(in srgb, var(--colour-primary) 44%, var(--colour-border));
      box-shadow: 0 22px 54px var(--colour-shadow-medium);
    }

    .dashboard-card-heading {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--spacing-sm);
      margin-bottom: var(--spacing-md);
    }

    .dashboard-card-heading h2 {
      margin: 0;
      color: var(--colour-text-primary);
      font-size: clamp(1.35rem, 2vw, 1.8rem);
      letter-spacing: -0.03em;
    }

    .dashboard-card-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      min-height: 38px;
      padding: 0 0.85rem;
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      font-weight: 800;
      text-decoration: none;
    }

    .dashboard-reward-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 36px;
      padding: 0 0.85rem;
      border: 1px solid var(--colour-amber-border);
      border-radius: var(--radius-pill);
      background: var(--colour-amber-bg);
      color: var(--colour-amber-text);
      font-weight: 900;
      white-space: nowrap;
    }

    .dashboard-reward-pill.is-active {
      animation: dashboardPulse 1.8s cubic-bezier(0.2, 0, 0, 1) infinite;
    }

    .dashboard-ring-layout {
      display: grid;
      grid-template-columns: 156px 1fr;
      gap: var(--spacing-md);
      align-items: center;
    }

    .dashboard-progress-ring {
      position: relative;
      width: 156px;
      height: 156px;
    }

    .dashboard-progress-ring svg {
      width: 100%;
      height: 100%;
      transform: rotate(-90deg);
    }

    .ring-track,
    .ring-progress {
      fill: none;
      stroke-width: 10;
    }

    .ring-track {
      stroke: var(--dashboard-ring-track);
    }

    .ring-progress {
      stroke: var(--colour-primary);
      stroke-linecap: round;
      transition: stroke-dashoffset 700ms cubic-bezier(0.2, 0, 0, 1);
      filter: drop-shadow(0 0 8px var(--dashboard-glow));
    }

    .dashboard-ring-value {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--colour-text-primary);
      font-size: 2rem;
      font-weight: 900;
      letter-spacing: -0.04em;
    }

    .dashboard-streak-metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--spacing-xs);
      margin: 0;
    }

    .dashboard-streak-metrics div,
    .dashboard-cbt-meter {
      padding: 14px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .dashboard-streak-metrics dt,
    .dashboard-cbt-meter span {
      color: var(--colour-text-secondary);
      font-size: 0.84rem;
      font-weight: 800;
    }

    .dashboard-streak-metrics dd,
    .dashboard-cbt-meter strong {
      margin: 0.2rem 0 0;
      color: var(--colour-text-primary);
      font-size: 1.55rem;
      font-weight: 900;
      letter-spacing: -0.04em;
    }

    .dashboard-support-text {
      margin: var(--spacing-sm) 0 0;
      color: var(--colour-text-secondary);
      font-weight: 700;
    }

    .dashboard-analytics-chart,
    .dashboard-recent-activity,
    .dashboard-dream-insights {
      grid-column: span 1;
    }

    .dashboard-analytics-chart {
      transition:
        grid-column var(--motion-emphasized),
        transform var(--motion-emphasized),
        box-shadow var(--motion-emphasized),
        border-color var(--motion-standard);
    }

    .dashboard-analytics-chart.is-expanded {
      order: -1;
      grid-column: 1 / -1;
    }

    .dashboard-range-group {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .dashboard-range-chip {
      min-height: 36px;
      padding: 0 0.8rem;
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-muted);
      color: var(--colour-text-secondary);
      font: inherit;
      font-weight: 900;
      cursor: pointer;
    }

    .dashboard-range-chip.is-selected {
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      border-color: transparent;
      box-shadow: 0 8px 18px var(--colour-primary-shadow);
    }

    .dashboard-season-select {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 40px;
      padding: 0 0.45rem 0 0.8rem;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      color: var(--colour-text-secondary);
      font-weight: 900;
    }

    .dashboard-season-select select {
      min-height: 32px;
      border: 0;
      border-radius: var(--radius-pill);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      font: inherit;
      font-weight: 850;
      padding: 0 0.8rem;
    }

    .dashboard-season-select select:focus-visible {
      outline: var(--focus-outline);
      outline-offset: 2px;
    }

    .dashboard-chart-expand {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      cursor: pointer;
      transition:
        background var(--motion-standard),
        border-color var(--motion-standard),
        transform var(--motion-emphasized);
    }

    .dashboard-chart-expand:hover,
    .dashboard-chart-expand:focus-visible {
      border-color: var(--colour-primary);
      background: var(--colour-control-hover);
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    .dashboard-chart-expand mat-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      font-size: 20px;
      line-height: 1;
    }

    .dashboard-chart {
      position: relative;
      min-height: 220px;
      border: 1px solid var(--colour-border);
      border-radius: 22px;
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--colour-surface-muted) 72%, transparent), transparent),
        var(--colour-surface);
      overflow: visible;
      transition:
        min-height var(--motion-emphasized),
        background var(--motion-standard),
        border-color var(--motion-standard);
    }

    .dashboard-chart svg {
      display: block;
      width: 100%;
      height: 220px;
      transition:
        height var(--motion-emphasized),
        opacity var(--motion-standard),
        filter var(--motion-standard);
    }

    .dashboard-analytics-chart.is-expanded .dashboard-chart {
      min-height: clamp(280px, 42vw, 420px);
    }

    .dashboard-analytics-chart.is-expanded .dashboard-chart svg {
      height: clamp(280px, 42vw, 420px);
    }

    .dashboard-chart.is-loading svg {
      opacity: 0.44;
      filter: saturate(0.72);
    }

    .dashboard-chart-loading {
      position: absolute;
      inset: 0;
      z-index: 4;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.8rem;
      border-radius: inherit;
      background: color-mix(in srgb, var(--colour-surface) 44%, transparent);
      color: var(--colour-text-primary);
      font-weight: 900;
      backdrop-filter: blur(6px);
      pointer-events: none;
    }

    .dashboard-chart-empty {
      position: absolute;
      inset: 58px 24px 42px;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.7rem;
      border: 1px dashed var(--colour-border);
      border-radius: 18px;
      background: color-mix(in srgb, var(--colour-surface-muted) 68%, transparent);
      color: var(--colour-text-secondary);
      font-weight: 900;
      text-align: center;
      pointer-events: none;
    }

    .dashboard-chart-empty mat-icon {
      color: var(--colour-primary);
    }

    .chart-grid line {
      stroke: color-mix(in srgb, var(--colour-border) 64%, transparent);
      stroke-width: 1;
      vector-effect: non-scaling-stroke;
    }

    .chart-axis-labels text {
      fill: var(--colour-text-secondary);
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.02em;
    }

    .chart-value-ticks text {
      fill: color-mix(in srgb, var(--colour-text-secondary) 82%, transparent);
      font-size: 0.66rem;
      font-weight: 850;
    }

    .chart-value-ticks text:nth-child(n + 4) {
      text-anchor: end;
    }

    .chart-time-ticks line {
      stroke: color-mix(in srgb, var(--colour-border) 72%, transparent);
      stroke-width: 1;
      vector-effect: non-scaling-stroke;
    }

    .chart-time-ticks text {
      fill: var(--colour-text-secondary);
      font-size: 0.68rem;
      font-weight: 850;
      letter-spacing: 0.01em;
      text-anchor: middle;
    }

    .chart-bar {
      opacity: 0.82;
      transform-origin: bottom;
      cursor: pointer;
    }

    .dashboard-chart.is-animating .chart-bar {
      animation: dashboardBarRise 420ms cubic-bezier(0.2, 0, 0, 1) both;
    }

    .chart-bar:hover,
    .chart-bar:focus-visible,
    .chart-mood-point:hover,
    .chart-mood-point:focus-visible {
      opacity: 1;
      filter: drop-shadow(0 0 10px var(--dashboard-glow));
      outline: none;
    }

    .chart-bar.daily {
      fill: var(--dashboard-daily);
    }

    .chart-bar.dream {
      fill: var(--dashboard-dream);
      opacity: 0.72;
    }

    .chart-mood-line {
      fill: none;
      stroke: var(--dashboard-cbt);
      stroke-width: 4;
      stroke-linecap: round;
      stroke-linejoin: round;
      filter: drop-shadow(0 4px 10px color-mix(in srgb, var(--dashboard-cbt) 30%, transparent));
    }

    .chart-mood-point {
      fill: var(--dashboard-cbt);
      stroke: var(--colour-surface-elevated);
      stroke-width: 2;
      cursor: pointer;
      filter: drop-shadow(0 4px 10px color-mix(in srgb, var(--dashboard-cbt) 30%, transparent));
    }

    .dashboard-chart-meta {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin: 0.85rem 0 0;
      color: var(--colour-text-secondary);
      font-size: 0.88rem;
      font-weight: 700;
    }

    .dashboard-chart-pill,
    .dashboard-chart-clear {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      padding: 0 0.9rem;
      border-radius: var(--radius-pill);
      font: inherit;
      font-weight: 900;
    }

    .dashboard-chart-pill {
      border: 1px solid color-mix(in srgb, var(--colour-primary) 28%, var(--colour-border));
      background: var(--colour-control-hover);
      color: var(--colour-text-primary);
    }

    .dashboard-chart-clear {
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      cursor: pointer;
    }

    .dashboard-range-chip:disabled,
    .dashboard-season-select select:disabled,
    .dashboard-chart-clear:disabled {
      cursor: progress;
      opacity: 0.68;
    }

    .dashboard-chart-detail {
      position: absolute;
      z-index: 3;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-sm);
      width: min(330px, calc(100% - 28px));
      padding: 0.8rem 0.9rem;
      border: 1px solid var(--colour-border);
      border-radius: 18px;
      background:
        linear-gradient(135deg, color-mix(in srgb, var(--colour-primary) 12%, transparent), transparent 62%),
        var(--colour-surface-muted);
      color: var(--colour-text-primary);
      box-shadow: 0 18px 36px var(--colour-shadow-strong);
      transform: translate(-50%, calc(-100% - 12px));
    }

    .dashboard-chart-detail::after {
      content: "";
      position: absolute;
      left: 50%;
      bottom: -7px;
      width: 14px;
      height: 14px;
      border-right: 1px solid var(--colour-border);
      border-bottom: 1px solid var(--colour-border);
      background: var(--colour-surface-muted);
      transform: translateX(-50%) rotate(45deg);
    }

    .dashboard-chart-detail div {
      display: grid;
      gap: 4px;
    }

    .dashboard-chart-detail span {
      color: var(--colour-text-secondary);
    }

    .dashboard-chart-detail button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      cursor: pointer;
    }

    .dashboard-chart-legend {
      display: flex;
      flex-wrap: wrap;
      gap: var(--spacing-xs);
      margin: var(--spacing-sm) 0 0;
      padding: 0;
      list-style: none;
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    .dashboard-chart-legend li,
    .dashboard-pattern-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    .legend-swatch,
    .legend-line {
      width: 18px;
      height: 10px;
      border-radius: var(--radius-pill);
    }

    .legend-swatch.daily {
      background: var(--dashboard-daily);
    }

    .legend-swatch.dream {
      background: var(--dashboard-dream);
    }

    .legend-line {
      height: 4px;
      background: var(--dashboard-cbt);
    }

    .dashboard-theme-cloud,
    .dashboard-cbt-insights {
      min-height: 300px;
    }

    .dashboard-theme-list,
    .dashboard-pattern-list {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .dashboard-theme-pill {
      --theme-scale: calc(0.9rem + (var(--theme-weight, 1) * 0.08rem));
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 42px;
      padding: 0 1rem;
      border: 1px solid color-mix(in srgb, var(--colour-primary) 26%, var(--colour-border));
      background: color-mix(in srgb, var(--colour-chip-bg) 76%, transparent);
      color: var(--colour-chip-text);
      font: inherit;
      font-size: var(--theme-scale);
      font-weight: 900;
      cursor: pointer;
      transition:
        box-shadow var(--motion-emphasized),
        background var(--motion-standard),
        border-color var(--motion-standard);
    }

    .dashboard-theme-pill strong {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 32px;
      min-height: 24px;
      padding: 0 8px;
      border-radius: var(--radius-pill);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      font-size: 0.8em;
    }

    .dashboard-theme-pill:hover,
    .dashboard-theme-pill:focus-visible,
    .dashboard-theme-pill.is-selected {
      border-color: var(--colour-primary);
      background: var(--colour-control-hover);
      box-shadow: 0 12px 24px var(--colour-shadow-soft);
    }

    .dashboard-theme-focus {
      margin: var(--spacing-sm) 0 0;
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    .dashboard-theme-focus strong {
      color: var(--colour-text-primary);
    }

    .dashboard-cbt-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--spacing-xs);
      margin-bottom: var(--spacing-sm);
    }

    .dashboard-cbt-meter.is-change {
      border-color: var(--colour-emerald-border);
      background: var(--colour-emerald-bg);
      color: var(--colour-emerald-text);
    }

    .dashboard-cbt-meter {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      min-height: 96px;
      text-align: center;
    }

    .dashboard-cbt-meter.is-change span,
    .dashboard-cbt-meter.is-change strong {
      color: var(--colour-emerald-text);
    }

    .dashboard-pattern-pill {
      min-height: 34px;
      padding: 0 0.8rem;
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      font-weight: 800;
    }

    .dashboard-reflection-list,
    .dashboard-activity-list {
      display: grid;
      gap: var(--spacing-xs);
      margin-top: var(--spacing-sm);
    }

    .dashboard-dream-insights,
    .dashboard-focus-sections,
    .dashboard-recent-activity {
      grid-column: 1 / -1;
    }

    .dashboard-dream-layout {
      display: grid;
      grid-template-columns: minmax(280px, 0.9fr) minmax(320px, 1.1fr);
      gap: var(--spacing-md);
      align-items: stretch;
    }

    .dashboard-recent-dreams {
      display: grid;
      gap: var(--spacing-xs);
    }

    .dashboard-latest-dream-card {
      display: grid;
      grid-template-columns: 112px 1fr;
      gap: var(--spacing-sm);
      min-height: 138px;
      padding: 14px;
      border: 1px solid var(--colour-border);
      border-radius: 24px;
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      text-decoration: none;
      transition:
        transform var(--motion-emphasized),
        border-color var(--motion-standard),
        background var(--motion-standard);
    }

    .dashboard-latest-dream-card:hover,
    .dashboard-latest-dream-card:focus-visible {
      transform: translateY(-3px);
      border-color: var(--colour-primary);
      background: var(--colour-control-hover);
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    .dashboard-latest-dream-image {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 110px;
      border-radius: 20px;
      background:
        radial-gradient(circle at 35% 25%, color-mix(in srgb, var(--dashboard-dream) 28%, transparent), transparent 40%),
        var(--colour-surface);
      background-position: center;
      background-size: cover;
      color: var(--dashboard-dream);
      overflow: hidden;
    }

    .dashboard-latest-dream-image mat-icon {
      width: 48px;
      height: 48px;
      font-size: 48px;
    }

    .dashboard-latest-dream-copy {
      display: flex;
      flex-direction: column;
      gap: 0.45rem;
      justify-content: center;
      min-width: 0;
    }

    .dashboard-latest-dream-copy small,
    .dashboard-latest-dream-copy span {
      color: var(--colour-text-secondary);
      font-weight: 700;
    }

    .dashboard-latest-dream-copy strong {
      color: var(--colour-text-primary);
      font-size: clamp(1.25rem, 2vw, 1.75rem);
      font-weight: 900;
      letter-spacing: -0.03em;
    }

    .dashboard-latest-dream-copy strong,
    .dashboard-latest-dream-copy > span:not(.dashboard-dream-meta) {
      display: -webkit-box;
      overflow: hidden;
      -webkit-box-orient: vertical;
    }

    .dashboard-latest-dream-copy strong {
      -webkit-line-clamp: 1;
    }

    .dashboard-latest-dream-copy > span:not(.dashboard-dream-meta) {
      -webkit-line-clamp: 2;
    }

    .dashboard-dream-meta {
      display: inline-flex;
      color: var(--colour-primary);
      font-size: 0.82rem;
      font-weight: 900;
    }

    .dashboard-dream-groups {
      display: grid;
      gap: var(--spacing-sm);
      align-content: start;
    }

    .dashboard-dream-groups h3,
    .dashboard-activity-section h3 {
      margin: 0;
      color: var(--colour-text-primary);
      font-size: 1rem;
      font-weight: 900;
    }

    .dashboard-mini-pill-list {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }

    .dashboard-mini-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 0 0.85rem;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-chip-bg);
      color: var(--colour-chip-text);
      font-weight: 850;
    }

    .dashboard-mini-pill strong {
      min-width: 28px;
      padding: 2px 7px;
      border-radius: var(--radius-pill);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      text-align: center;
    }

    .dashboard-focus-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(220px, 1fr));
      gap: var(--spacing-sm);
    }

    .dashboard-focus-panel {
      display: grid;
      align-content: start;
      gap: var(--spacing-sm);
      min-width: 0;
      padding: 1rem;
      border: 1px solid var(--colour-border);
      border-radius: 24px;
      background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--colour-primary) 12%, transparent), transparent 42%),
        var(--colour-surface-muted);
    }

    .dashboard-focus-panel-heading {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .dashboard-focus-panel h3 {
      margin: 0;
      color: var(--colour-text-primary);
      font-size: 1rem;
      font-weight: 950;
    }

    .dashboard-focus-panel-heading span:not(.dashboard-focus-icon) {
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    .dashboard-focus-icon {
      display: grid;
      place-items: center;
      width: 48px;
      height: 48px;
      flex: 0 0 48px;
      border-radius: 18px;
      background: var(--colour-blue-bg);
      color: var(--colour-blue-text);
    }

    .dashboard-focus-icon.drift {
      background: var(--colour-violet-bg);
      color: var(--colour-violet-text);
    }

    .dashboard-focus-icon.mood {
      background: var(--colour-emerald-bg);
      color: var(--colour-emerald-text);
    }

    .dashboard-focus-icon.important {
      background: var(--colour-amber-bg);
      color: var(--colour-amber-text);
    }

    .dashboard-focus-list,
    .dashboard-drift-list,
    .dashboard-anchor-list {
      display: grid;
      gap: 10px;
    }

    .dashboard-focus-link,
    .dashboard-anchor-card {
      display: grid;
      gap: 4px;
      min-width: 0;
      padding: 0.8rem;
      border: 1px solid var(--colour-border);
      border-radius: 18px;
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      text-decoration: none;
    }

    .dashboard-focus-link strong,
    .dashboard-focus-link span,
    .dashboard-anchor-card span {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .dashboard-focus-link small,
    .dashboard-focus-link span,
    .dashboard-anchor-card small {
      color: var(--colour-text-secondary);
      font-weight: 750;
    }

    .dashboard-drift-list {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .dashboard-drift-pill,
    .dashboard-anchor-card {
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      font: inherit;
      cursor: pointer;
    }

    .dashboard-drift-pill {
      display: inline-flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      min-height: 42px;
      min-width: 0;
      padding: 0 0.8rem;
      border-radius: var(--radius-pill);
      font-weight: 900;
    }

    .dashboard-drift-pill span {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .dashboard-drift-pill strong,
    .dashboard-anchor-card strong {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 34px;
      min-height: 28px;
      padding: 0 8px;
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, var(--colour-primary) 16%, var(--colour-surface-muted));
      color: var(--colour-text-primary);
    }

    .dashboard-anchor-card {
      text-align: left;
      transition:
        border-color var(--motion-standard),
        background var(--motion-standard);
    }

    .dashboard-anchor-card strong {
      justify-self: start;
    }

    .dashboard-anchor-card.is-positive strong {
      background: var(--colour-emerald-bg);
      color: var(--colour-emerald-text);
    }

    .dashboard-anchor-card.is-steady strong {
      background: var(--colour-blue-bg);
      color: var(--colour-blue-text);
    }

    .dashboard-anchor-card.is-mixed strong {
      background: var(--colour-amber-bg);
      color: var(--colour-amber-text);
    }

    .dashboard-anchor-card.is-low strong {
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    .dashboard-anchor-meter {
      position: relative;
      display: block;
      width: 100%;
      height: 7px;
      overflow: hidden;
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, var(--colour-border) 72%, transparent);
    }

    .dashboard-anchor-meter::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: var(--anchor-score, 0%);
      border-radius: inherit;
      background: linear-gradient(90deg, var(--colour-danger-text), var(--colour-amber-text), var(--colour-emerald-text));
    }

    .dashboard-focus-link:hover,
    .dashboard-focus-link:focus-visible,
    .dashboard-drift-pill:hover,
    .dashboard-drift-pill:focus-visible,
    .dashboard-anchor-card:hover,
    .dashboard-anchor-card:focus-visible,
    .dashboard-chart-clear:hover,
    .dashboard-chart-clear:focus-visible,
    .dashboard-chart-detail button:hover,
    .dashboard-chart-detail button:focus-visible {
      border-color: var(--colour-primary);
      background: var(--colour-control-hover);
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    .dashboard-activity-sections {
      display: grid;
      grid-template-columns: repeat(4, minmax(210px, 1fr));
      gap: var(--spacing-sm);
      align-items: stretch;
    }

    .dashboard-activity-section {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-xs);
      min-width: 0;
      padding: 14px;
      border: 1px solid var(--colour-border);
      border-radius: 24px;
      background: var(--colour-surface-muted);
    }

    .dashboard-activity-section-heading {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .dashboard-reflection-card,
    .dashboard-activity-item {
      display: grid;
      gap: 4px;
      padding: 14px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      text-decoration: none;
      transition:
        transform var(--motion-emphasized),
        border-color var(--motion-standard),
        background var(--motion-standard);
    }

    .dashboard-reflection-card:hover,
    .dashboard-activity-item:hover {
      transform: translateX(3px);
      border-color: var(--colour-primary);
      background: var(--colour-control-hover);
    }

    .dashboard-reflection-card span,
    .dashboard-activity-copy span,
    .dashboard-activity-copy small {
      color: var(--colour-text-secondary);
      font-weight: 700;
    }

    .dashboard-activity-icon {
      display: grid;
      place-items: center;
      width: 44px;
      height: 44px;
      border-radius: 16px;
      background: var(--colour-blue-bg);
      color: var(--colour-blue-text);
    }

    .dashboard-activity-icon.dream {
      background: var(--colour-violet-bg);
      color: var(--colour-violet-text);
    }

    .dashboard-activity-icon.thought_record {
      background: var(--colour-emerald-bg);
      color: var(--colour-emerald-text);
    }

    .dashboard-activity-icon.important_day {
      background: var(--colour-amber-bg);
      color: var(--colour-amber-text);
    }

    .dashboard-activity-copy {
      display: grid;
      gap: 2px;
      min-width: 0;
    }

    .dashboard-activity-copy strong,
    .dashboard-activity-copy span {
      display: -webkit-box;
      overflow: hidden;
      -webkit-box-orient: vertical;
    }

    .dashboard-activity-copy strong {
      -webkit-line-clamp: 2;
    }

    .dashboard-activity-copy span {
      -webkit-line-clamp: 3;
    }

    .dashboard-muted {
      margin: 0;
      color: var(--colour-text-secondary);
      font-weight: 700;
    }

    .dashboard-see-more-link,
    .dashboard-back-to-top {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 0.9rem;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      font: inherit;
      font-weight: 900;
      text-decoration: none;
    }

    .dashboard-see-more-link {
      margin-top: auto;
    }

    .dashboard-back-to-top {
      align-self: center;
      gap: 8px;
      margin: var(--spacing-md) auto 0;
      cursor: pointer;
      box-shadow: 0 10px 24px var(--colour-shadow-soft);
    }

    .dashboard-empty-state,
    .dashboard-status-card {
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    .dashboard-status-card {
      min-height: 78px;
    }

    .dashboard-status-card.is-error {
      border-color: var(--colour-danger-text);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    .dashboard-empty-state mat-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--colour-primary);
      line-height: 1;
    }

    .dashboard-quick-log {
      position: fixed;
      right: clamp(18px, 4vw, 42px);
      bottom: clamp(18px, 4vw, 42px);
      z-index: 90;
    }

    .dashboard-quick-log-trigger {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 64px;
      height: 64px;
      border: 1px solid color-mix(in srgb, var(--colour-primary) 48%, transparent);
      border-radius: var(--radius-pill);
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      box-shadow: 0 18px 38px var(--colour-primary-shadow);
      cursor: pointer;
      transition: transform var(--motion-emphasized);
    }

    .dashboard-quick-log-trigger:hover,
    .dashboard-quick-log-trigger:focus-visible {
      transform: translateY(-3px) scale(1.04);
    }

    .dashboard-quick-log-menu {
      position: absolute;
      right: 0;
      bottom: 76px;
      display: grid;
      gap: 8px;
      min-width: 220px;
      padding: 10px;
      border: 1px solid var(--colour-border);
      border-radius: 22px;
      background: var(--colour-surface-elevated);
      box-shadow: 0 22px 54px var(--colour-shadow-medium);
    }

    .dashboard-quick-action {
      display: flex;
      align-items: center;
      gap: 10px;
      min-height: 48px;
      padding: 0 14px;
      border: 1px solid transparent;
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      font: inherit;
      font-weight: 900;
      cursor: pointer;
      text-align: left;
    }

    .dashboard-focus-icon mat-icon,
    .dashboard-activity-icon mat-icon,
    .dashboard-quick-log-trigger mat-icon,
    .dashboard-quick-action mat-icon,
    .dashboard-back-to-top mat-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.25em;
      height: 1.25em;
      margin: 0;
      line-height: 1;
    }

    .dashboard-quick-action:hover,
    .dashboard-quick-action:focus-visible,
    .dashboard-card-link:hover,
    .dashboard-card-link:focus-visible,
    .dashboard-see-more-link:hover,
    .dashboard-see-more-link:focus-visible,
    .dashboard-back-to-top:hover,
    .dashboard-back-to-top:focus-visible,
      .dashboard-range-chip:focus-visible,
      .dashboard-chart-expand:focus-visible,
      .dashboard-primary-action:focus-visible,
      .dashboard-secondary-action:focus-visible,
      .dashboard-activity-item:focus-visible,
    .dashboard-reflection-card:focus-visible {
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    @keyframes dashboardPulse {
      0%, 100% {
        box-shadow: 0 0 0 0 color-mix(in srgb, var(--colour-amber-border) 28%, transparent);
      }
      50% {
        box-shadow: 0 0 0 8px transparent;
      }
    }

    @keyframes dashboardBarRise {
      from {
        transform: scaleY(0.08);
        opacity: 0.35;
      }
      to {
        transform: scaleY(1);
      }
    }

    @media (max-width: 980px) {
      .dashboard-hero-panel,
      .dashboard-card-heading {
        flex-direction: column;
        align-items: stretch;
      }

      .dashboard-hero-actions,
      .dashboard-range-group {
        justify-content: flex-start;
      }

      .dashboard-grid {
        grid-template-columns: 1fr;
      }

      .dashboard-dream-layout,
      .dashboard-focus-grid,
      .dashboard-activity-sections {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 640px) {
      .dashboard-ring-layout,
      .dashboard-cbt-grid {
        grid-template-columns: 1fr;
      }

      .dashboard-progress-ring {
        margin: 0 auto;
      }

      .dashboard-streak-metrics {
        grid-template-columns: 1fr;
      }

      .dashboard-quick-log-trigger {
        width: 56px;
        height: 56px;
      }

      .dashboard-latest-dream-card {
        grid-template-columns: 1fr;
      }

      .dashboard-drift-list {
        grid-template-columns: 1fr;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .dashboard-card,
      .dashboard-theme-pill,
      .dashboard-reflection-card,
      .dashboard-activity-item,
      .dashboard-quick-log-trigger,
      .dashboard-analytics-chart,
      .dashboard-chart,
      .ring-progress,
      .chart-bar,
      .dashboard-reward-pill.is-active {
        animation: none;
        transition: none;
      }

      .dashboard-card:hover,
      .dashboard-theme-pill:hover,
      .dashboard-reflection-card:hover,
      .dashboard-activity-item:hover,
      .dashboard-quick-log-trigger:hover {
        transform: none;
      }
    }
  `],
})
export class DashboardComponent implements OnInit {
  private readonly dashboardService = inject(DashboardService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly rangeOptions: Array<{ value: DashboardRange; label: string }> = [
    { value: "1w", label: "1W" },
    { value: "1m", label: "1M" },
    { value: "3m", label: "3M" },
    { value: "all", label: "All" },
  ];
  readonly activityTypes: DashboardActivityType[] = [
    "daily",
    "dream",
    "thought_record",
    "important_day",
  ];
  readonly ringCircumference = 251.327;
  private readonly chartPreferenceStorageKey = "openmynd_dashboard_chart_preference";

  selectedRange: DashboardRange = "1m";
  overview: DashboardOverview | null = null;
  isLoading = false;
  isChartLoading = false;
  errorMessage = "";
  selectedTheme: DashboardTheme | null = null;
  activeThemeFilter: DashboardTheme | null = null;
  selectedSeason = "";
  chartSeries: DashboardSeriesPoint[] = [];
  chartMaxWords = 1;
  chartMidWords = 0;
  chartMoodPolyline = "";
  chartMoodPoints: Array<{ x: string; y: string; title: string; source: DashboardSeriesPoint }> = [];
  chartTimeTicks: DashboardChartTick[] = [];
  selectedChartPoint: DashboardChartSelection | null = null;
  selectedChartPosition: DashboardChartPosition = { left: 50, top: 50 };
  isChartAnimating = false;
  isChartExpanded = false;
  private chartAnimationTimer: ReturnType<typeof setTimeout> | null = null;
  isQuickLogOpen = false;

  get displayName(): string {
    const user = this.authService.getCurrentUser();
    return user?.display_name || user?.first_name || user?.username || "there";
  }

  get greeting(): string {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  }

  get availableSeasonOptions(): DashboardSeasonOption[] {
    return this.overview?.available_seasons || [];
  }

  ngOnInit(): void {
    this.restoreChartPreference();
    this.loadOverview();
  }

  loadOverview(scope: "page" | "chart" = "page"): void {
    this.isLoading = scope === "page";
    this.isChartLoading = scope === "chart";
    this.errorMessage = "";
    this.dashboardService
      .getOverview(this.selectedSeason ? "all" : this.selectedRange, this.activeThemeFilter)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (overview) => {
          this.overview = this.normaliseOverview(overview);
          if (this.reconcileSelectedSeason()) {
            this.isLoading = false;
            this.isChartLoading = false;
            this.loadOverview(scope);
            return;
          }
          this.refreshChartData();
          this.isLoading = false;
          this.isChartLoading = false;
        },
        error: (error: unknown) => {
          console.error("Dashboard overview failed:", error);
          this.errorMessage = this.getDashboardErrorMessage(error);
          this.isLoading = false;
          this.isChartLoading = false;
        },
      });
  }

  private getDashboardErrorMessage(error: unknown): string {
    if (error instanceof HttpErrorResponse) {
      if (error.status === 0) {
        return "Dashboard insights could not be loaded because the API is unreachable.";
      }
      if (error.status === 401 || error.status === 422) {
        return "Your session expired. Please sign in again.";
      }
      if (error.status >= 500) {
        return "Dashboard insights could not be loaded because the server returned an error.";
      }
    }
    return "Dashboard insights could not be loaded.";
  }

  private normaliseOverview(
    overview: Partial<DashboardOverview> | null | undefined,
  ): DashboardOverview {
    const cbt = overview?.cbt;
    const dreamInsights = overview?.dream_insights;
    const focusSections = overview?.focus_sections;
    const memoryEcho = focusSections?.memory_echo;
    const groupedActivity =
      (overview?.recent_activity_by_type || {}) as Partial<
        DashboardOverview["recent_activity_by_type"]
      >;
    const includedEntryTypes = Array.isArray(overview?.streak?.included_entry_types)
      ? overview.streak.included_entry_types
      : ["daily", "dream"];

    return {
      range: this.isDashboardRange(overview?.range) ? overview.range : this.selectedRange,
      theme_filter: overview?.theme_filter ?? null,
      generated_at: overview?.generated_at || new Date().toISOString(),
      available_seasons: Array.isArray(overview?.available_seasons)
        ? overview.available_seasons
        : [],
      streak: {
        current_days: 0,
        best_days: 0,
        weekly_goal: 4,
        week_count: 0,
        month_count: 0,
        weekly_progress: 0,
        ...(overview?.streak || {}),
        included_entry_types: includedEntryTypes,
      },
      series: Array.isArray(overview?.series) ? overview.series : [],
      themes: Array.isArray(overview?.themes) ? overview.themes : [],
      cbt: {
        total_records: Number(cbt?.total_records || 0),
        common_patterns: Array.isArray(cbt?.common_patterns) ? cbt.common_patterns : [],
        average_before: cbt?.average_before ?? null,
        average_after: cbt?.average_after ?? null,
        average_change: cbt?.average_change ?? null,
        recent_reflections: Array.isArray(cbt?.recent_reflections)
          ? cbt.recent_reflections
          : [],
      },
      recent_activity: Array.isArray(overview?.recent_activity)
        ? overview.recent_activity
        : [],
      recent_activity_by_type: {
        daily: Array.isArray(groupedActivity.daily) ? groupedActivity.daily : [],
        dream: Array.isArray(groupedActivity.dream) ? groupedActivity.dream : [],
        thought_record: Array.isArray(groupedActivity.thought_record)
          ? groupedActivity.thought_record
          : [],
        important_day: Array.isArray(groupedActivity.important_day)
          ? groupedActivity.important_day
          : [],
      },
      dream_insights: {
        total_dreams: Number(dreamInsights?.total_dreams || 0),
        top_symbols: Array.isArray(dreamInsights?.top_symbols)
          ? dreamInsights.top_symbols
          : [],
        top_people: Array.isArray(dreamInsights?.top_people)
          ? dreamInsights.top_people
          : [],
        top_places: Array.isArray(dreamInsights?.top_places)
          ? dreamInsights.top_places
          : [],
        recent: Array.isArray(dreamInsights?.recent) ? dreamInsights.recent : [],
        recent_repeating_patterns: Array.isArray(
          dreamInsights?.recent_repeating_patterns,
        )
          ? dreamInsights.recent_repeating_patterns
          : [],
        latest: dreamInsights?.latest ?? null,
      },
      focus_sections: {
        memory_echo: {
          label: memoryEcho?.label || "This time before",
          count: Number(memoryEcho?.count || 0),
          items: Array.isArray(memoryEcho?.items) ? memoryEcho.items : [],
        },
        theme_drift: Array.isArray(focusSections?.theme_drift)
          ? focusSections.theme_drift
          : [],
        mood_anchors: Array.isArray(focusSections?.mood_anchors)
          ? focusSections.mood_anchors
          : [],
        important_day_cues: Array.isArray(focusSections?.important_day_cues)
          ? focusSections.important_day_cues
          : [],
      },
      quick_actions: Array.isArray(overview?.quick_actions)
        ? overview.quick_actions
        : this.defaultQuickActions(),
    };
  }

  private defaultQuickActions(): DashboardQuickAction[] {
    const today = new Date().toISOString().slice(0, 10);
    return [
      {
        type: "daily",
        label: "Diary",
        icon: "book",
        route: `/entries/create?date=${today}&type=daily`,
      },
      {
        type: "dream",
        label: "Dream",
        icon: "nights_stay",
        route: `/entries/create?date=${today}&type=dream`,
      },
      {
        type: "thought_record",
        label: "Thought record",
        icon: "psychology_alt",
        route: `/cbt?create=true&date=${today}`,
      },
      {
        type: "important_day",
        label: "Important day",
        icon: "event",
        route: `/entries/create?date=${today}&type=important-day`,
      },
    ];
  }

  selectRange(range: DashboardRange): void {
    if (!this.selectedSeason && this.selectedRange === range) return;
    this.selectedSeason = "";
    this.selectedRange = range;
    this.persistChartPreference();
    this.selectedChartPoint = null;
    this.pulseChartAnimation();
    this.loadOverview("chart");
  }

  selectSeason(event: Event): void {
    const value = (event.target as HTMLSelectElement | null)?.value || "";
    if (value && !this.hasAvailableSeason(value)) return;
    if (this.selectedSeason === value) return;
    this.selectedSeason = value;
    if (value) {
      this.selectedRange = "all";
    }
    this.persistChartPreference();
    this.selectedChartPoint = null;
    this.pulseChartAnimation();
    this.loadOverview("chart");
  }

  private restoreChartPreference(): void {
    const savedPreference = this.readChartPreference();
    if (!savedPreference) return;
    this.selectedRange = savedPreference.range;
    this.selectedSeason = savedPreference.season;
  }

  private readChartPreference(): { range: DashboardRange; season: string } | null {
    if (typeof localStorage === "undefined") return null;
    try {
      const rawValue = localStorage.getItem(this.chartPreferenceStorageKey);
      if (!rawValue) return null;
      const parsed = JSON.parse(rawValue) as { range?: unknown; season?: unknown };
      const range = this.isDashboardRange(parsed.range) ? parsed.range : "1m";
      const season = this.isDashboardSeason(parsed.season) ? parsed.season : "";
      return { range: season ? "all" : range, season };
    } catch {
      localStorage.removeItem(this.chartPreferenceStorageKey);
      return null;
    }
  }

  private persistChartPreference(): void {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(
      this.chartPreferenceStorageKey,
      JSON.stringify({
        range: this.selectedRange,
        season: this.selectedSeason,
      }),
    );
  }

  private isDashboardRange(value: unknown): value is DashboardRange {
    return this.rangeOptions.some((option) => option.value === value);
  }

  private isDashboardSeason(value: unknown): value is string {
    return (
      typeof value === "string" &&
      (value === "" || /^(spring|summer|autumn|winter)-\d{4}$/.test(value))
    );
  }

  private reconcileSelectedSeason(): boolean {
    if (!this.selectedSeason || this.hasAvailableSeason(this.selectedSeason)) return false;
    this.selectedSeason = "";
    if (this.selectedRange === "all") {
      this.selectedRange = "1m";
    }
    this.persistChartPreference();
    return true;
  }

  private hasAvailableSeason(value: string): boolean {
    return this.availableSeasonOptions.some((option) => option.value === value);
  }

  getRingOffset(progress: number): number {
    const clamped = Math.min(Math.max(progress, 0), 100);
    return this.ringCircumference - (this.ringCircumference * clamped) / 100;
  }

  formatIncludedTypes(types: string[]): string {
    const labels: Record<string, string> = {
      daily: "Diary",
      dream: "Dreams",
      thought_record: "Thought records",
    };
    return types.map((type) => labels[type] || type).join(", ") || "Diary, Dreams";
  }

  private refreshChartData(): void {
    this.chartSeries = this.getVisibleSeries(this.overview?.series || []);
    this.chartMaxWords = Math.max(
      1,
      ...this.chartSeries.map((point) => point.daily_words + point.dream_words),
    );
    this.chartMidWords = Math.round(this.chartMaxWords / 2);
    this.chartMoodPolyline = this.buildMoodPolyline(this.chartSeries);
    this.chartMoodPoints = this.buildMoodPoints(this.chartSeries);
    this.chartTimeTicks = this.buildChartTimeTicks(this.chartSeries);
  }

  private getVisibleSeries(series: DashboardSeriesPoint[]): DashboardSeriesPoint[] {
    const sorted = this.filterSeriesBySeason(series).sort((a, b) =>
      a.date.localeCompare(b.date),
    );
    if (this.selectedRange === "1w") {
      return sorted;
    }
    if (this.selectedSeason) {
      return this.bucketSeries(sorted, "week");
    }
    if (this.selectedRange === "all") {
      return this.bucketSeries(sorted, "month").slice(-24);
    }
    return this.bucketSeries(sorted, "week");
  }

  private filterSeriesBySeason(series: DashboardSeriesPoint[]): DashboardSeriesPoint[] {
    if (!this.selectedSeason) return [...series];
    const bounds = this.getSeasonBounds(this.selectedSeason);
    if (!bounds) return [...series];
    return series.filter((point) => point.date >= bounds.start && point.date <= bounds.end);
  }

  private getSeasonBounds(value: string): { start: string; end: string } | null {
    const [season, yearText] = value.split("-");
    const year = Number(yearText);
    if (!Number.isInteger(year)) return null;
    const bounds: Record<string, [string, string]> = {
      spring: [`${year}-03-01`, `${year}-05-31`],
      summer: [`${year}-06-01`, `${year}-08-31`],
      autumn: [`${year}-09-01`, `${year}-11-30`],
      winter: [`${year}-12-01`, `${year + 1}-02-28`],
    };
    const selected = bounds[season];
    return selected ? { start: selected[0], end: selected[1] } : null;
  }

  private bucketSeries(
    series: DashboardSeriesPoint[],
    mode: "week" | "month",
  ): DashboardSeriesPoint[] {
    const buckets = new Map<
      string,
      {
        daily_words: number;
        dream_words: number;
        thought_records: number;
        mood_values: number[];
        sentiment_values: number[];
      }
    >();
    for (const point of series) {
      const key =
        mode === "month"
          ? `${point.date.slice(0, 7)}-01`
          : this.getWeekBucketKey(point.date);
      const bucket =
        buckets.get(key) ||
        {
          daily_words: 0,
          dream_words: 0,
          thought_records: 0,
          mood_values: [],
          sentiment_values: [],
        };
      bucket.daily_words += point.daily_words;
      bucket.dream_words += point.dream_words;
      bucket.thought_records += point.thought_records;
      if (typeof point.mood_score === "number") {
        bucket.mood_values.push(point.mood_score);
      }
      if (typeof point.sentiment_score === "number") {
        bucket.sentiment_values.push(point.sentiment_score);
      }
      buckets.set(key, bucket);
    }
    return Array.from(buckets.entries())
      .map(([dateKey, bucket]) => ({
        date: dateKey,
        daily_words: bucket.daily_words,
        dream_words: bucket.dream_words,
        thought_records: bucket.thought_records,
        mood_score: this.average(bucket.mood_values),
        sentiment_score: this.average(bucket.sentiment_values),
      }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }

  private getWeekBucketKey(value: string): string {
    const date = new Date(`${value.slice(0, 10)}T12:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    const day = date.getDay() || 7;
    date.setDate(date.getDate() - day + 1);
    return [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, "0"),
      String(date.getDate()).padStart(2, "0"),
    ].join("-");
  }

  private average(values: number[]): number | null {
    if (!values.length) return null;
    return Number(
      (values.reduce((total, value) => total + value, 0) / values.length).toFixed(2),
    );
  }

  getChartX(index: number): number {
    const slot = 600 / Math.max(this.chartSeries.length, 1);
    return 20 + index * slot + slot * 0.16;
  }

  getChartCenterX(index: number, seriesLength = this.chartSeries.length): number {
    const slot = 600 / Math.max(seriesLength, 1);
    return 20 + index * slot + slot / 2;
  }

  getBarWidth(): number {
    return Math.max(6, Math.min(26, (600 / Math.max(this.chartSeries.length, 1)) * 0.56));
  }

  getDailyBarHeight(point: DashboardSeriesPoint): number {
    return Math.max(0, (point.daily_words / this.chartMaxWords) * 140);
  }

  getDreamBarHeight(point: DashboardSeriesPoint): number {
    return Math.max(0, (point.dream_words / this.chartMaxWords) * 140);
  }

  getDailyBarY(point: DashboardSeriesPoint): number {
    return 178 - this.getDailyBarHeight(point);
  }

  getDreamBarY(point: DashboardSeriesPoint): number {
    return this.getDailyBarY(point) - this.getDreamBarHeight(point);
  }

  private buildMoodPolyline(series: DashboardSeriesPoint[]): string {
    const moodPoints = series
      .map((point, index) => ({ point, index }))
      .filter(({ point }) => typeof point.mood_score === "number");
    if (moodPoints.length < 2) return "";
    const slot = 600 / Math.max(series.length, 1);
    return moodPoints
      .map(({ point, index }) => {
        const score = point.mood_score ?? 3;
        const x = this.getChartCenterX(index, series.length);
        const y = 178 - ((score - 1) / 4) * 132;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }

  private buildMoodPoints(
    series: DashboardSeriesPoint[],
  ): Array<{ x: string; y: string; title: string; source: DashboardSeriesPoint }> {
    return series
      .map((point, index) => {
        if (typeof point.mood_score !== "number") return null;
        const x = this.getChartCenterX(index, series.length);
        const y = 178 - ((point.mood_score - 1) / 4) * 132;
        return {
          x: x.toFixed(1),
          y: y.toFixed(1),
          title: this.getChartPointTitle(point, "mood"),
          source: point,
        };
      })
      .filter((
        point,
      ): point is { x: string; y: string; title: string; source: DashboardSeriesPoint } =>
        point !== null,
      );
  }

  private buildChartTimeTicks(series: DashboardSeriesPoint[]): DashboardChartTick[] {
    if (!series.length) return [];
    const maxTicks = this.selectedRange === "1w" && !this.selectedSeason ? 7 : 6;
    const step = Math.max(1, Math.ceil(series.length / maxTicks));
    const selectedIndexes = new Set<number>();
    for (let index = 0; index < series.length; index += step) {
      selectedIndexes.add(index);
    }
    selectedIndexes.add(series.length - 1);

    return Array.from(selectedIndexes)
      .sort((a, b) => a - b)
      .map((index) => {
        const point = series[index];
        return {
          x: this.getChartCenterX(index, series.length).toFixed(1),
          label: this.formatChartTimeTick(point.date),
          fullLabel: this.formatDate(point.date),
        };
      });
  }

  private formatChartTimeTick(value: string): string {
    const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    if (this.selectedRange === "all" && !this.selectedSeason) {
      return parsed.toLocaleDateString(undefined, {
        month: "short",
        year: "2-digit",
      });
    }
    if (this.selectedRange === "1w" && !this.selectedSeason) {
      return parsed.toLocaleDateString(undefined, {
        weekday: "short",
        day: "numeric",
      });
    }
    return parsed.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
    });
  }

  getSelectedSeasonLabel(): string {
    return this.availableSeasonOptions.find((option) => option.value === this.selectedSeason)?.label || "Season";
  }

  selectChartPoint(
    point: DashboardSeriesPoint,
    metric: DashboardChartMetric,
    event?: MouseEvent,
  ): void {
    this.selectedChartPoint = { point, metric };
    this.selectedChartPosition = event
      ? this.getMouseChartPosition(event)
      : this.getKeyboardChartPosition(point, metric);
  }

  clearChartPoint(): void {
    this.selectedChartPoint = null;
  }

  toggleChartExpanded(): void {
    this.isChartExpanded = !this.isChartExpanded;
    this.selectedChartPoint = null;
  }

  getChartSelectionTitle(selection: DashboardChartSelection): string {
    const label = this.formatDate(selection.point.date);
    const metricLabels: Record<DashboardChartMetric, string> = {
      daily: "Diary words",
      dream: "Dream words",
      mood: "Mood score",
    };
    return `${metricLabels[selection.metric]} · ${label}`;
  }

  getChartSelectionDetail(selection: DashboardChartSelection): string {
    const { point, metric } = selection;
    if (metric === "daily") {
      return `${point.daily_words} diary words, ${point.dream_words} dream words, ${point.thought_records} thought records.`;
    }
    if (metric === "dream") {
      return `${point.dream_words} dream words, ${point.daily_words} diary words, ${point.thought_records} thought records.`;
    }
    return point.mood_score === null
      ? "No mood score was saved for this period."
      : `Average mood score ${point.mood_score} out of 5.`;
  }

  private pulseChartAnimation(): void {
    this.isChartAnimating = true;
    if (this.chartAnimationTimer) {
      clearTimeout(this.chartAnimationTimer);
    }
    this.chartAnimationTimer = setTimeout(() => {
      this.isChartAnimating = false;
      this.chartAnimationTimer = null;
    }, 460);
  }

  private getMouseChartPosition(event: MouseEvent): DashboardChartPosition {
    const chart = (event.currentTarget as Element | null)?.closest(".dashboard-chart");
    const rect = chart?.getBoundingClientRect();
    if (!rect?.width || !rect.height) {
      return { left: 50, top: 50 };
    }
    return {
      left: this.clamp((event.clientX - rect.left) / rect.width * 100, 14, 86),
      top: this.clamp((event.clientY - rect.top) / rect.height * 100, 20, 90),
    };
  }

  private getKeyboardChartPosition(
    point: DashboardSeriesPoint,
    metric: DashboardChartMetric,
  ): DashboardChartPosition {
    const index = Math.max(0, this.chartSeries.findIndex((item) => item.date === point.date));
    const x = this.getChartCenterX(index);
    let y = 112;
    if (metric === "daily") {
      y = this.getDailyBarY(point);
    } else if (metric === "dream") {
      y = this.getDreamBarY(point);
    } else if (typeof point.mood_score === "number") {
      y = 178 - ((point.mood_score - 1) / 4) * 132;
    }
    return {
      left: this.clamp((x / 640) * 100, 14, 86),
      top: this.clamp((y / 220) * 100, 20, 90),
    };
  }

  private clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
  }

  getChartPointTitle(
    point: DashboardSeriesPoint,
    metric: "daily" | "dream" | "mood",
  ): string {
    const dateLabel = this.formatDate(point.date);
    if (metric === "daily") {
      return `${dateLabel}: ${point.daily_words} diary words`;
    }
    if (metric === "dream") {
      return `${dateLabel}: ${point.dream_words} dream words`;
    }
    return `${dateLabel}: mood score ${point.mood_score ?? "not set"}`;
  }

  getChartAriaLabel(series: DashboardSeriesPoint[]): string {
    const totalDaily = series.reduce((total, point) => total + point.daily_words, 0);
    const totalDream = series.reduce((total, point) => total + point.dream_words, 0);
    const moodValues = series
      .map((point) => point.mood_score)
      .filter((score): score is number => typeof score === "number");
    const averageMood =
      moodValues.length > 0
        ? (moodValues.reduce((total, score) => total + score, 0) / moodValues.length).toFixed(1)
        : "not enough data";
    return `Dashboard chart showing ${totalDaily} diary words, ${totalDream} dream words, and average mood score ${averageMood}.`;
  }

  getThemeAriaLabel(theme: DashboardTheme): string {
    return `${theme.kind.replace("_", " ")}: ${theme.label}, ${theme.count} ${theme.count === 1 ? "entry" : "entries"}`;
  }

  getThemeWeight(theme: DashboardTheme, themes: DashboardTheme[]): number {
    const max = Math.max(1, ...themes.map((item) => item.count));
    return Math.min(5, Math.max(1, Math.round((theme.count / max) * 5)));
  }

  formatNullableNumber(value: number | null): string {
    return value === null ? "–" : String(Math.round(value));
  }

  formatSignedNumber(value: number | null): string {
    if (value === null) return "–";
    return value > 0 ? `+${Math.round(value)}` : String(Math.round(value));
  }

  getActivityIcon(type: DashboardActivityType): string {
    const icons: Record<DashboardActivityType, string> = {
      daily: "book",
      dream: "nights_stay",
      thought_record: "psychology_alt",
      important_day: "event",
    };
    return icons[type];
  }

  getActivityFallback(type: DashboardActivityType): string {
    const labels: Record<DashboardActivityType, string> = {
      daily: "Open diary entry",
      dream: "Open dream entry",
      thought_record: "Review thought record",
      important_day: "Open important days",
    };
    return labels[type];
  }

  getActivityTypeLabel(type: DashboardActivityType): string {
    const labels: Record<DashboardActivityType, string> = {
      daily: "Diary",
      dream: "Dreams",
      thought_record: "Thought records",
      important_day: "Important days",
    };
    return labels[type];
  }

  getGroupedActivity(
    overview: DashboardOverview,
    type: DashboardActivityType,
  ) {
    return overview.recent_activity_by_type?.[type] || [];
  }

  getActivityMoreLink(type: DashboardActivityType): string[] {
    if (type === "thought_record") return ["/cbt"];
    if (type === "important_day") return ["/important-days"];
    return ["/entries"];
  }

  getActivityMoreQueryParams(type: DashboardActivityType): Record<string, string> | null {
    if (type === "daily") return { type: "daily" };
    if (type === "dream") return { type: "dreams" };
    return null;
  }

  getDreamPeoplePlaces(overview: DashboardOverview): DashboardTheme[] {
    return [
      ...overview.dream_insights.top_people,
      ...overview.dream_insights.top_places,
    ].slice(0, 8);
  }

  getDreamMeta(dream: DashboardDreamLatest): string[] {
    return [
      ...(dream.symbols || []).slice(0, 2),
      ...(dream.people || []).slice(0, 1),
      ...(dream.places || []).slice(0, 1),
    ].filter(Boolean).slice(0, 4);
  }

  trackSeriesPoint(_index: number, point: DashboardSeriesPoint): string {
    return point.date;
  }

  trackMoodPoint(
    _index: number,
    point: { x: string; y: string; title: string; source: DashboardSeriesPoint },
  ): string {
    return `${point.source.date}-${point.x}-${point.y}`;
  }

  trackChartTick(_index: number, tick: DashboardChartTick): string {
    return `${tick.x}-${tick.label}`;
  }

  selectTheme(theme: DashboardTheme): void {
    this.selectedTheme = theme;
  }

  searchTheme(): void {
    if (!this.selectedTheme) return;
    void this.router.navigate(["/entries"], {
      queryParams: { search: this.selectedTheme.label },
    });
  }

  applyThemeFocus(): void {
    if (!this.selectedTheme) return;
    this.activeThemeFilter = this.selectedTheme;
    this.selectedChartPoint = null;
    this.loadOverview("chart");
  }

  clearThemeFocus(): void {
    this.activeThemeFilter = null;
    this.selectedChartPoint = null;
    this.loadOverview("chart");
  }

  searchThemeLike(theme: Pick<DashboardTheme, "label">): void {
    void this.router.navigate(["/entries"], {
      queryParams: { search: theme.label },
    });
  }

  getThemeDriftLabel(theme: DashboardThemeDriftItem): string {
    return `${theme.label}: ${theme.current_count} this period, ${theme.previous_count} previous period`;
  }

  formatCompactThemeLabel(label: string): string {
    return label
      .split(/\s+/)
      .map((word) => (word.length > 8 ? `${word.slice(0, 8)}…` : word))
      .join(" ")
      .slice(0, 24);
  }

  normaliseTestId(value: string): string {
    return value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 48) || "theme";
  }

  getMoodAnchorLabel(score: number): string {
    if (score >= 4.25) return "Positive";
    if (score >= 3.25) return "Steady";
    if (score >= 2.25) return "Mixed";
    return "Low";
  }

  getMoodAnchorTone(score: number): string {
    if (score >= 4.25) return "is-positive";
    if (score >= 3.25) return "is-steady";
    if (score >= 2.25) return "is-mixed";
    return "is-low";
  }

  getMoodAnchorWidth(score: number): number {
    return this.clamp((score / 5) * 100, 4, 100);
  }

  getMoodAnchorTitle(score: number): string {
    return `Average mood score ${score.toFixed(1)} out of 5`;
  }

  getDaysUntilLabel(cue: DashboardImportantDayCue): string {
    if (cue.days_until === null) return "Date";
    if (cue.days_until === 0) return "Today";
    if (cue.days_until === 1) return "Tomorrow";
    return `${cue.days_until} days`;
  }

  getActivityRouterLink(route: string): string[] {
    return [route.split("?")[0]];
  }

  getActivityQueryParams(route: string): Record<string, string> | null {
    const queryString = route.split("?")[1];
    if (!queryString) return null;
    return Object.fromEntries(new URLSearchParams(queryString).entries());
  }

  formatDate(value: string | null): string {
    if (!value) return "";
    const parsed = new Date(`${value.slice(0, 10)}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  toggleQuickLog(event: Event): void {
    event.stopPropagation();
    this.isQuickLogOpen = !this.isQuickLogOpen;
  }

  openQuickAction(action: DashboardQuickAction): void {
    this.isQuickLogOpen = false;
    void this.router.navigateByUrl(action.route);
  }

  scrollToTop(): void {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  @HostListener("document:click", ["$event"])
  closeDashboardOverlays(event: MouseEvent): void {
    const target = event.target as Element | null;
    this.isQuickLogOpen = false;
    if (!target?.closest(".dashboard-chart")) {
      this.selectedChartPoint = null;
    }
  }

  @HostListener("document:keydown.escape")
  closeDashboardOverlaysOnEscape(): void {
    this.isQuickLogOpen = false;
    this.selectedChartPoint = null;
  }
}
