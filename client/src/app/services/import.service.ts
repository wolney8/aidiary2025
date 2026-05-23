import { Injectable } from "@angular/core";
import {
  HttpClient,
  HttpErrorResponse,
  HttpHeaders,
} from "@angular/common/http";
import { Observable, throwError } from "rxjs";
import { catchError } from "rxjs/operators";
import { AuthService } from "../core/services/auth.service";

export interface ImportTemplate {
  headers: string[];
  example_data: string[][];
}

export interface ImportResult {
  success: boolean;
  entries_imported: number;
  errors: string[];
  warnings: string[];
}

@Injectable({
  providedIn: "root",
})
export class ImportService {
  private readonly baseUrl = "http://localhost:5001/api";

  constructor(
    private http: HttpClient,
    private authService: AuthService,
  ) {}

  private getHeaders(): HttpHeaders {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    const token = this.authService.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    return new HttpHeaders(headers);
  }

  /**
   * Download import template for specified entry type
   */
  getImportTemplate(
    entryType: "daily" | "dream" = "daily",
  ): Observable<ImportTemplate> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http
      .get<ImportTemplate>(`${this.baseUrl}/import/template/${entryType}`, {
        headers: this.getHeaders(),
      })
      .pipe(catchError(this.handleError));
  }

  /**
   * Upload and process import file
   */
  uploadImportFile(
    file: File,
    entryType: "daily" | "dream" = "daily",
  ): Observable<ImportResult> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("entry_type", entryType);

    // For FormData, we need to set headers differently
    const token = this.authService.getToken();
    const headers = new HttpHeaders();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    return this.http
      .post<ImportResult>(`${this.baseUrl}/import/upload`, formData, {
        headers: headers,
      })
      .pipe(catchError(this.handleError));
  }

  /**
   * Validate import file without processing
   */
  validateImportFile(
    file: File,
    entryType?: "daily" | "dream",
  ): Observable<{ valid: boolean; message: string }> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    const formData = new FormData();
    formData.append("file", file);
    if (entryType) {
      formData.append("entry_type", entryType);
    }

    // For FormData, we need to set headers differently
    const token = this.authService.getToken();
    const headers = new HttpHeaders();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    return this.http
      .post<{ valid: boolean; message: string }>(
        `${this.baseUrl}/import/validate`,
        formData,
        {
          headers: headers,
        },
      )
      .pipe(catchError(this.handleError));
  }

  /**
   * Get import history and statistics
   */
  getImportHistory(): Observable<any[]> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    return this.http
      .get<any[]>(`${this.baseUrl}/import/history`, {
        headers: this.getHeaders(),
      })
      .pipe(catchError(this.handleError));
  }

  private handleError(error: HttpErrorResponse) {
    let errorMessage = "An error occurred during import";

    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Error: ${error.error.message}`;
    } else {
      // Server-side error
      errorMessage =
        error.error?.message ||
        `Error Code: ${error.status}\nMessage: ${error.message}`;
    }

    return throwError(() => errorMessage);
  }
}
