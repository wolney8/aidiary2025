import {
  Component,
  Output,
  EventEmitter,
  inject,
  OnDestroy,
  OnInit,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatToolbarModule } from "@angular/material/toolbar";
import { MatIconModule } from "@angular/material/icon";
import { MatButtonModule } from "@angular/material/button";
import { MatMenuModule } from "@angular/material/menu";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
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
    <mat-toolbar color="primary">
      <button mat-icon-button (click)="toggleSidenav.emit()">
        <mat-icon>menu</mat-icon>
      </button>

      <button class="logo" (click)="goHome()" aria-label="Home">LOGO</button>

      <div class="search-wrapper">
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
          </div>

          <!-- Search History Dropdown (Google-style) -->
          <div
            class="search-history-dropdown"
            *ngIf="
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

      <span class="spacer"></span>

      <div class="user-section">
        <span class="user-name" *ngIf="userName$ | async as name">{{
          name
        }}</span>
        <span class="version-label">{{ versionLabel }}</span>
        <button mat-icon-button [matMenuTriggerFor]="userMenu">
          <mat-icon>account_circle</mat-icon>
        </button>
      </div>

      <mat-menu #userMenu="matMenu">
        <button mat-menu-item routerLink="/profile">Profile</button>
        <button mat-menu-item routerLink="/settings/import">
          Import Entries
        </button>
        <button mat-menu-item (click)="logout()">Logout</button>
      </mat-menu>
    </mat-toolbar>
  `,
  styles: [
    `
      mat-toolbar {
        gap: var(--spacing-sm);
      }
      .logo {
        background: var(--colour-secondary);
        color: #ffffff;
        padding: 8px 16px;
        border-radius: var(--radius-pill);
        font-weight: 700;
        cursor: pointer;
        border: none;
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
      }
      .search-form {
        width: 100%;
        max-width: 540px;
        position: relative;
      }
      .search-shell {
        display: flex;
        align-items: center;
        width: 100%;
        background: var(--colour-surface);
        border-radius: var(--radius-pill);
        border: 1px solid var(--colour-border);
        padding: 6px 12px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12);
      }
      .search-shell:focus-within {
        border-color: var(--colour-primary);
        box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.2);
      }
      .search-button {
        background: none;
        border: none;
        color: var(--colour-text-secondary);
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
        color: var(--colour-text-primary);
      }
      .search-input::placeholder {
        color: var(--colour-text-secondary);
      }
      .user-section {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }
      .version-label {
        font-size: 12px;
        padding: 4px 8px;
        background: rgba(255, 255, 255, 0.28);
        border-radius: var(--radius-pill);
        border: 1px solid rgba(255, 255, 255, 0.35);
        color: #ffffff;
      }

      /* Search History Dropdown - Google Style */
      .search-history-dropdown {
        position: absolute;
        top: calc(100% + 4px);
        left: 0;
        right: 0;
        background: var(--colour-surface);
        border-radius: var(--radius-md);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
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
        border-bottom: 1px solid #e2e8f0;
        transition: background-color 0.2s ease;
      }

      .search-history-item:hover {
        background-color: var(--colour-surface-muted);
      }

      .search-history-item:last-child {
        border-bottom: none;
      }

      .history-icon {
        color: #64748b;
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
        color: #d73502 !important;
        font-weight: 600 !important;
        background: rgba(215, 53, 2, 0.15) !important;
        padding: 1px 2px !important;
        border-radius: 2px !important;
        display: inline !important;
      }

      .history-remove {
        background: none;
        border: none;
        color: #64748b;
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

      .history-remove:hover {
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
        color: #999;
        font-size: 14px;
        gap: 8px;
      }

      .empty-icon {
        color: #ccc;
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
  @Output() toggleSidenav = new EventEmitter<void>();
  private authService = inject(AuthService);
  private searchService = inject(SearchService);
  private router = inject(Router);
  private location = inject(Location);
  private fb = inject(FormBuilder);
  private sanitizer = inject(DomSanitizer);
  private destroy$ = new Subject<void>();

  // Search History Properties
  protected searchHistory: string[] = [];
  protected filteredSearchHistory: string[] = [];
  protected showSearchHistory = false;
  protected searchInputFocused = false;
  protected currentSearchQuery = "";

  userName$: Observable<string | null> = this.authService.currentUser$.pipe(
    map((user) => user?.first_name || user?.username || null),
  );

  versionLabel = APP_VERSION;

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
        }
      });
  }

  logout(): void {
    this.authService.logout();
  }

  filterResults(): void {
    const query = this.searchForm.value.query?.trim() || "";
    if (!query) return;

    const currentPath = this.location.path() || "";
    if (!currentPath.includes("/entries")) {
      // Navigate to entries with search query - let the route handler trigger search
      this.router.navigate(["/entries"], { queryParams: { search: query } });
    } else {
      // Already on entries page, just update query param
      this.router.navigate(["/entries"], { queryParams: { search: query } });
    }
  }

  private performSearch(query: string): void {
    const normalized = this.normalizeQuery(query);
    // Always search all categories since we removed filters
    const filters = {
      tags: true,
      date: true,
      keywords: true,
      people: true,
    };

    this.isSearching = true;
    // Disable the search input during search
    this.searchForm.get("query")?.disable();

    this.searchService.search(normalized, filters).subscribe({
      next: () => {
        this.isSearching = false;
        this.searchForm.get("query")?.enable();
      },
      error: () => {
        this.isSearching = false;
        this.searchForm.get("query")?.enable();
      },
      complete: () => {
        this.isSearching = false;
        this.searchForm.get("query")?.enable();
      },
    });
  }

  private normalizeQuery(query: string): string {
    const ordinalDate =
      /^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+\d{2,4})?$/i;
    const m = query.match(ordinalDate);
    if (m) {
      const day = parseInt(m[1], 10);
      const monthName = m[2].toLowerCase();
      const months: Record<string, string> = {
        january: "01",
        february: "02",
        march: "03",
        april: "04",
        may: "05",
        june: "06",
        july: "07",
        august: "08",
        september: "09",
        october: "10",
        november: "11",
        december: "12",
        jan: "01",
        feb: "02",
        mar: "03",
        apr: "04",
        jun: "06",
        jul: "07",
        aug: "08",
        sep: "09",
        sept: "09",
        oct: "10",
        nov: "11",
        dec: "12",
      };
      const mm = months[monthName];
      if (mm) {
        const dd = day < 10 ? `0${day}` : `${day}`;
        return `${dd}/${mm}`;
      }
    }
    return query;
  }

  goHome(): void {
    this.router.navigate(["/entries"]).then(() => {
      this.searchService.clear();
      this.searchForm.patchValue({ query: "" });
    });
  }

  // Search History Methods

  ngOnInit(): void {
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
