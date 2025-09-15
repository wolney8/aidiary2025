// Top navigation bar matching wireframes
import { Component, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { SearchBarComponent } from '../../shared/components/search-bar/search-bar.component';

@Component({
  selector: 'app-top-bar',
  standalone: true,
  imports: [
    CommonModule,
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    SearchBarComponent
  ],
  template: `
    <mat-toolbar color="primary">
      <button mat-icon-button (click)="toggleSidenav.emit()">
        <mat-icon>menu</mat-icon>
      </button>
      
      <div class="logo">LOGO</div>
      
      <app-search-bar></app-search-bar>
      
      <span class="spacer"></span>
      
      <button mat-icon-button>
        <mat-icon>filter_list</mat-icon>
      </button>
      
      <button mat-icon-button>
        <mat-icon>account_circle</mat-icon>
      </button>
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
  `]
})
export class TopBarComponent {
  @Output() toggleSidenav = new EventEmitter<void>();
}