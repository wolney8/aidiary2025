// Side navigation matching wireframes
import { Component, Output, EventEmitter, computed, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterModule } from "@angular/router";
import { MatListModule } from "@angular/material/list";
import { MatIconModule } from "@angular/material/icon";
import { MatDividerModule } from "@angular/material/divider";
import { AuthService } from "../../services/auth.service";
import { ThemeService } from "../../services/theme.service";

@Component({
  selector: "app-side-nav",
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatListModule,
    MatIconModule,
    MatDividerModule,
  ],
  template: `
    <div class="sidenav-container" data-testid="app-side-nav">
      <div class="sidenav-header">
        <div class="logo-circle" aria-hidden="true">
          <img
            class="brand-logo-image"
            [src]="brandLogoSrc()"
            alt=""
          />
        </div>
        <h3>OpenMynd</h3>
      </div>

      <mat-nav-list>
        <a
          mat-list-item
          routerLink="/dashboard"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #dashboardRla="routerLinkActive"
          [attr.aria-current]="dashboardRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
          data-testid="nav-dashboard"
        >
          <mat-icon matListItemIcon>dashboard</mat-icon>
          <span matListItemTitle>Dashboard</span>
        </a>

        <a
          mat-list-item
          routerLink="/entries"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #entriesRla="routerLinkActive"
          [attr.aria-current]="entriesRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
          data-testid="nav-entries"
        >
          <mat-icon matListItemIcon>auto_stories</mat-icon>
          <span matListItemTitle>Entries</span>
        </a>

        <a
          mat-list-item
          [routerLink]="['/entries']"
          [queryParams]="{ type: 'daily' }"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #dailyRla="routerLinkActive"
          [attr.aria-current]="dailyRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
        >
          <mat-icon matListItemIcon>book</mat-icon>
          <span matListItemTitle>Daily Diary</span>
        </a>

        <a
          mat-list-item
          [routerLink]="['/entries']"
          [queryParams]="{ type: 'dreams' }"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #dreamsRla="routerLinkActive"
          [attr.aria-current]="dreamsRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
        >
          <mat-icon matListItemIcon>nights_stay</mat-icon>
          <span matListItemTitle>Dream Diary</span>
        </a>

        <a
          mat-list-item
          routerLink="/cbt"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: false }"
          #cbtRla="routerLinkActive"
          [attr.aria-current]="cbtRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
          data-testid="nav-thought-records"
        >
          <mat-icon matListItemIcon>psychology_alt</mat-icon>
          <span matListItemTitle>Thought Records</span>
        </a>

        <a
          mat-list-item
          routerLink="/important-days"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #importantDaysRla="routerLinkActive"
          [attr.aria-current]="importantDaysRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
          data-testid="nav-important-days"
        >
          <mat-icon matListItemIcon>event</mat-icon>
          <span matListItemTitle>Important Days</span>
        </a>

        <a
          mat-list-item
          routerLink="/reflections"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #reflectionsRla="routerLinkActive"
          [attr.aria-current]="reflectionsRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
          data-testid="nav-reflection-summaries"
        >
          <mat-icon matListItemIcon>summarize</mat-icon>
          <span matListItemTitle>Reflections</span>
        </a>

        <mat-divider></mat-divider>

        <a mat-list-item (click)="logout()">
          <mat-icon matListItemIcon>logout</mat-icon>
          <span matListItemTitle>Logout</span>
        </a>
      </mat-nav-list>
    </div>
  `,
  styles: [
    `
      .sidenav-container {
        box-sizing: border-box;
        width: 250px;
        height: 100%;
        overflow-x: hidden;
        background: var(--colour-surface);
        border-right: 1px solid var(--colour-border);
      }

      .sidenav-header {
        padding: var(--spacing-md);
        text-align: center;
        background: var(--colour-surface-muted);
        border-bottom: 1px solid var(--colour-border);
      }

      .logo-circle {
        width: 60px;
        height: 60px;
        border-radius: var(--radius-pill);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto var(--spacing-sm);
        overflow: hidden;
        background: var(--colour-surface-elevated);
        border: 1px solid var(--colour-border);
        box-shadow: 0 8px 18px var(--colour-shadow-soft);
      }

      .brand-logo-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .sidenav-container a[mat-list-item] {
        box-sizing: border-box;
        width: calc(100% - var(--spacing-sm));
        min-height: 48px;
        border-radius: var(--radius-pill);
        margin: 4px var(--spacing-xs);
        color: var(--colour-text-primary);
      }

      .sidenav-container a[mat-list-item]:hover {
        background: var(--colour-control-hover);
      }

      .sidenav-container a[mat-list-item].is-active {
        background: var(--colour-control-selected);
        color: var(--colour-control-selected-text);
        box-shadow: 0 8px 18px var(--colour-primary-shadow);
        font-weight: 800;
      }

      .sidenav-container a[mat-list-item].is-active mat-icon {
        color: currentColor;
      }

      .sidenav-container a[mat-list-item]:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }
    `,
  ],
})
export class SideNavComponent {
  @Output() closeSidenav = new EventEmitter<void>();
  private authService = inject(AuthService);
  private readonly themeService = inject(ThemeService);
  readonly brandLogoSrc = computed(() =>
    this.themeService.isDark()
      ? "assets/brand/openmynd-logo-dark.jpg"
      : "assets/brand/openmynd-logo-light.jpg",
  );

  logout(): void {
    this.authService.logout();
    this.closeSidenav.emit();
  }
}
