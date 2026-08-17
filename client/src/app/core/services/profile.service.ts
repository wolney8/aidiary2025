// Service for profile retrieval and updates
import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { User } from '../models/user.model';
import { AuthService } from './auth.service';
import { environment } from '../../../environments/environment';

export interface ProfileMediaAsset {
  id: number;
  entry_type: 'daily' | 'dream';
  entry_id: number;
  entry_title: string;
  entry_date: string;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  url: string | null;
}

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

  uploadProfilePicture(file: File): Observable<{ message: string; user: User }> {
    const formData = new FormData();
    formData.append('image', file);
    const token = this.authService.getToken();
    const headers = token
      ? new HttpHeaders({ Authorization: `Bearer ${token}` })
      : undefined;

    return this.http.post<{ message: string; user: User }>(
      `${this.apiUrl}/profile/picture`,
      formData,
      { headers },
    ).pipe(
      tap((response) => this.authService.syncCurrentUser(response.user)),
    );
  }

  deleteProfilePicture(): Observable<{ message: string; user: User }> {
    return this.http.delete<{ message: string; user: User }>(
      `${this.apiUrl}/profile/picture`,
      { headers: this.buildHeaders() },
    ).pipe(
      tap((response) => this.authService.syncCurrentUser(response.user)),
    );
  }

  getMediaAssets(limit = 25): Observable<{ assets: ProfileMediaAsset[] }> {
    return this.http.get<{ assets: ProfileMediaAsset[] }>(
      `${this.apiUrl}/profile/media-assets?limit=${limit}`,
      { headers: this.buildHeaders() },
    );
  }

  deleteMediaAsset(assetId: number): Observable<{
    message: string;
    deleted_asset_id: number;
  }> {
    return this.http.delete<{
      message: string;
      deleted_asset_id: number;
    }>(
      `${this.apiUrl}/profile/media-assets/${assetId}`,
      { headers: this.buildHeaders() },
    );
  }

  deleteAccount(payload: {
    password?: string;
    confirmation: string;
  }): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(
      `${this.apiUrl}/profile/account`,
      {
        headers: this.buildHeaders(),
        body: payload,
      },
    );
  }
}
