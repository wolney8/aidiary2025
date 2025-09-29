import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams, HttpHeaders } from '@angular/common/http';
import { AuthService } from './auth.service';
import { BehaviorSubject, Observable, tap, catchError, timeout, TimeoutError } from 'rxjs';

export interface SearchMatches {
  title?: string;
  body?: string;
  tags?: string;
  people?: string;
  ai?: string;
  date?: string;
}

export interface SearchResult {
  id: number;
  type: 'daily' | 'dream';
  title: string;
  title_highlight: string;
  entry_date: string;
  entry_date_display: string;
  tags: string;
  matches: SearchMatches;
}

export interface SearchResponse {
  query: string;
  filters: string[];
  filters_display: string;
  results: SearchResult[];
}

export interface SearchState extends SearchResponse {
  active: boolean;
  loading?: boolean;
  error?: string;
}

export interface SearchFilters {
  tags: boolean;
  date: boolean;
  keywords: boolean;
  people: boolean;
}

@Injectable({ providedIn: 'root' })
export class SearchService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = 'http://localhost:5001/api/search';
  private resultsSubject = new BehaviorSubject<SearchState>({
    query: '',
    filters: [],
    filters_display: 'All Entries',
    results: [],
    active: false,
    loading: false
  });

  results$ = this.resultsSubject.asObservable();
  
  // Search History Management (Session Storage)
  private readonly MAX_HISTORY_SIZE = 6;
  private readonly HISTORY_KEY = 'search-history';
  private searchHistorySubject = new BehaviorSubject<string[]>(this.loadSearchHistory());
  
  searchHistory$ = this.searchHistorySubject.asObservable();

  search(query: string, filters?: SearchFilters): Observable<SearchResponse> {
    if (!query.trim()) {
      this.clear();
      return new Observable(subscriber => subscriber.complete());
    }

    const filtersArray: string[] = [];
    if (filters) {
      if (filters.tags) filtersArray.push('tags');
      if (filters.date) filtersArray.push('date');
      if (filters.keywords) filtersArray.push('keywords');
      if (filters.people) filtersArray.push('people');
    }

    const filtersDisplay = filtersArray.length > 0 ? filtersArray.join(', ') : 'All Entries';

    // Immediately set active state so the UI switches to search results (shows loading)
    this.resultsSubject.next({
      ...this.resultsSubject.getValue(),
      query: query.trim(),
      filters: filtersArray,
      filters_display: filtersDisplay,
      active: true,
      loading: true,
      error: undefined
    });

    let params = new HttpParams().set('q', query.trim());
    if (filtersArray.length > 0) {
      params = params.set('filters', filtersArray.join(','));
    }

  const token = this.authService.getToken();
  const headers = token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : undefined;

  return this.http.get<SearchResponse>(this.apiUrl, { params, headers }).pipe(
      timeout(8000), // 8 second timeout (Google UX standard for search)
      tap(response => {
        // Add to search history on successful search
        this.addToHistory(query.trim());
        
        this.resultsSubject.next({ 
          ...response, 
          active: true,
          loading: false,
          error: undefined
        });
      }),
      catchError(error => {
        let errorMessage: string;
        
        if (error instanceof TimeoutError) {
          errorMessage = 'Search request timed out. Please try again.';
        } else if (error.status === 0) {
          errorMessage = 'Network connection error. Please check your internet connection.';
        } else if (error.status >= 500) {
          errorMessage = 'Server error. Please try again in a moment.';
        } else if (error.status === 401) {
          errorMessage = 'Authentication error. Please refresh and log in again.';
        } else {
          errorMessage = error.error?.message || 'Search failed. Please try again.';
        }
          
        this.resultsSubject.next({
          ...this.resultsSubject.getValue(),
          loading: false,
          error: errorMessage
        });
        
        throw error;
      })
    );
  }

  clear(): void {
    this.resultsSubject.next({
      query: '',
      filters: [],
      filters_display: 'All Entries',
      results: [],
      active: false,
      loading: false,
      error: undefined
    });
  }

  getCurrentSearchState(): SearchState {
    return this.resultsSubject.getValue();
  }

  // Search History Methods
  private loadSearchHistory(): string[] {
    try {
      const history = sessionStorage.getItem(this.HISTORY_KEY);
      return history ? JSON.parse(history) : [];
    } catch {
      return [];
    }
  }

  private saveSearchHistory(history: string[]): void {
    try {
      sessionStorage.setItem(this.HISTORY_KEY, JSON.stringify(history));
      this.searchHistorySubject.next(history);
    } catch {
      // Silently fail if storage is unavailable
    }
  }

  addToHistory(query: string): void {
    if (!query.trim()) return;
    
    const currentHistory = this.loadSearchHistory();
    const trimmedQuery = query.trim();
    
    // Remove if already exists (move to front)
    const filteredHistory = currentHistory.filter(item => item !== trimmedQuery);
    
    // Add to front and limit size
    const newHistory = [trimmedQuery, ...filteredHistory].slice(0, this.MAX_HISTORY_SIZE);
    
    this.saveSearchHistory(newHistory);
  }

  removeFromHistory(query: string): void {
    const currentHistory = this.loadSearchHistory();
    const newHistory = currentHistory.filter(item => item !== query);
    this.saveSearchHistory(newHistory);
  }

  clearHistory(): void {
    this.saveSearchHistory([]);
  }

  getSearchHistory(): string[] {
    return this.loadSearchHistory();
  }
}
