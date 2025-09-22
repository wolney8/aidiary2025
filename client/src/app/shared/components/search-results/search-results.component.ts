import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SearchService, SearchResult, SearchState } from '../../../core/services/search.service';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

@Component({
  selector: 'app-search-results',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule
  ],
  template: `
    <div *ngIf="results$ | async as searchState" class="search-results">
      <div *ngIf="searchState.active" class="search-header">
        <h2>Search results for "{{ searchState.query }}" in {{ searchState.filters_display }}</h2>
      </div>

      <!-- Loading Spinner -->
      <div *ngIf="searchState.loading" class="loading-overlay">
        <mat-progress-spinner diameter="56" mode="indeterminate"></mat-progress-spinner>
      </div>

      <!-- Error Panel -->
      <mat-card *ngIf="searchState.error" class="error-card">
        <mat-card-title>Search Error</mat-card-title>
        <mat-card-content>
          <p>{{ searchState.error }}</p>
        </mat-card-content>
        <mat-card-actions>
          <button mat-raised-button color="primary" (click)="retry(searchState)">Retry</button>
          <button mat-button (click)="searchService.clear()">Close</button>
        </mat-card-actions>
      </mat-card>
      
      <div class="results-grid">
        <mat-card *ngFor="let result of searchState.results" class="entry-card" 
                  [class.expanded]="isExpanded(result.id)">
          <!-- Main Card View -->
          <mat-card-header (click)="toggleExpand(result.id)">
            <mat-icon mat-card-avatar>
              {{ result.type === 'dream' ? 'nights_stay' : 'book' }}
            </mat-icon>
            <mat-card-title [innerHTML]="result.title_highlight"></mat-card-title>
            <mat-card-subtitle>{{ result.entry_date_display }}</mat-card-subtitle>
          </mat-card-header>
          
          <mat-card-content (click)="toggleExpand(result.id)">
            <div class="entry-image-placeholder">
              <mat-icon>pie_chart</mat-icon>
            </div>
            <div class="match-snippets" *ngIf="!isExpanded(result.id)">
              <p *ngIf="result.matches.body" class="snippet" [innerHTML]="result.matches.body"></p>
              <p *ngIf="result.matches.tags" class="snippet" [innerHTML]="result.matches.tags"></p>
              <p *ngIf="result.matches.people" class="snippet" [innerHTML]="result.matches.people"></p>
            </div>
          </mat-card-content>

          <!-- Expanded Card View -->
          <div *ngIf="isExpanded(result.id)" class="expanded-details">
            <div class="expanded-header">
              <h3>"{{ result.title }}"</h3>
              <div class="expanded-actions">
                <a [routerLink]="['/', result.type, result.id]" mat-button color="primary">
                  VIEW ENTRY
                </a>
                <button mat-icon-button class="close-btn" (click)="closeExpanded($event)">
                  <mat-icon>close</mat-icon>
                </button>
              </div>
            </div>
            
            <div class="expanded-content">
              <p class="entry-date">{{ result.entry_date_display }}</p>
              <p *ngIf="result.matches.tags" class="tags" [innerHTML]="result.matches.tags"></p>
              <div class="content-matches">
                <p *ngIf="result.matches.body" class="match-quote">
                  "...<span [innerHTML]="result.matches.body"></span>..."
                </p>
                <p *ngIf="result.matches.ai" class="match-quote">
                  "...<span [innerHTML]="result.matches.ai"></span>..."
                </p>
              </div>
            </div>
          </div>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .search-results {
      padding: 1rem;
    }

    .loading-overlay {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1rem 0 2rem;
    }

    .error-card {
      margin: 1rem 0;
      background: #fff4f4;
      border: 1px solid #f1c0c0;
      color: #611;
    }

    .search-header {
      margin-bottom: 2rem;
    }

    .search-header h2 {
      font-size: 1.5rem;
      font-weight: 500;
      color: #333;
    }

    .results-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 1rem;
    }

    .entry-card {
      cursor: pointer;
      transition: all 0.3s ease;

      &.expanded {
        grid-column: 1 / -1;
      }

      .mat-mdc-card-header {
        padding: 16px 16px 0;
      }

      .mat-mdc-card-content {
        padding: 16px;
      }
    }

    .entry-image-placeholder {
      height: 150px;
      background: #f5f5f5;
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 1rem;
      border-radius: 4px;
      
      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: #ccc;
      }
    }

    .match-snippets {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }

    .snippet {
      margin: 0;
      font-size: 0.9rem;
      color: #495057;
      line-height: 1.4;

      ::ng-deep mark {
        background: none;
        color: #dc3545;
        font-weight: 500;
      }
    }

    /* Server may wrap matches in <span class="match">..</span> or <mark>..</mark> */
    ::ng-deep .match {
      color: #dc3545;
      font-weight: 500;
    }

    .expanded-details {
      padding: 0 16px 16px;
      border-top: 1px solid #dee2e6;
    }

    .expanded-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin: 1rem 0;

      h3 {
        margin: 0;
        font-size: 1.25rem;
        color: #212529;
      }
    }

    .expanded-actions {
      display: flex;
      gap: 0.5rem;
      align-items: center;
    }

    .expanded-content {
      .entry-date {
        color: #6c757d;
        font-size: 0.9rem;
        margin: 0.5rem 0;
      }

      .tags {
        margin: 1rem 0;
        ::ng-deep mark {
          background: none;
          color: #dc3545;
          font-weight: 500;
        }
      }

      .content-matches {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin-top: 1rem;
      }

      .match-quote {
        margin: 0;
        color: #495057;
        font-size: 0.95rem;
        line-height: 1.5;
        
        ::ng-deep mark {
          background: none;
          color: #dc3545;
          font-weight: 500;
        }
      }
    }

    ::ng-deep {
      .mat-mdc-card-title {
        font-size: 1.1rem !important;
      }

      .mat-mdc-card-subtitle {
        font-size: 0.9rem !important;
      }
    }
  `]
})
export class SearchResultsComponent {
  protected readonly searchService = inject(SearchService);
  protected readonly results$ = this.searchService.results$;
  private expandedId: number | null = null;

  toggleExpand(id: number): void {
    this.expandedId = this.expandedId === id ? null : id;
  }

  isExpanded(id: number): boolean {
    return this.expandedId === id;
  }

  closeExpanded(event: Event): void {
    event.stopPropagation();
    this.expandedId = null;
  }

  retry(state: SearchState): void {
    const filtersObj = {
      tags: state.filters.includes('tags'),
      date: state.filters.includes('date'),
      keywords: state.filters.includes('keywords'),
      people: state.filters.includes('people')
    };
    this.searchService.search(state.query, filtersObj).subscribe({
      next: () => {},
      error: () => {}
    });
  }
}