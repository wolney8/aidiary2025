import { Component, inject, ElementRef, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { SearchService, SearchResult, SearchState } from '../../../core/services/search.service';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { trigger, state, style, transition, animate } from '@angular/animations';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Subscription } from 'rxjs';

@Component({
  selector: 'app-search-results',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatPaginatorModule
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
        <h2 *ngIf="!searchState.loading && !searchState.error && searchState.results.length > 0">
          {{ getResultCountMessage(searchState) }}
        </h2>
        <h2 *ngIf="searchState.loading">
          Searching for "{{ searchState.query }}" in {{ searchState.filters_display }}...
        </h2>
      </div>

      <!-- Enhanced Loading State -->
      <div *ngIf="searchState.loading" class="loading-container">
        <!-- Skeleton Loading Cards -->
        <div class="skeleton-grid">
          <div *ngFor="let i of [1,2,3,4,5,6]" class="skeleton-card">
            <div class="skeleton-header">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-title-group">
                <div class="skeleton-title"></div>
                <div class="skeleton-subtitle"></div>
              </div>
            </div>
            <div class="skeleton-content">
              <div class="skeleton-image"></div>
              <div class="skeleton-text-lines">
                <div class="skeleton-line"></div>
                <div class="skeleton-line short"></div>
                <div class="skeleton-line medium"></div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Centered Loading Message (positioned like no-results card) -->
        <div class="loading-message-overlay">
          <mat-card class="loading-message-card">
            <mat-card-content class="loading-message-content">
              <mat-progress-spinner diameter="48" mode="indeterminate" color="primary"></mat-progress-spinner>
              <p class="loading-text">Searching your entries...</p>
            </mat-card-content>
          </mat-card>
        </div>
      </div>

      <!-- Enhanced Error Panel -->
      <mat-card *ngIf="searchState.error" class="error-card">
        <mat-card-content class="error-content">
          <div class="error-icon">
            <mat-icon>error_outline</mat-icon>
          </div>
          <h3>Search failed</h3>
          <p class="error-message">{{ getErrorMessage(searchState.error) }}</p>
          
          <!-- Error-specific suggestions -->
          <div class="error-suggestions" *ngIf="getErrorSuggestions(searchState.error).length > 0">
            <h4>Try these steps:</h4>
            <ul>
              <li *ngFor="let suggestion of getErrorSuggestions(searchState.error)">{{ suggestion }}</li>
            </ul>
          </div>
          
          <div class="error-actions">
            <button mat-raised-button color="primary" (click)="retry(searchState)" [disabled]="isRetrying">
              <mat-progress-spinner *ngIf="isRetrying" diameter="20" mode="indeterminate"></mat-progress-spinner>
              <span *ngIf="!isRetrying">Try Again</span>
              <span *ngIf="isRetrying">Retrying...</span>
            </button>
            <button mat-button (click)="searchService.clear()">Cancel</button>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- No Results State -->
      <mat-card *ngIf="!searchState.loading && !searchState.error && searchState.active && searchState.results.length === 0" 
                class="no-results-card">
        <mat-card-content class="no-results-content">
          <div class="no-results-icon">
            <mat-icon>search_off</mat-icon>
          </div>
          <h3>No results found</h3>
          <p class="no-results-message">
            We couldn't find any entries matching "<strong>{{ searchState.query }}</strong>" in {{ searchState.filters_display }}.
          </p>
          
          <!-- Smart Suggestions -->
          <div class="search-suggestions" *ngIf="getSearchSuggestions(searchState.query).length > 0">
            <h4>Try these suggestions:</h4>
            <ul>
              <li *ngFor="let suggestion of getSearchSuggestions(searchState.query)">{{ suggestion }}</li>
            </ul>
          </div>
          
          <div class="no-results-actions">
            <button mat-raised-button color="primary" (click)="browseAllEntries()">
              Browse All Entries
            </button>
          </div>
        </mat-card-content>
      </mat-card>
      
      <!-- Top Pagination (matching entries list exactly) -->
      <div class="pagination-container" 
           *ngIf="!searchState.loading && !searchState.error && searchState.active && searchState.results.length > 0">
        <mat-paginator
          [length]="searchState.results.length"
          [pageSize]="pageSize"
          [pageSizeOptions]="[8, 16, 32]"
          [pageIndex]="currentPage"
          [showFirstLastButtons]="true"
          (page)="onPageChange($event)"
          aria-label="Select page">
        </mat-paginator>
      </div>
      
      <div class="results-grid"
           *ngIf="!searchState.loading && !searchState.error && searchState.active && searchState.results.length > 0">
        <div *ngFor="let result of paginatedResults" class="result-container" [attr.data-card-id]="result.id">
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
                <p class="snippet" [innerHTML]="getSafeHtml(getBestSnippet(result))"></p>
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

      <!-- Bottom Pagination (matching entries list exactly) -->
      <div class="pagination-container" 
           *ngIf="!searchState.loading && !searchState.error && searchState.active && searchState.results.length > 0">
        <mat-paginator
          [length]="searchState.results.length"
          [pageSize]="pageSize"
          [pageSizeOptions]="[8, 16, 32]"
          [pageIndex]="currentPage"
          [showFirstLastButtons]="true"
          (page)="onPageChange($event)"
          aria-label="Select page">
        </mat-paginator>
      </div>
    </div>
  `,
  styles: [`
    .search-results {
      padding: 1rem;
    }

    .loading-container {
      position: relative;
      min-height: 400px;
    }

    /* Centered Loading Message Card - aligned with first row of results */
    .loading-message-overlay {
      position: absolute;
      top: 1rem; /* Align with skeleton-grid padding */
      left: 0;
      right: 0;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      z-index: 10;
      pointer-events: none; /* Allow interaction with skeleton cards underneath */
      padding-top: 2rem; /* Additional spacing to align with first card row */
    }

    .loading-message-card {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(8px);
      border: 1px solid #e0e0e0;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
      max-width: 400px;
      pointer-events: auto;
    }

    .loading-message-content {
      padding: 2rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 1rem;
      text-align: center;
    }

    .loading-text {
      margin: 0;
      color: #616161;
      font-size: 0.95rem;
      font-weight: 500;
    }

    /* Skeleton Loading Cards */
    .skeleton-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
      padding: 1rem;
      animation: fadeInSkeletons 0.5s ease-in-out;
    }

    .skeleton-card {
      background: white;
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      /* Match actual entry-card dimensions exactly: 303 x 350 */
      height: 350px;
      width: 303px;
      min-width: 303px;
      max-width: 303px;
      display: flex;
      flex-direction: column;
      opacity: 0.8;
      border: 1px solid #f0f0f0;
    }

    .skeleton-header {
      display: flex;
      align-items: center;
      margin-bottom: 16px;
      gap: 12px;
    }

    .skeleton-avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
    }

    .skeleton-title-group {
      flex: 1;
    }

    .skeleton-title {
      height: 16px;
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      border-radius: 4px;
      margin-bottom: 8px;
      width: 70%;
    }

    .skeleton-subtitle {
      height: 12px;
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      border-radius: 4px;
      width: 50%;
    }

    .skeleton-content {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    .skeleton-image {
      height: 120px; /* Match entry-image-placeholder height exactly */
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      border-radius: 8px;
      margin-bottom: 12px; /* Match entry-image-placeholder margin-bottom */
      flex-shrink: 0; /* Match entry-image-placeholder behavior */
    }

    .skeleton-text-lines {
      flex: 1; /* Match match-snippets flex behavior */
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 100px; /* Match match-snippets max-height */
      overflow: hidden;
      padding: 8px 0; /* Match match-snippets padding */
    }

    .skeleton-line {
      height: 14px;
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
      border-radius: 4px;
      width: 100%;
    }

    .skeleton-line.short {
      width: 60%;
    }

    .skeleton-line.medium {
      width: 80%;
    }

    @keyframes shimmer {
      0% {
        background-position: -200% 0;
      }
      100% {
        background-position: 200% 0;
      }
    }

    @keyframes fadeInSkeletons {
      from { 
        opacity: 0;
        transform: translateY(20px);
      }
      to { 
        opacity: 1;
        transform: translateY(0);
      }
    }

    .error-card {
      margin: 2rem auto;
      max-width: 500px;
      background: #fff8f8;
      border: 1px solid #ffcdd2;
      color: #c62828;
    }

    .error-content {
      padding: 2rem;
      text-align: center;
    }

    .error-icon {
      margin-bottom: 1rem;
    }

    .error-icon mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: #e57373;
    }

    .error-content h3 {
      margin: 0 0 1rem;
      font-size: 1.25rem;
      font-weight: 500;
      color: #c62828;
    }

    .error-message {
      margin: 0 0 1.5rem;
      color: #d32f2f;
      line-height: 1.5;
    }

    .error-suggestions {
      margin: 1.5rem 0;
      text-align: left;
      background: #ffebee;
      border-radius: 8px;
      padding: 1rem;
    }

    .error-suggestions h4 {
      margin: 0 0 0.5rem;
      font-size: 0.9rem;
      font-weight: 500;
      color: #c62828;
    }

    .error-suggestions ul {
      margin: 0;
      padding-left: 1.2rem;
      color: #d32f2f;
    }

    .error-suggestions li {
      margin-bottom: 0.25rem;
      font-size: 0.85rem;
    }

    .error-actions {
      display: flex;
      gap: 1rem;
      justify-content: center;
      flex-wrap: wrap;
    }

    .error-actions button {
      min-width: 120px;
    }

    .no-results-card {
      margin: 2rem auto;
      max-width: 500px;
      text-align: center;
      background: #fafafa;
      border: 1px solid #e0e0e0;
    }

    .no-results-content {
      padding: 3rem 2rem 2rem;
    }

    .no-results-icon {
      margin-bottom: 1.5rem;
    }

    .no-results-icon mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: #9e9e9e;
    }

    .no-results-content h3 {
      margin: 0 0 1rem;
      font-size: 1.5rem;
      font-weight: 500;
      color: #424242;
    }

    .no-results-message {
      margin: 0 0 2rem;
      color: #757575;
      line-height: 1.5;
    }

    .search-suggestions {
      margin: 2rem 0;
      text-align: left;
      background: #f5f5f5;
      border-radius: 8px;
      padding: 1.5rem;
    }

    .search-suggestions h4 {
      margin: 0 0 1rem;
      font-size: 1rem;
      font-weight: 500;
      color: #424242;
    }

    .search-suggestions ul {
      margin: 0;
      padding-left: 1.2rem;
      color: #616161;
    }

    .search-suggestions li {
      margin-bottom: 0.5rem;
    }

    .no-results-actions {
      display: flex;
      gap: 1rem;
      justify-content: center;
      flex-wrap: wrap;
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
      overflow: hidden; /* Prevent content overflow */
    }

    .entry-card:hover {
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
      transform: translateY(-2px);
    }

    .entry-image-placeholder {
      height: 120px; /* Reduced from 150px to give more space for text */
      background: #f5f5f5;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      margin-bottom: 12px;
      flex-shrink: 0; /* Don't shrink, maintain fixed height */

      mat-icon {
        font-size: 36px; /* Slightly smaller icon */
        width: 36px;
        height: 36px;
        color: #9e9e9e;
      }
    }
    .match-snippets {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      overflow: hidden; /* Prevent overflow from container */
      flex: 1; /* Take remaining space after image placeholder */
      max-height: 100px; /* Reduced since we only show one snippet now */
      padding: 8px 0; /* Add some vertical padding for better spacing */
    }

    .snippet {
      margin: 0;
      font-size: 0.9rem;
      color: #495057;
      line-height: 1.4;
      /* Text truncation for long snippets */
      overflow: hidden;
      text-overflow: ellipsis;
      display: -webkit-box;
      -webkit-line-clamp: 4; /* Increased to 4 lines since we only show one snippet */
      -webkit-box-orient: vertical;
      word-break: break-word; /* Handle long words */

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

    /* Pagination Styles - matching entries list exactly */
    .pagination-container {
      display: flex;
      justify-content: center;
      padding: 1rem 0;
      border-top: 1px solid #e0e0e0;
      background: #fafafa;
    }

    .pagination-container:first-of-type {
      border-top: none;
      border-bottom: 1px solid #e0e0e0;
      margin-bottom: 1rem;
    }

    .pagination-container:last-of-type {
      border-bottom: none;
      margin-top: 1rem;
    }

    .pagination-container mat-paginator {
      background: transparent;
    }

    /* Responsive pagination */
    @media (max-width: 768px) {
      .pagination-container {
        padding: 0.75rem 0;
      }
    }
  `]
})
export class SearchResultsComponent implements OnInit, OnDestroy {
  protected readonly searchService = inject(SearchService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly elementRef = inject(ElementRef);
  protected readonly results$ = this.searchService.results$;
  private expandedId: number | null = null;
  protected isRetrying = false;
  private searchSubscription?: Subscription;
  
  // Pagination properties matching entries list exactly
  protected pageSize = 8; // 2 rows of 4 cards - default from entries
  protected currentPage = 0;
  protected paginatedResults: SearchResult[] = [];

  ngOnInit(): void {
    // Subscribe to search state changes and update pagination
    this.searchSubscription = this.results$.subscribe(searchState => {
      console.log('Search results component received state:', searchState);
      if (searchState.results && searchState.results.length > 0) {
        // Reset to first page when new search results arrive
        // (We'll always reset pagination for new searches to avoid complexity)
        this.currentPage = 0;
        this.updatePaginatedResults(searchState);
      } else {
        this.paginatedResults = [];
      }
    });
  }

  ngOnDestroy(): void {
    this.searchSubscription?.unsubscribe();
  }

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

  getBestSnippet(result: SearchResult): string {
    // Prioritize: body match > tags match > people match
    // Return the most relevant single snippet to avoid visual clutter
    if (result.matches.body) {
      return this.truncateSnippet(result.matches.body);
    }
    if (result.matches.tags) {
      return this.truncateSnippet(result.matches.tags);
    }
    if (result.matches.people) {
      return this.truncateSnippet(result.matches.people);
    }
    
    // Fallback to a simple message if no matches found
    return 'No preview available';
  }

  private truncateSnippet(snippet: string): string {
    // Remove HTML tags temporarily to count actual text length
    const textOnly = snippet.replace(/<[^>]*>/g, '');
    
    // If the text is already short, return as-is
    if (textOnly.length <= 120) {
      return snippet;
    }
    
    // For longer text, try to truncate at word boundaries while preserving highlighting
    const maxLength = 100;
    let truncated = snippet;
    
    // Find a good truncation point near the highlighted term
    const matchIndex = snippet.toLowerCase().indexOf('<span');
    if (matchIndex > -1) {
      // Keep content around the match
      const beforeMatch = snippet.substring(0, matchIndex);
      const afterMatchStart = snippet.indexOf('</span>', matchIndex) + 7;
      const afterMatch = snippet.substring(afterMatchStart);
      
      // Truncate before and after the match
      const beforeTruncated = beforeMatch.length > 50 ? '...' + beforeMatch.substring(beforeMatch.length - 40) : beforeMatch;
      const afterTruncated = afterMatch.length > 50 ? afterMatch.substring(0, 40) + '...' : afterMatch;
      
      truncated = beforeTruncated + snippet.substring(matchIndex, afterMatchStart) + afterTruncated;
    } else {
      // No highlighting found, just truncate normally
      truncated = snippet.substring(0, maxLength) + (snippet.length > maxLength ? '...' : '');
    }
    
    return truncated;
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
    if (this.isRetrying) return; // Prevent multiple retry attempts
    
    this.isRetrying = true;
    const filtersObj = {
      tags: state.filters.includes('tags'),
      date: state.filters.includes('date'),
      keywords: state.filters.includes('keywords'),
      people: state.filters.includes('people')
    };
    
    this.searchService.search(state.query, filtersObj).subscribe({
      next: () => {
        this.isRetrying = false;
      },
      error: () => {
        this.isRetrying = false;
      },
      complete: () => {
        this.isRetrying = false;
      }
    });
  }

  getErrorMessage(error: string): string {
    // Parse common error types and provide user-friendly messages
    if (error.toLowerCase().includes('network') || error.toLowerCase().includes('connection')) {
      return 'Unable to connect to the server. Please check your internet connection.';
    }
    if (error.toLowerCase().includes('timeout')) {
      return 'Search request timed out. The server may be busy or your connection is slow.';
    }
    if (error.toLowerCase().includes('server') || error.includes('500')) {
      return 'The search service is temporarily unavailable. Please try again in a moment.';
    }
    if (error.toLowerCase().includes('unauthorized') || error.includes('401')) {
      return 'Your session has expired. Please refresh the page and log in again.';
    }
    
    // Generic error message for unknown errors
    return 'Something went wrong while searching. Please try again.';
  }

  getErrorSuggestions(error: string): string[] {
    const suggestions: string[] = [];
    
    if (error.toLowerCase().includes('network') || error.toLowerCase().includes('connection')) {
      suggestions.push('Check your internet connection');
      suggestions.push('Try refreshing the page');
      suggestions.push('Contact support if the issue persists');
    } else if (error.toLowerCase().includes('timeout')) {
      suggestions.push('Try a simpler search term');
      suggestions.push('Check your internet speed');
      suggestions.push('Wait a moment and try again');
    } else if (error.toLowerCase().includes('server') || error.includes('500')) {
      suggestions.push('Wait a few minutes and try again');
      suggestions.push('Try a different search term');
      suggestions.push('Contact support if the issue continues');
    } else if (error.toLowerCase().includes('unauthorized') || error.includes('401')) {
      suggestions.push('Refresh the page and log in again');
      suggestions.push('Clear your browser cache');
    } else {
      // Generic suggestions
      suggestions.push('Try refreshing the page');
      suggestions.push('Check your internet connection');
      suggestions.push('Try a different search term');
    }
    
    return suggestions.slice(0, 3); // Limit to 3 suggestions
  }

  clearSearch(): void {
    this.searchService.clear();
  }

  browseAllEntries(): void {
    // Clear the search first
    this.searchService.clear();
    // Navigate to entries (latest entries will be shown by default)
    // The entries list component should handle showing latest entries
    window.location.href = '/entries';
  }

  getSearchSuggestions(query: string): string[] {
    const suggestions: string[] = [];
    
    // Basic suggestions based on query characteristics
    if (query.length > 0) {
      // Check if query looks like a person's name (capitalized)
      if (query.charAt(0) === query.charAt(0).toUpperCase() && !query.includes(' ')) {
        suggestions.push(`Try variations like "${query.toLowerCase()}" or nicknames`);
        suggestions.push('Search for the full name if you used a nickname');
      }
      
      // Always show comprehensive search tips
      suggestions.push('Try searching for a date (e.g., "26th August", "October 2023")');
      suggestions.push('Search for keywords, places, or emotions from your entries');
      suggestions.push('Try tags or people names mentioned in your diary');
      suggestions.push('Check your spelling and try fewer keywords');
    }
    
    // Limit to 4 suggestions max for clean UI
    return suggestions.slice(0, 4);
  }

  getResultCountMessage(searchState: SearchState): string {
    const count = searchState.results.length;
    const query = searchState.query;
    const context = searchState.filters_display;
    
    if (count === 0) {
      return `No results found for "${query}" in ${context}`;
    } else if (count === 1) {
      return `About 1 result for "${query}" in ${context}`;
    } else {
      return `About ${count} results for "${query}" in ${context}`;
    }
  }

  // Pagination Methods - Matching entries list exactly
  
  onPageChange(event: PageEvent): void {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.updatePaginatedResults();
  }

  updatePaginatedResults(searchState?: SearchState): void {
    // Use current search state or get it from the service
    const currentState = searchState || this.searchService.getCurrentSearchState();
    
    if (currentState && currentState.results && currentState.results.length > 0) {
      const startIndex = this.currentPage * this.pageSize;
      const endIndex = startIndex + this.pageSize;
      this.paginatedResults = currentState.results.slice(startIndex, endIndex);
    } else {
      this.paginatedResults = [];
    }
  }

  // Reset pagination when new search performed
  resetPagination(): void {
    this.currentPage = 0;
    this.updatePaginatedResults();
  }
}