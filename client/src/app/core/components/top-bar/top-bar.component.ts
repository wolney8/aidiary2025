import { Component, Output, EventEmitter, inject, OnDestroy, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { Router, RouterModule, NavigationEnd } from '@angular/router';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../../services/auth.service';
import { APP_VERSION } from '../../../version';
import { Observable, Subject } from 'rxjs';
import { map, filter, takeUntil } from 'rxjs/operators';
import { SearchService } from '../../services/search.service';
import { Location } from '@angular/common';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [
    CommonModule,
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    MatMenuModule,
    RouterModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatCheckboxModule,
    MatDividerModule
  ],
  template: `
    <mat-toolbar color="primary">
      <button mat-icon-button (click)="toggleSidenav.emit()">
        <mat-icon>menu</mat-icon>
      </button>

      <button class="logo" (click)="goHome()" aria-label="Home">LOGO</button>

      <div class="search-wrapper">
        <form [formGroup]="searchForm" (ngSubmit)="filterResults()" class="search-form">
          <div class="search-shell">
            <button type="button" class="search-button" (click)="filterResults()">
              <mat-icon>search</mat-icon>
            </button>
            <input
              class="search-input"
              type="search"
              placeholder="Search"
              formControlName="query"
              (keydown.enter)="$event.preventDefault(); filterResults()"
            />
            <button type="button" class="filter-button" (click)="toggleFilters()">
              <mat-icon>tune</mat-icon>
              <span class="filter-dot" *ngIf="hasActiveFilters"></span>
            </button>
          </div>
        </form>

        <div class="filter-panel" *ngIf="showFilters">
          <mat-divider></mat-divider>
          <div class="filter-list" [formGroup]="searchForm">
            <mat-checkbox formControlName="filterTags">Tags</mat-checkbox>
            <mat-checkbox formControlName="filterDate">Date</mat-checkbox>
            <mat-checkbox formControlName="filterKeywords">Keywords</mat-checkbox>
            <mat-checkbox formControlName="filterPeople">People&apos;s Names</mat-checkbox>
          </div>
        </div>
      </div>

      <span class="spacer"></span>

      <div class="user-section">
        <span class="user-name" *ngIf="userName$ | async as name">{{ name }}</span>
        <span class="version-label">{{ versionLabel }}</span>
        <button mat-icon-button [matMenuTriggerFor]="userMenu">
          <mat-icon>account_circle</mat-icon>
        </button>
      </div>

      <mat-menu #userMenu="matMenu">
        <button mat-menu-item routerLink="/profile">Settings</button>
        <button mat-menu-item (click)="logout()">Logout</button>
      </mat-menu>
    </mat-toolbar>
  `,
  styles: [
    `
    mat-toolbar { gap: var(--spacing-sm); }
    .logo { background: black; color: white; padding: 8px 16px; border-radius: 20px; font-weight: bold; cursor: pointer; border: none; }
    .spacer { flex: 1; }
    .search-wrapper { position: relative; display: flex; flex-direction: column; align-items: center; flex: 1; gap: var(--spacing-sm); }
    .search-form { width: 100%; max-width: 540px; }
    .search-shell { display: flex; align-items: center; width: 100%; background: white; border-radius: 999px; padding: 6px 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
    .search-button { background: none; border: none; color: #616161; cursor: pointer; padding: 4px; margin-right: 8px; }
    .search-input { flex: 1; border: none; outline: none; font-size: 16px; background: transparent; }
    .filter-button { position: relative; border: none; background: transparent; cursor: pointer; width: 32px; height: 32px; }
    .filter-dot { position: absolute; top: 4px; right: 4px; width: 8px; height: 8px; background: #e53935; border-radius: 50%; }
    .filter-panel { position: absolute; top: 56px; width: 260px; background: white; color: #212121; padding: var(--spacing-sm) var(--spacing-md); border-radius: 12px; box-shadow: 0 12px 32px rgba(0,0,0,0.2); display: flex; flex-direction: column; gap: var(--spacing-sm); z-index: 20; }
    .filter-list { display: flex; flex-direction: column; gap: var(--spacing-sm); }
    .user-section { display: flex; align-items: center; gap: var(--spacing-sm); }
    .version-label { font-size: 12px; padding: 4px 8px; background: rgba(255,255,255,0.2); border-radius: 12px; }
    `
  ]
})
export class TopBarComponent implements OnDestroy {
  @Output() toggleSidenav = new EventEmitter<void>();
  private authService = inject(AuthService);
  private searchService = inject(SearchService);
  private router = inject(Router);
  private location = inject(Location);
  private fb = inject(FormBuilder);
  private destroy$ = new Subject<void>();

