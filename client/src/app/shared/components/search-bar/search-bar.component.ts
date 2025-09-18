// Search bar component from wireframes
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormControl } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-search-bar',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatIconModule
  ],
  template: `
    <mat-form-field appearance="outline" class="search-field">
      <mat-icon matPrefix>search</mat-icon>
      <input
        matInput
        placeholder="Search"
        [formControl]="searchControl"
        (keyup.enter)="onSearch()"
      />
    </mat-form-field>
  `,
  styles: [`
    .search-field {
      width: 100%;
      max-width: 420px;
    }
  `]
})
export class SearchBarComponent {
  searchControl = new FormControl('');

  onSearch(): void {
    console.log('Searching for:', this.searchControl.value);
    // Implement search functionality
  }
}
