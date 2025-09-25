import { Component, Output, EventEmitter, inject, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Router, RouterModule, NavigationEnd } from '@angular/router';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
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
    MatProgressSpinnerModule,
    RouterModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule
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
            <button type="button" class="search-button" (click)="filterResults()" [disabled]="isSearching">
              <mat-progress-spinner *ngIf="isSearching" diameter="20" mode="indeterminate"></mat-progress-spinner>
              <mat-icon *ngIf="!isSearching">search</mat-icon>
            </button>
            <input
              class="search-input"
              type="search"
              placeholder="Search entries, tags, people, dates..."
              formControlName="query"
              (keydown.enter)="$event.preventDefault(); filterResults()"
              [disabled]="isSearching"
            />
          </div>
        </form>
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
  
  // Track search loading state
  isSearching = false;

  searchForm = this.fb.group({
    query: ['']
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
      }
    });
  }

  logout(): void {
    this.authService.logout();
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
    // Always search all categories since we removed filters
    const filters = {
      tags: true,
      date: true,
      keywords: true,
      people: true
    };

    this.isSearching = true;
    this.searchService.search(normalized, filters).subscribe({
      next: () => {
        this.isSearching = false;
      },
      error: () => {
        this.isSearching = false;
      },
      complete: () => {
        this.isSearching = false;
      }
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
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
