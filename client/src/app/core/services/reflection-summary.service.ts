import { HttpClient, HttpHeaders, HttpParams } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable, throwError } from "rxjs";
import { environment } from "../../../environments/environment";
import {
  ReflectionSummary,
  ReflectionSummaryPeriodType,
} from "../models/reflection-summary.model";
import { AuthService } from "./auth.service";

@Injectable({ providedIn: "root" })
export class ReflectionSummaryService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/reflection-summaries`;

  private buildHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }

  private ensureAuthenticated(): Observable<never> | null {
    return this.authService.isAuthenticated()
      ? null
      : throwError(() => new Error("User not authenticated"));
  }

  listSummaries(periodType?: ReflectionSummaryPeriodType): Observable<ReflectionSummary[]> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;

    let params = new HttpParams();
    if (periodType) params = params.set("period_type", periodType);
    return this.http.get<ReflectionSummary[]>(this.apiUrl, {
      headers: this.buildHeaders(),
      params,
    });
  }

  generateSummary(
    periodType: ReflectionSummaryPeriodType,
    periodStart: string,
  ): Observable<ReflectionSummary> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;

    return this.http.post<ReflectionSummary>(
      `${this.apiUrl}/generate`,
      { period_type: periodType, period_start: periodStart },
      { headers: this.buildHeaders() },
    );
  }

  deleteSummary(id: number): Observable<{ message: string }> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;

    return this.http.delete<{ message: string }>(`${this.apiUrl}/${id}`, {
      headers: this.buildHeaders(),
    });
  }
}
