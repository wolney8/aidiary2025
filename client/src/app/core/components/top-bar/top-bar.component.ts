// Top navigation bar matching wireframes
import { Component, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { RouterModule } from '@angular/router';
import { SearchBarComponent } from '../../../shared/components/search-bar/search-bar.component';
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
    SearchBarComponent
  ],
  template: `
    <mat-toolbar color="primary">
      <button mat-icon-button (click)="toggleSidenav.emit()">
        <mat-icon>menu</mat-icon>
      </button>
      
      <div class="logo">LOGO</div>

      <div class="search-wrapper">
        <app-search-bar></app-search-bar>
        <button mat-icon-button class="filter-button">
          <mat-icon>filter_list</mat-icon>
        </button>
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
      align-items: center;
      gap: var(--spacing-sm);
      flex: 1;
      justify-content: center;
    }

    .search-wrapper app-search-bar {
      flex: 0 1 420px;
    }

    .filter-button {
      background: white;
      color: var(--mat-toolbar-container-text-color);
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

  userName$: Observable<string | null> = this.authService.currentUser$.pipe(
    map(user => user?.first_name || user?.username || null)
  );

  versionLabel = APP_VERSION;

  logout(): void {
    this.authService.logout();
  }
}
