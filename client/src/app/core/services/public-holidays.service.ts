import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Observable, throwError } from "rxjs";
import { AuthService } from "./auth.service";
import {
  PublicHolidayCountry,
  PublicHolidayFeedResponse,
} from "../models/public-holiday.model";

@Injectable({
  providedIn: "root",
})
export class PublicHolidaysService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = "http://localhost:5001/api";

  private buildHeaders(): HttpHeaders {
    const headers: Record<string, string> = {};
    const token = this.authService.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return new HttpHeaders(headers);
  }

  getAvailableCountries(): Observable<PublicHolidayCountry[]> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.get<PublicHolidayCountry[]>(
      `${this.apiUrl}/public-holidays/countries`,
      { headers: this.buildHeaders() },
    );
  }

  getPublicHolidays(year: number): Observable<PublicHolidayFeedResponse> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http.get<PublicHolidayFeedResponse>(
      `${this.apiUrl}/public-holidays?year=${year}`,
      { headers: this.buildHeaders() },
    );
  }
}
