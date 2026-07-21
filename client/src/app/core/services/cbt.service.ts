import { HttpClient, HttpHeaders, HttpParams } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable, throwError } from "rxjs";
import { environment } from "../../../environments/environment";
import {
  CbtLinkedEntryType,
  CbtWorksheet,
  CbtWorksheetPayload,
  CbtWorksheetStatus,
} from "../models/cbt.model";
import { AuthService } from "./auth.service";

@Injectable({ providedIn: "root" })
export class CbtService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/cbt/worksheets`;

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

  listWorksheets(filters?: {
    status?: CbtWorksheetStatus;
    linkedEntryType?: CbtLinkedEntryType;
    linkedEntryId?: number;
  }): Observable<CbtWorksheet[]> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;

    let params = new HttpParams();
    if (filters?.status) params = params.set("status", filters.status);
    if (filters?.linkedEntryType) {
      params = params.set("linked_entry_type", filters.linkedEntryType);
    }
    if (filters?.linkedEntryId) {
      params = params.set("linked_entry_id", filters.linkedEntryId);
    }
    return this.http.get<CbtWorksheet[]>(this.apiUrl, {
      headers: this.buildHeaders(),
      params,
    });
  }

  createWorksheet(payload: CbtWorksheetPayload = {}): Observable<CbtWorksheet> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.post<CbtWorksheet>(this.apiUrl, payload, {
      headers: this.buildHeaders(),
    });
  }

  getWorksheet(id: number): Observable<CbtWorksheet> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.get<CbtWorksheet>(`${this.apiUrl}/${id}`, {
      headers: this.buildHeaders(),
    });
  }

  updateWorksheet(
    id: number,
    payload: CbtWorksheetPayload,
  ): Observable<CbtWorksheet> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.put<CbtWorksheet>(`${this.apiUrl}/${id}`, payload, {
      headers: this.buildHeaders(),
    });
  }

  completeWorksheet(id: number): Observable<CbtWorksheet> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.post<CbtWorksheet>(
      `${this.apiUrl}/${id}/complete`,
      {},
      { headers: this.buildHeaders() },
    );
  }

  reviseWorksheet(
    id: number,
    payload: CbtWorksheetPayload,
  ): Observable<CbtWorksheet> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.put<CbtWorksheet>(
      `${this.apiUrl}/${id}/revise`,
      payload,
      { headers: this.buildHeaders() },
    );
  }

  analyseWorksheet(id: number): Observable<CbtWorksheet> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.post<CbtWorksheet>(
      `${this.apiUrl}/${id}/analyse`,
      {},
      { headers: this.buildHeaders() },
    );
  }

  deleteWorksheet(id: number): Observable<{ message: string }> {
    const authError = this.ensureAuthenticated();
    if (authError) return authError;
    return this.http.delete<{ message: string }>(`${this.apiUrl}/${id}`, {
      headers: this.buildHeaders(),
    });
  }
}
