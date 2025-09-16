// Side navigation matching wireframes
import { Component, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatDividerModule } from '@angular/material/divider';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-side-nav',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatListModule,
    MatIconModule,
    MatDividerModule
  ],
  template: `
    <div class="sidenav-container">
      <div class="sidenav-header">
        <div class="logo-circle">LOGO</div>
        <h3>AI Diary</h3>
      </div>
      
      <mat-nav-list>
        <a mat-list-item routerLink="/entries" (click)="closeSidenav.emit()">
          <mat-icon matListItemIcon>home</mat-icon>
          <span matListItemTitle>Home</span>
        </a>
        
        <a mat-list-item routerLink="/entries?type=daily" (click)="closeSidenav.emit()">
          <mat-icon matListItemIcon>book</mat-icon>
          <span matListItemTitle>Daily Diary</span>
        </a>
        
        <a mat-list-item routerLink="/entries?type=dream" (click)="closeSidenav.emit()">
          <mat-icon matListItemIcon>nights_stay</mat-icon>
          <span matListItemTitle>Dream Diary</span>
        </a>
        
        <a mat-list-item routerLink="/profile" (click)="closeSidenav.emit()">
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
  styles: [`
    .sidenav-container {
      width: 250px;
      height: 100%;
      background: white;
    }
    
    .sidenav-header {
      padding: var(--spacing-md);
      text-align: center;
      background: #f5f5f5;
    }
    
    .logo-circle {
      width: 60px;
      height: 60px;
      background: black;
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto var(--spacing-sm);
      font-weight: bold;
    }
  `]
})
export class SideNavComponent {
  @Output() closeSidenav = new EventEmitter<void>();
  private authService = inject(AuthService);
  
  logout(): void {
    this.authService.logout();
    this.closeSidenav.emit();
  }
}
