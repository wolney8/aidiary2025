// Settings shell — hosts sub-sections such as Import
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatListModule,
    MatIconModule,
    MatCardModule,
    MatDividerModule
  ],
  template: `
    <div class="settings-container" role="main" aria-label="Settings">
      <mat-card class="settings-nav-card">
        <mat-card-header>
          <mat-card-title>Settings</mat-card-title>
        </mat-card-header>
        <mat-divider></mat-divider>
        <mat-nav-list>
          <a
            mat-list-item
            routerLink="/settings/import"
            routerLinkActive="active-link"
            aria-label="Go to Import Entries"
          >
            <mat-icon matListItemIcon>upload_file</mat-icon>
            <span matListItemTitle>Import Entries</span>
            <span matListItemLine>Bulk import from Excel template</span>
          </a>
        </mat-nav-list>
      </mat-card>

      <div class="settings-content">
        <router-outlet></router-outlet>
      </div>
    </div>
  `,
  styles: [`
    .settings-container {
      display: flex;
      gap: 24px;
      padding: var(--spacing-md, 16px);
      max-width: 1100px;
      margin: 0 auto;
    }

    .settings-nav-card {
      width: 220px;
      flex-shrink: 0;
      align-self: flex-start;
      border-radius: 12px;
    }

    .settings-content {
      flex: 1;
      min-width: 0;
    }

    .active-link {
      background: rgba(123, 63, 242, 0.08) !important;
      color: #7B3FF2 !important;
    }

    @media (max-width: 768px) {
      .settings-container {
        flex-direction: column;
        padding: 8px;
      }

      .settings-nav-card {
        width: 100%;
      }
    }
  `]
})
export class SettingsComponent {}
