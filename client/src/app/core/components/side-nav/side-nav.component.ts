// Side navigation matching wireframes
import { Component, Output, EventEmitter, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterModule } from "@angular/router";
import { MatListModule } from "@angular/material/list";
import { MatIconModule } from "@angular/material/icon";
import { MatDividerModule } from "@angular/material/divider";
import { AuthService } from "../../services/auth.service";

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
    <div class="sidenav-container">
      <div class="sidenav-header">
        <div class="logo-circle">LOGO</div>
        <h3>AI Diary</h3>
      </div>

      <mat-nav-list>
        <a
          mat-list-item
          routerLink="/entries"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #homeRla="routerLinkActive"
          [attr.aria-current]="homeRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
        >
          <mat-icon matListItemIcon>home</mat-icon>
          <span matListItemTitle>Home</span>
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
          routerLink="/profile"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          #profileRla="routerLinkActive"
          [attr.aria-current]="profileRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
        >
          <mat-icon matListItemIcon>person</mat-icon>
          <span matListItemTitle>Profile</span>
        </a>

        <a
          mat-list-item
          routerLink="/settings"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: false }"
          #settingsRla="routerLinkActive"
          [attr.aria-current]="settingsRla.isActive ? 'page' : null"
          (click)="closeSidenav.emit()"
        >
          <mat-icon matListItemIcon>settings</mat-icon>
          <span matListItemTitle>Settings</span>
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
        width: 250px;
        height: 100%;
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
        background: var(--colour-secondary);
        color: var(--colour-surface);
        border-radius: var(--radius-pill);
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto var(--spacing-sm);
        font-weight: 700;
      }

      .sidenav-container a[mat-list-item] {
        border-radius: var(--radius-sm);
        margin: 2px 8px;
        color: var(--colour-text-primary);
      }

      .sidenav-container a[mat-list-item]:hover {
        background: var(--colour-surface-muted);
      }

      .sidenav-container a[mat-list-item].is-active {
        background: var(--colour-surface-muted);
        border-left: 3px solid var(--colour-primary);
        font-weight: 600;
      }

      .sidenav-container a[mat-list-item].is-active mat-icon {
        color: var(--colour-primary);
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

  logout(): void {
    this.authService.logout();
    this.closeSidenav.emit();
  }
}
