// Service for diary entries CRUD operations
import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Observable, of, throwError } from "rxjs";
import {
  DailyEntry,
  DreamEntry,
} from "../models/entry.model";
import { AuthService } from "./auth.service";

@Injectable({
  providedIn: "root",
})
export class EntriesService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = "http://localhost:5001/api";

  private getHeaders(includeJsonContentType = true): HttpHeaders {
    const headers: Record<string, string> = {
    };

    if (includeJsonContentType) {
      headers["Content-Type"] = "application/json";
    }

    const token = this.authService.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return new HttpHeaders(headers);
  }

  // Daily entries
  getDailyEntries(): Observable<DailyEntry[]> {
    if (!this.authService.isAuthenticated()) {
      return of([]);
    }

    return this.http.get<DailyEntry[]>(`${this.apiUrl}/daily`, {
      headers: this.getHeaders(),
    });
  }

  getDailyEntry(id: number): Observable<DailyEntry> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.get<DailyEntry>(`${this.apiUrl}/daily/${id}`, {
      headers: this.getHeaders(),
    });
  }

  createDailyEntry(entry: DailyEntry): Observable<DailyEntry> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.post<DailyEntry>(`${this.apiUrl}/daily`, entry, {
      headers: this.getHeaders(),
    });
  }

  updateDailyEntry(
    id: number,
    entry: Partial<DailyEntry>,
  ): Observable<DailyEntry> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.put<DailyEntry>(`${this.apiUrl}/daily/${id}`, entry, {
      headers: this.getHeaders(),
    });
  }

  deleteDailyEntry(id: number): Observable<void> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.delete<void>(`${this.apiUrl}/daily/${id}`, {
      headers: this.getHeaders(),
    });
  }

  generateDailyImage(
    id: number,
    imagePromptOverride?: string,
  ): Observable<{
    id: number;
    image_prompt: string;
    image_url: string;
    image_source?: string | null;
    recycled_image_prompt?: string;
    image_position_x?: number;
    image_position_y?: number;
  }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.post<{
      id: number;
      image_prompt: string;
      image_url: string;
      image_source?: string | null;
      recycled_image_prompt?: string;
      image_position_x?: number;
      image_position_y?: number;
    }>(
      `${this.apiUrl}/daily/${id}/generate-image`,
      imagePromptOverride?.trim()
        ? { image_prompt_override: imagePromptOverride.trim() }
        : {},
      { headers: this.getHeaders() },
    );
  }

  uploadDailyImage(
    id: number,
    file: File,
  ): Observable<{
    id: number;
    image_prompt: string;
    image_url: string;
    image_source?: string | null;
    recycled_image_prompt?: string;
    image_position_x?: number;
    image_position_y?: number;
  }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    const formData = new FormData();
    formData.append("image", file);

    return this.http.post<{
      id: number;
      image_prompt: string;
      image_url: string;
      image_source?: string | null;
      recycled_image_prompt?: string;
      image_position_x?: number;
      image_position_y?: number;
    }>(
      `${this.apiUrl}/daily/${id}/image`,
      formData,
      { headers: this.getHeaders(false) },
    );
  }

  deleteDailyImage(
    id: number,
  ): Observable<{
    id: number;
    image_prompt: string;
    image_url: string | null;
    image_source?: string | null;
    recycled_image_prompt?: string;
    image_position_x?: number;
    image_position_y?: number;
  }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.delete<{
      id: number;
      image_prompt: string;
      image_url: string | null;
      image_source?: string | null;
      recycled_image_prompt?: string;
      image_position_x?: number;
      image_position_y?: number;
    }>(
      `${this.apiUrl}/daily/${id}/image`,
      { headers: this.getHeaders(false) },
    );
  }

  // Dream entries
  getDreamEntries(): Observable<DreamEntry[]> {
    if (!this.authService.isAuthenticated()) {
      return of([]);
    }

    return this.http.get<DreamEntry[]>(`${this.apiUrl}/dreams`, {
      headers: this.getHeaders(),
    });
  }

  getDreamEntry(id: number): Observable<DreamEntry> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.get<DreamEntry>(`${this.apiUrl}/dreams/${id}`, {
      headers: this.getHeaders(),
    });
  }

  createDreamEntry(entry: DreamEntry): Observable<DreamEntry> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.post<DreamEntry>(`${this.apiUrl}/dreams`, entry, {
      headers: this.getHeaders(),
    });
  }

  updateDreamEntry(
    id: number,
    entry: Partial<DreamEntry>,
  ): Observable<DreamEntry> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.put<DreamEntry>(`${this.apiUrl}/dreams/${id}`, entry, {
      headers: this.getHeaders(),
    });
  }

  deleteDreamEntry(id: number): Observable<void> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.delete<void>(`${this.apiUrl}/dreams/${id}`, {
      headers: this.getHeaders(),
    });
  }

  generateDreamImage(
    id: number,
    imagePromptOverride?: string,
  ): Observable<{
    id: number;
    image_prompt: string;
    image_url: string;
    image_source?: string | null;
    recycled_image_prompt?: string;
    image_position_x?: number;
    image_position_y?: number;
  }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.post<{
      id: number;
      image_prompt: string;
      image_url: string;
      image_source?: string | null;
      recycled_image_prompt?: string;
      image_position_x?: number;
      image_position_y?: number;
    }>(
      `${this.apiUrl}/dreams/${id}/generate-image`,
      imagePromptOverride?.trim()
        ? { image_prompt_override: imagePromptOverride.trim() }
        : {},
      { headers: this.getHeaders() },
    );
  }

  uploadDreamImage(
    id: number,
    file: File,
  ): Observable<{
    id: number;
    image_prompt: string;
    image_url: string;
    image_source?: string | null;
    recycled_image_prompt?: string;
    image_position_x?: number;
    image_position_y?: number;
  }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    const formData = new FormData();
    formData.append("image", file);

    return this.http.post<{
      id: number;
      image_prompt: string;
      image_url: string;
      image_source?: string | null;
      recycled_image_prompt?: string;
      image_position_x?: number;
      image_position_y?: number;
    }>(
      `${this.apiUrl}/dreams/${id}/image`,
      formData,
      { headers: this.getHeaders(false) },
    );
  }

  deleteDreamImage(
    id: number,
  ): Observable<{
    id: number;
    image_prompt: string;
    image_url: string | null;
    image_source?: string | null;
    recycled_image_prompt?: string;
    image_position_x?: number;
    image_position_y?: number;
  }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.delete<{
      id: number;
      image_prompt: string;
      image_url: string | null;
      image_source?: string | null;
      recycled_image_prompt?: string;
      image_position_x?: number;
      image_position_y?: number;
    }>(
      `${this.apiUrl}/dreams/${id}/image`,
      { headers: this.getHeaders(false) },
    );
  }
}
