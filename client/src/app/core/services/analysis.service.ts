// Service for AI analysis
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { AnalysisRequest, DailyAnalysisResponse, DreamAnalysisResponse } from '../models/entry.model';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class AnalysisService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = 'http://localhost:5001/api';
  
  analyseText(request: AnalysisRequest): Observable<DailyAnalysisResponse | DreamAnalysisResponse> {
    const token = this.authService.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    });
    
    if (!token) {
      return throwError(() => new Error('User not authenticated'));
    }

    return this.http.post<DailyAnalysisResponse | DreamAnalysisResponse>(
      `${this.apiUrl}/analyse`,
      request,
      { headers }
    );
  }
}
