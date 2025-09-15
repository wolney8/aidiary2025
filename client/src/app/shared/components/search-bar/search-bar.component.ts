// Search bar component from wireframes
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule
  ],
  template: `
    <div class="search-container">
      <mat-icon>search</mat-icon>
      <input 
        type="text" 
        placeholder="Search" 
        [(ngModel)]="searchQuery"
        (keyup.enter)="onSearch()"
      />
    </div>
  `,
  styles: [`
    .search-container {
      display: flex;
      align-items: center;
      background: white;
      border-radius: 4px;
      padding: 4px 12px;
      min-width: 300px;
      
      mat-icon {
        color: #666;
        margin-right: 8px;
      }
      
      input {
        border: none;
        outline: none;
        flex: 1;
        font-size: 14px;
      }
    }
  `]
})
export class SearchBarComponent {
  searchQuery = '';
  
  onSearch(): void {
    console.log('Searching for:', this.searchQuery);
    // Implement search functionality
  }
}