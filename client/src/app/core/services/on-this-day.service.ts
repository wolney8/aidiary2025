import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpHeaders, HttpParams } from "@angular/common/http";
import { Observable, throwError } from "rxjs";
import { environment } from "../../../environments/environment";
import {
  OnThisDayEntryType,
  OnThisDayFeed,
} from "../models/on-this-day.model";
import { AuthService } from "./auth.service";

@Injectable({ providedIn: "root" })
export class OnThisDayService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = environment.apiBaseUrl;

  getFeed(date?: string): Observable<OnThisDayFeed> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }
    const params = date ? new HttpParams().set("date", date) : undefined;
    return this.http.get<OnThisDayFeed>(`${this.apiUrl}/on-this-day`, {
      headers: this.buildHeaders(),
      params,
    });
  }

  getMonthFeed(year: number, month: number): Observable<OnThisDayFeed> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }
    const monthValue = `${year}-${String(month).padStart(2, "0")}`;
    return this.http.get<OnThisDayFeed>(`${this.apiUrl}/on-this-day`, {
      headers: this.buildHeaders(),
      params: new HttpParams().set("month", monthValue),
    });
  }

  hideEntry(
    entryType: OnThisDayEntryType,
    entryId: number,
  ): Observable<{ message: string }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }
    return this.http.post<{ message: string }>(
      `${this.apiUrl}/on-this-day/hide`,
      { entry_type: entryType, entry_id: entryId },
      { headers: this.buildHeaders() },
    );
  }

  private buildHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders(
      token ? { Authorization: `Bearer ${token}` } : {},
    );
  }
}