  userName$: Observable<string | null> = this.authService.currentUser$.pipe(
    map(user => user?.first_name || user?.username || null)
  );

  versionLabel = APP_VERSION;
  showFilters = false;

  searchForm = this.fb.group({
    query: [''],
    filterTags: [false],
    filterDate: [false],
    filterKeywords: [false],
    filterPeople: [false]
  });

  constructor() {
    // Clear search when navigating away from entries
    this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd),
      takeUntil(this.destroy$)
    ).subscribe((event) => {
      if (!event || !event.url) return;
      if (!event.url.includes('/entries')) {
        this.searchService.clear();
        this.searchForm.patchValue({ query: '' });
        this.showFilters = false;
      }
    });
  }

  get hasActiveFilters(): boolean {
    const v = this.searchForm.value;
    return Boolean(v.filterTags || v.filterDate || v.filterKeywords || v.filterPeople);
  }

  logout(): void {
    this.authService.logout();
  }

  toggleFilters(): void {
    this.showFilters = !this.showFilters;
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.showFilters) return;
    const target = event.target as HTMLElement | null;
    if (!target) return;

    // Walk up the DOM to see if the click occurred inside the filter panel or button
    let el: HTMLElement | null = target;
    while (el) {
      if (el.classList && (el.classList.contains('filter-panel') || el.classList.contains('filter-button'))) {
        return; // click inside, do nothing
      }
      el = el.parentElement;
    }

    // otherwise close
    this.showFilters = false;
  }

  filterResults(): void {
    const query = this.searchForm.value.query?.trim() || '';
    if (!query) return;

    const currentPath = this.location.path() || '';
    if (!currentPath.includes('/entries')) {
      this.router.navigate(['/entries']).then(() => this.performSearch(query));
    } else {
      this.performSearch(query);
    }
  }

  private performSearch(query: string): void {
    const normalized = this.normalizeQuery(query);
    const v = this.searchForm.value;
    const filters = {
      tags: !!v.filterTags,
      date: !!v.filterDate,
      keywords: !!v.filterKeywords,
      people: !!v.filterPeople
    };

    this.searchService.search(normalized, filters).subscribe({
      next: () => this.showFilters = false,
      error: () => this.showFilters = false,
      complete: () => this.showFilters = false
    });
  }

  private normalizeQuery(query: string): string {
    const ordinalDate = /^(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)(?:\s+\d{2,4})?$/i;
    const m = query.match(ordinalDate);
    if (m) {
      const day = parseInt(m[1], 10);
      const monthName = m[2].toLowerCase();
      const months: Record<string, string> = {
        january: '01', february: '02', march: '03', april: '04', may: '05', june: '06',
        july: '07', august: '08', september: '09', october: '10', november: '11', december: '12',
        jan: '01', feb: '02', mar: '03', apr: '04', jun: '06', jul: '07', aug: '08', sep: '09', sept: '09', oct: '10', nov: '11', dec: '12'
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
    this.router.navigate(['/entries']).then(() => {
      this.searchService.clear();
      this.searchForm.patchValue({ query: '' });
      this.showFilters = false;
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
