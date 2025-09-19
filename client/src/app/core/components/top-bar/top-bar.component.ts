// Top navigation bar matching wireframes
import { Component, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { RouterModule } from '@angular/router';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../../services/auth.service';
import { APP_VERSION } from '../../../version';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

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
      
      <div class="logo">LOGO</div>

      <div class="search-wrapper">
        <form [formGroup]="searchForm" (ngSubmit)="filterResults()" class="search-form">
          <mat-form-field appearance="outline" class="search-field">
            <mat-icon matPrefix>search</mat-icon>
            <input matInput placeholder="Search" formControlName="query">
            <button mat-icon-button matSuffix type="button" (click)="toggleFilters()">
              <mat-icon [class.active-filter]="hasActiveFilters">filter_list</mat-icon>
              <span class="filter-indicator" *ngIf="hasActiveFilters"></span>
            </button>
          </mat-form-field>
          <button mat-flat-button color="accent" type="submit">Search</button>
        </form>

        <div class="filter-panel" *ngIf="showFilters">
          <mat-divider></mat-divider>
          <div class="filter-row">
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
  styles: [`
    mat-toolbar {
      gap: var(--spacing-sm);
    }
    
    .logo {
      background: black;
      color: white;
      padding: 8px 16px;
      border-radius: 20px;
      font-weight: bold;
    }

    .spacer {
      flex: 1;
    }

    .search-wrapper {
      display: flex;
      flex-direction: column;
      align-items: center;
      flex: 1;
      gap: var(--spacing-sm);
    }

    .search-form {
      display: flex;
      gap: var(--spacing-sm);
      align-items: center;
      width: 100%;
      max-width: 520px;
    }

    .search-field {
      flex: 1;
    }

    .filter-indicator {
      display: inline-block;
      width: 8px;
      height: 8px;
      background: #e53935;
      border-radius: 50%;
      margin-left: 4px;
    }

    .filter-panel {
      position: absolute;
      top: 64px;
      background: white;
      color: black;
      padding: var(--spacing-sm) var(--spacing-md);
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      display: flex;
      flex-direction: column;
      gap: var(--spacing-sm);
      z-index: 10;
    }

    .filter-row {
      display: flex;
      gap: var(--spacing-lg);
    }

    .filter-panel mat-checkbox {
      margin-right: var(--spacing-sm);
    }

    @media (max-width: 768px) {
      .filter-panel {
        right: var(--spacing-sm);
      }
    }

    .user-section {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }

    .user-name {
      font-weight: 500;
    }

    .version-label {
      font-size: 12px;
      padding: 4px 8px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 12px;
    }
  `]
})
export class TopBarComponent {
  @Output() toggleSidenav = new EventEmitter<void>();
  private authService = inject(AuthService);
  private fb = inject(FormBuilder);

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

  get hasActiveFilters(): boolean {
    const { filterTags, filterDate, filterKeywords, filterPeople } = this.searchForm.value;
    return Boolean(filterTags || filterDate || filterKeywords || filterPeople);
  }

  logout(): void {
    this.authService.logout();
  }

  toggleFilters(): void {
    this.showFilters = !this.showFilters;
  }

  filterResults(): void {
    const { query, filterTags, filterDate, filterKeywords, filterPeople } = this.searchForm.value;
    console.log('Search request', { query, filterTags, filterDate, filterKeywords, filterPeople });
    this.showFilters = false;
  }
}
