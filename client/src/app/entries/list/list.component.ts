// Entry list with timeline and card grid
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { ViewToggleComponent } from '../../shared/components/view-toggle/view-toggle.component';
import { SearchResultsComponent } from '../../shared/components/search-results/search-results.component';
import { EntriesService } from '../../core/services/entries.service';
import { SearchService } from '../../core/services/search.service';
import { DailyEntry, DreamEntry } from '../../core/models/entry.model';

type TimelineMonth = { label: string; year: string };

@Component({
  selector: 'app-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    ViewToggleComponent,
    SearchResultsComponent
  ],
  styleUrl: './list.component.css',
  template: `
    <div class="list-container">
      <ng-container *ngIf="searchService.results$ | async as searchState">
        <!-- Search Results View -->
        <ng-container *ngIf="searchState.active">
          <div class="search-mode-header">
            <button mat-button (click)="exitSearch()">
              <mat-icon>arrow_back</mat-icon>
              Back to Entries
            </button>
          </div>
          <app-search-results></app-search-results>
        </ng-container>

        <!-- Normal Entries View -->
        <ng-container *ngIf="!searchState.active">
          <div class="list-header">
            <app-view-toggle [value]="currentView" (viewChange)="onViewChange($event)"></app-view-toggle>
            <button mat-raised-button color="primary" routerLink="/entries/create">New Entry</button>
          </div>
          
          <!-- Timeline scroller -->
          <div class="timeline-scroller">
            <button mat-icon-button>
              <mat-icon>chevron_left</mat-icon>
            </button>
            
            <div class="timeline-months">
              <div class="month-item" *ngFor="let item of months">
                <div class="year">{{ item.year }}</div>
                <div class="month">{{ item.label }}</div>
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
                <mat-card-subtitle>{{ entry.entry_date | date:'dd/MM/yyyy' }}</mat-card-subtitle>
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
        </ng-container>
      </ng-container>
    </div>
  `
})
export class ListComponent implements OnInit {
  private entriesService = inject(EntriesService);
  protected readonly searchService = inject(SearchService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  
  months: TimelineMonth[] = this.generateTimelineMonths();
  currentView: 'all' | 'daily' | 'dreams' = 'all';
  dailyEntries: DailyEntry[] = [];
  dreamEntries: DreamEntry[] = [];
  filteredEntries: any[] = [];

  exitSearch(): void {
    this.searchService.clear();
  }
  
  ngOnInit(): void {
    this.route.queryParamMap.subscribe(params => {
      const type = params.get('type');
      if (type === 'daily' || type === 'dreams') {
        this.currentView = type;
      } else {
        this.currentView = 'all';
      }

      this.loadEntries();
    });
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
    this.currentView = view as 'all' | 'daily' | 'dreams';
    this.filterEntries();
    const queryParams = this.currentView === 'all' ? {} : { type: this.currentView };
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      queryParamsHandling: 'merge'
    });
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
    if (entry.type === 'daily') {
      const [title] = this.splitDailyMessage(entry.user_message || '');
      return title || 'Daily Entry';
    }
    return 'Dream Entry';
  }
  
  getEntrySnippet(entry: any): string {
    const text = entry.type === 'daily'
      ? this.splitDailyMessage(entry.user_message || '')[1]
      : entry.plot || entry.user_message || '';
    return text.substring(0, 150) + (text.length > 150 ? '...' : '');
  }

  private splitDailyMessage(message: string): [string, string] {
    const [title, ...rest] = message.split(/\n\n?/);
    if (rest.length === 0) {
      return ['', title];
    }
    return [title, rest.join('\n\n')];
  }

  private generateTimelineMonths(count = 4): TimelineMonth[] {
    const months: TimelineMonth[] = [];
    const now = new Date();
    for (let i = count - 1; i >= 0; i--) {
      const date = new Date(now.getFullYear(), now.getMonth() - i, 1);
      months.push({
        label: date.toLocaleString('default', { month: 'long' }),
        year: date.getFullYear().toString()
      });
    }
    return months;
  }
}
