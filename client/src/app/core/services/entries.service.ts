// Service for diary entries CRUD operations
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { DailyEntry, DreamEntry } from '../models/entry.model';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class EntriesService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = 'http://localhost:5001/api';
  
  private getHeaders(): HttpHeaders {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };

    const token = this.authService.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return new HttpHeaders(headers);
  }
  
  // Daily entries
  getDailyEntries(): Observable<DailyEntry[]> {
    return this.http.get<DailyEntry[]>(`${this.apiUrl}/daily`, {
      headers: this.getHeaders()
    });
  }
  
  getDailyEntry(id: number): Observable<DailyEntry> {
    return this.http.get<DailyEntry>(`${this.apiUrl}/daily/${id}`, {
      headers: this.getHeaders()
    });
  }
  
  createDailyEntry(entry: DailyEntry): Observable<DailyEntry> {
    return this.http.post<DailyEntry>(`${this.apiUrl}/daily`, entry, {
      headers: this.getHeaders()
    });
  }
  
  updateDailyEntry(id: number, entry: Partial<DailyEntry>): Observable<DailyEntry> {
    return this.http.put<DailyEntry>(`${this.apiUrl}/daily/${id}`, entry, {
      headers: this.getHeaders()
    });
  }
  
  deleteDailyEntry(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/daily/${id}`, {
      headers: this.getHeaders()
    });
  }
  
  // Dream entries
  getDreamEntries(): Observable<DreamEntry[]> {
    return this.http.get<DreamEntry[]>(`${this.apiUrl}/dreams`, {
      headers: this.getHeaders()
    });
  }
  
  getDreamEntry(id: number): Observable<DreamEntry> {
    return this.http.get<DreamEntry>(`${this.apiUrl}/dreams/${id}`, {
      headers: this.getHeaders()
    });
  }
  
  createDreamEntry(entry: DreamEntry): Observable<DreamEntry> {
    return this.http.post<DreamEntry>(`${this.apiUrl}/dreams`, entry, {
      headers: this.getHeaders()
    });
  }
  
  updateDreamEntry(id: number, entry: Partial<DreamEntry>): Observable<DreamEntry> {
    return this.http.put<DreamEntry>(`${this.apiUrl}/dreams/${id}`, entry, {
      headers: this.getHeaders()
    });
  }
  
  deleteDreamEntry(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/dreams/${id}`, {
      headers: this.getHeaders()
    });
  }
}
