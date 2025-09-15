// Entry list with timeline and card grid
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { ViewToggleComponent } from '../../shared/components/view-toggle/view-toggle.component';
import { EntriesService } from '../../core/services/entries.service';
import { DailyEntry, DreamEntry } from '../../core/models/entry.model';

@Component({
  selector: 'app-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    ViewToggleComponent
  ],
  template: `
    <div class="list-container">
      <app-view-toggle (viewChange)="onViewChange($event)"></app-view-toggle>
      
      <!-- Timeline scroller -->
      <div class="timeline-scroller">
        <button mat-icon-button>
          <mat-icon>chevron_left</mat-icon>
        </button>
        
        <div class="timeline-months">
          <div class="month-item" *ngFor="let month of months">
            <div class="year">2024</div>
            <div class="month">{{ month }}</div>
          </div>
        </div>
        
        <button mat-icon-button>
          <mat-icon>chevron_right</mat-icon>
        </button>
      </div>
      
      <!-- Entry cards grid -->
      <div class="entries-grid">
        <mat-card class="entry-card" *ngFor="let entry of filteredEntries">
          <mat-card-header>
            <mat-icon mat-card-avatar>
              {{ entry.type === 'dream' ? 'nights_stay' : 'book' }}
            </mat-icon>
            <mat-card-title>{{ getEntryTitle(entry) }}</mat-card-title>
            <mat-card-subtitle>{{ entry.entry_date | date:'EEEE d MMMM yyyy' }}</mat-card-subtitle>
          </mat-card-header>
          
          <mat-card-content>
            <div class="entry-image-placeholder">
              <!-- Chart placeholder matching wireframes -->
              <mat-icon>pie_chart</mat-icon>
            </div>
            <p>{{ getEntrySnippet(entry) }}</p>
          </mat-card-content>
          
          <mat-card-actions>
            <a mat-button color="primary" [routerLink]="['/entries', entry.id]">
              VIEW ENTRY
            </a>
            <button mat-icon-button>
              <mat-icon>favorite_border</mat-icon>
            </button>
            <button mat-icon-button>
              <mat-icon>share</mat-icon>
            </button>
          </mat-card-actions>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .timeline-scroller {
      display: flex;
      align-items: center;
      padding: var(--spacing-md) 0;
      border-bottom: 1px solid #e0e0e0;
    }
    
    .timeline-months {
      display: flex;
      gap: var(--spacing-lg);
      overflow-x: auto;
      flex: 1;
      padding: 0 var(--spacing-sm);
    }
    
    .month-item {
      text-align: center;
      min-width: 100px;
      
      .year {
        font-size: 12px;
        color: #666;
      }
      
      .month {
        font-weight: 500;
      }
    }
    
    .entries-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: var(--spacing-md);
      padding: var(--spacing-md) 0;
    }
    
    .entry-card {
      cursor: pointer;
      
      .entry-image-placeholder {
        height: 150px;
        background: #f5f5f5;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: var(--spacing-sm);
        
        mat-icon {
          font-size: 48px;
          width: 48px;
          height: 48px;
          color: #ccc;
        }
      }
    }
  `]
})
export class ListComponent implements OnInit {
  private entriesService = inject(EntriesService);
  
  months = ['September', 'October', 'November', 'December'];
  currentView = 'all';
  dailyEntries: DailyEntry[] = [];
  dreamEntries: DreamEntry[] = [];
  filteredEntries: any[] = [];
  
  ngOnInit(): void {
    this.loadEntries();
  }
  
  loadEntries(): void {
    this.entriesService.getDailyEntries().subscribe(entries => {
      this.dailyEntries = entries.map(e => ({ ...e, type: 'daily' }));
      this.filterEntries();
    });
    
    this.entriesService.getDreamEntries().subscribe(entries => {
      this.dreamEntries = entries.map(e => ({ ...e, type: 'dream' }));
      this.filterEntries();
    });
  }
  
  onViewChange(view: string): void {
    this.currentView = view;
    this.filterEntries();
  }
  
  filterEntries(): void {
    if (this.currentView === 'daily') {
      this.filteredEntries = this.dailyEntries;
    } else if (this.currentView === 'dreams') {
      this.filteredEntries = this.dreamEntries;
    } else {
      this.filteredEntries = [...this.dailyEntries, ...this.dreamEntries]
        .sort((a, b) => new Date(b.entry_date).getTime() - new Date(a.entry_date).getTime());
    }
  }
  
  getEntryTitle(entry: any): string {
    if (entry.type === 'dream' && entry.title) {
      return `"${entry.title}"`;
    }
    return entry.type === 'dream' ? 'Dream Entry' : 'Daily Entry';
  }
  
  getEntrySnippet(entry: any): string {
    const text = entry.user_message || entry.plot || '';
    return text.substring(0, 150) + (text.length > 150 ? '...' : '');
  }
}