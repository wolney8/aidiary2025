import { Component, inject, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SearchService, SearchResult, SearchState } from '../../../core/services/search.service';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { trigger, state, style, transition, animate } from '@angular/animations';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

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
  animations: [
    trigger('slideInOut', [
      transition(':enter', [
        style({ height: '0', opacity: '0', transform: 'translateY(-10px)' }),
        animate('300ms cubic-bezier(0.4, 0.0, 0.2, 1)', 
                style({ height: '*', opacity: '1', transform: 'translateY(0)' }))
      ]),
      transition(':leave', [
        animate('300ms cubic-bezier(0.4, 0.0, 0.2, 1)', 
                style({ height: '0', opacity: '0', transform: 'translateY(-10px)' }))
      ])
    ])
  ],
  template: `
    <div *ngIf="results$ | async as searchState" class="search-results" (click)="closeExpandedIfClickingAway($event)">
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
        <div *ngFor="let result of searchState.results" class="result-container" [attr.data-card-id]="result.id">
          <!-- Main Card View (Fixed Size) -->
          <mat-card class="entry-card" (click)="toggleExpand(result.id); $event.stopPropagation()">
            <mat-card-header>
              <mat-icon mat-card-avatar>
                {{ result.type === 'dream' ? 'nights_stay' : 'book' }}
              </mat-icon>
              <mat-card-title [innerHTML]="getDisplayTitle(result)"></mat-card-title>
              <mat-card-subtitle>{{ result.entry_date_display }}</mat-card-subtitle>
            </mat-card-header>
            
            <mat-card-content>
              <div class="entry-image-placeholder">
                <mat-icon>pie_chart</mat-icon>
              </div>
              <div class="match-snippets">
                <p *ngIf="result.matches.body" class="snippet" [innerHTML]="getSafeHtml(result.matches.body)"></p>
                <p *ngIf="result.matches.tags" class="snippet" [innerHTML]="getSafeHtml(result.matches.tags)"></p>
                <p *ngIf="result.matches.people" class="snippet" [innerHTML]="getSafeHtml(result.matches.people)"></p>
              </div>
            </mat-card-content>
          </mat-card>

          <!-- Expanded Details Card (Separate Card Below) -->
          <div *ngIf="isExpanded(result.id)" class="expanded-connector">
            <!-- Visual connector arrow -->
            <div class="connector-arrow">
              <mat-icon>keyboard_arrow_down</mat-icon>
            </div>
          </div>
          
          <mat-card *ngIf="isExpanded(result.id)" 
                    class="expanded-details-card"
                    [@slideInOut]
                    (click)="$event.stopPropagation()">
            <div class="expanded-header">
              <div class="expanded-actions">
                <a [routerLink]="['/entries', result.id]" mat-button color="primary">
                  VIEW ENTRY
                </a>
                <button mat-icon-button class="close-btn" (click)="closeExpanded($event)">
                  <mat-icon>close</mat-icon>
                </button>
              </div>
            </div>
            
            <div class="expanded-content">
              <!-- Title Row -->
              <div class="detail-row">
                <mat-icon class="detail-icon">bookmark</mat-icon>
                <span class="detail-text" [innerHTML]="getDisplayTitle(result)"></span>
              </div>
              
              <!-- Date Row -->
              <div class="detail-row">
                <mat-icon class="detail-icon">calendar_today</mat-icon>
                <span class="detail-text">{{ result.entry_date_display }}</span>
              </div>
              
              <!-- Tags Row (if has matching tags) -->
              <div class="detail-row" *ngIf="result.matches.tags">
                <mat-icon class="detail-icon">local_offer</mat-icon>
                <span class="detail-text" [innerHTML]="getSafeHtml(result.matches.tags)"></span>
              </div>
              
              <!-- Body/Content Row (if has matching body) -->
              <div class="detail-row" *ngIf="result.matches.body">
                <mat-icon class="detail-icon">edit</mat-icon>
                <span class="detail-text" [innerHTML]="getSafeHtml(result.matches.body)"></span>
              </div>
              
              <!-- AI Response Row (if has matching AI response) -->
              <div class="detail-row" *ngIf="result.matches.ai">
                <mat-icon class="detail-icon">psychology</mat-icon>
                <span class="detail-text" [innerHTML]="getSafeHtml(result.matches.ai)"></span>
              </div>
            </div>
          </mat-card>
        </div>
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
      gap: 16px;
      position: relative; /* Allow expanded cards to position relative to grid */
    }

    .result-container {
      display: flex;
      flex-direction: column;
      gap: 8px;
      position: relative; /* Allow for absolute positioning of expanded cards */
    }

    .result-container:has(.expanded-details-card) {
      /* Ensure expanded cards have proper stacking context */
      z-index: 1;
      /* Add extra bottom margin to prevent other cards from creeping up */
      margin-bottom: 32px;
    }

    /* Visual connector between main card and expanded card */
    .expanded-connector {
      display: flex;
      justify-content: flex-start; /* Align to left as per wireframe */
      padding-left: 60px; /* Off-center to the left */
      margin: 4px 0;
      z-index: 15;
      position: relative;
    }

    .connector-arrow {
      background-color: #007bff;
      color: white;
      border-radius: 50%;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0, 123, 255, 0.3);
    }

    .connector-arrow mat-icon {
      font-size: 20px;
      width: 20px;
      height: 20px;
    }

    .entry-card {
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
      transform: translateZ(0);
      width: 100%;
      min-width: 300px;
      max-width: 350px;
    }

    /* When expanded, make the expanded card appear below and span wider */
    .expanded-details-card {
      background-color: #f8f9fa;
      border-left: 4px solid #007bff;
      overflow: hidden;
      /* Use CSS custom properties for dynamic sizing and positioning */
      width: var(--expanded-width, min(900px, 90vw));
      max-width: none; /* Allow custom width to take precedence */
      margin: 0; /* Remove default margin since we have connector spacing */
      /* Position using CSS custom properties */
      transform: translateX(var(--offset-x, 0px));
      /* Ensure it appears above other content */
      z-index: 20;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
      border-radius: 8px;
      transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
      /* Position relative to maintain document flow */
      position: relative;
      /* Ensure it doesn't get cut off */
      overflow: visible;
    }

    /* Make sure expanded cards push down subsequent content more */
    .result-container:has(.expanded-details-card) ~ .result-container {
      margin-top: 24px; /* Increased spacing */
    }

    /* Ensure other cards don't creep into expanded area */
    .result-container:has(.expanded-details-card) {
      /* Create a clear boundary around expanded content */
      padding-bottom: 16px;
      border-bottom: 1px solid transparent; /* Invisible spacer */
    }

    /* Ensure search result cards also have consistent heights */
    .entry-card {
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
      transform: translateZ(0);
      width: 100%;
      min-width: 300px;
      max-width: 350px;
      /* Force consistent height for search result cards too */
      height: 350px;
      display: flex;
      flex-direction: column;
    }

    /* Highlight the selected/expanded card */
    .result-container:has(.expanded-details-card) .entry-card {
      border: 2px solid #007bff;
      box-shadow: 0 4px 20px rgba(0, 123, 255, 0.15);
    }

    /* Ensure search result card content fills properly */
    .entry-card .mat-mdc-card-content {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .entry-card:hover {
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
      transform: translateY(-2px);
    }

    .entry-image-placeholder {
      height: 150px;
      background: #f5f5f5;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      margin-bottom: 12px;

      mat-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: #9e9e9e;
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

    .expanded-header {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #e9ecef;
    }

    .expanded-content {
      padding: 16px;
    }

    .detail-row {
      display: flex;
      align-items: flex-start;
      margin-bottom: 16px;
      padding: 8px 0;
      transition: background-color 0.2s ease;
    }

    .detail-row:last-child {
      margin-bottom: 0;
    }

    .detail-row:hover {
      background-color: rgba(0, 123, 255, 0.05);
      border-radius: 8px;
      margin: 0 -8px 16px -8px;
      padding: 8px;
    }

    .detail-icon {
      flex-shrink: 0;
      width: 24px;
      height: 24px;
      margin-right: 16px;
      color: #6c757d;
      font-size: 20px !important;
    }

    .detail-text {
      flex: 1;
      font-size: 0.9rem;
      line-height: 1.5;
      color: #495057;
      word-wrap: break-word;
    }

    .expanded-actions {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .close-btn {
      color: #6c757d;
      transition: color 0.2s ease;
    }

    .close-btn:hover {
      color: #495057;
    }
  `]
})
export class SearchResultsComponent {
  protected readonly searchService = inject(SearchService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly elementRef = inject(ElementRef);
  protected readonly results$ = this.searchService.results$;
  private expandedId: number | null = null;

  toggleExpand(id: number): void {
    // Clean up any previously expanded cards
    this.cleanupPreviousExpanded();
    
    this.expandedId = this.expandedId === id ? null : id;
    
    // If expanding, scroll the card into view after a short delay for animation
    if (this.expandedId !== null) {
      setTimeout(() => this.scrollToCard(id), 300);
    }
  }

  private cleanupPreviousExpanded(): void {
    // Remove positioning classes and styles from all expanded cards
    const expandedCards = this.elementRef.nativeElement.querySelectorAll('.expanded-details-card');
    expandedCards.forEach((card: HTMLElement) => {
      card.classList.remove('align-left', 'align-right');
      card.style.removeProperty('--offset-x');
      card.style.removeProperty('--expanded-width');
    });
    
    // Also clean up connector positioning if needed
    const connectors = this.elementRef.nativeElement.querySelectorAll('.expanded-connector');
    connectors.forEach((connector: HTMLElement) => {
      connector.style.removeProperty('--connector-offset');
    });
  }

  private scrollToCard(id: number): void {
    const cardElement = this.elementRef.nativeElement.querySelector(`[data-card-id="${id}"]`);
    if (cardElement) {
      setTimeout(() => {
        // Get the grid container and its bounds
        const gridContainer = this.elementRef.nativeElement.querySelector('.results-grid');
        const expandedCard = cardElement.querySelector('.expanded-details-card');
        
        if (expandedCard && gridContainer) {
          const gridRect = gridContainer.getBoundingClientRect();
          const cardRect = cardElement.getBoundingClientRect();
          
          // Calculate position relative to grid
          const cardPositionInGrid = cardRect.left - gridRect.left;
          const gridWidth = gridRect.width;
          const expandedWidth = Math.min(900, gridWidth * 0.9); // 90% of grid width max
          
          // Check if card is in right half of grid
          const isRightSide = cardPositionInGrid > gridWidth / 2;
          
          // Calculate optimal position
          let leftOffset = 0;
          if (isRightSide) {
            // Position so right edge aligns with grid right edge
            leftOffset = gridWidth - expandedWidth - cardPositionInGrid;
          } else {
            // Position so left edge aligns with grid left edge
            leftOffset = -cardPositionInGrid;
          }
          
          // Apply the positioning
          expandedCard.style.setProperty('--offset-x', `${leftOffset}px`);
          expandedCard.style.setProperty('--expanded-width', `${expandedWidth}px`);
          
          if (isRightSide) {
            expandedCard.classList.add('align-right');
          } else {
            expandedCard.classList.add('align-left');
          }
        }
        
        // Scroll into view
        cardElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
          inline: 'nearest'
        });
      }, 50); // Small delay to ensure DOM is updated
    }
  }

  isExpanded(id: number): boolean {
    return this.expandedId === id;
  }

  getDisplayTitle(result: SearchResult): SafeHtml {
    // Use highlighted title if available, otherwise plain title
    const highlighted = result.matches?.title || result.title_highlight || result.title;
    return this.sanitizer.bypassSecurityTrustHtml(highlighted);
  }

  getSafeHtml(content: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(content);
  }

  closeExpanded(event: Event): void {
    event.stopPropagation();
    this.expandedId = null;
  }

  closeExpandedIfClickingAway(event: Event): void {
    // Only close if we have an expanded card and the click wasn't on a card
    if (this.expandedId !== null) {
      this.expandedId = null;
    }
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