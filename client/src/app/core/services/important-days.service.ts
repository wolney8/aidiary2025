import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Observable, throwError } from "rxjs";
import {
  ImportantDay,
  ImportantDayPayload,
} from "../models/important-day.model";
import { AuthService } from "./auth.service";

@Injectable({
  providedIn: "root",
})
export class ImportantDaysService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = "http://localhost:5001/api";

  private buildHeaders(): HttpHeaders {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const token = this.authService.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return new HttpHeaders(headers);
  }

  getImportantDays(): Observable<ImportantDay[]> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.get<ImportantDay[]>(`${this.apiUrl}/important-days`, {
      headers: this.buildHeaders(),
    });
  }

  createImportantDay(payload: ImportantDayPayload): Observable<ImportantDay> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.post<ImportantDay>(
      `${this.apiUrl}/important-days`,
      payload,
      { headers: this.buildHeaders() },
    );
  }

  updateImportantDay(
    id: number,
    payload: ImportantDayPayload,
  ): Observable<ImportantDay> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.put<ImportantDay>(
      `${this.apiUrl}/important-days/${id}`,
      payload,
      { headers: this.buildHeaders() },
    );
  }

  deleteImportantDay(
    id: number,
  ): Observable<{ message: string; id: number }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.delete<{ message: string; id: number }>(
      `${this.apiUrl}/important-days/${id}`,
      { headers: this.buildHeaders() },
    );
  }
}
