import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams, HttpHeaders } from '@angular/common/http';
import { AuthService } from './auth.service';
import { BehaviorSubject, Observable, tap, catchError } from 'rxjs';

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
      tap(response => {
        this.resultsSubject.next({ 
          ...response, 
          active: true,
          loading: false,
          error: undefined
        });
      }),
      catchError(error => {
        const errorMessage = error.status === 0 
          ? 'Could not connect to search service'
          : error.error?.message || 'Error performing search';
          
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
}
