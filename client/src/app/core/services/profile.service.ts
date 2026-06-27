// Service for profile retrieval and updates
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { User } from '../models/user.model';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ProfileService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiBaseUrl;

  private buildHeaders(): HttpHeaders {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };

    const token = this.authService.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return new HttpHeaders(headers);
  }

  getProfile(): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/profile`, {
      headers: this.buildHeaders()
    }).pipe(
      tap((user) => this.authService.syncCurrentUser(user))
    );
  }

  updateProfile(payload: Partial<User>): Observable<{ message: string; user: User }> {
    return this.http.put<{ message: string; user: User }>(`${this.apiUrl}/profile`, payload, {
      headers: this.buildHeaders()
    }).pipe(
      tap((response) => this.authService.syncCurrentUser(response.user))
    );
  }
}
