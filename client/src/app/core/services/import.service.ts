// Import service — handles template download, file upload, and history retrieval
import { Injectable, inject } from "@angular/core";
import { HttpClient, HttpEventType, HttpHeaders } from "@angular/common/http";
import { Observable, throwError } from "rxjs";
import { catchError, map } from "rxjs/operators";
import { AuthService } from "./auth.service";

export interface ImportHistoryItem {
  id: number;
  imported_at: string;
  filename: string;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  status: "success" | "partial" | "failed";
  notes?: string;
}

export interface ImportResult {
  status: "success" | "partial" | "failed";
  message: string;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  errors?: string[];
  warnings?: string[];
}

export interface UploadProgress {
  percent: number;
  loaded: number;
  total: number;
}

@Injectable({ providedIn: "root" })
export class ImportService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);

  private readonly primaryBaseUrl = "http://localhost:5001/api";
  private readonly fallbackBaseUrl = "http://localhost:500/api";
  private readonly maxFileSizeBytes = 5 * 1024 * 1024; // 5 MB
  private readonly allowedMimeTypes = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
  ];
  private readonly allowedExtensions = [".xlsx", ".xls"];

  /** Download the Excel import template. */
  downloadTemplate(): Observable<Blob> {
    const headers = this.getAuthHeaders();
    return this.requestWithPortFallback((baseUrl) =>
      this.http.get(`${baseUrl}/import/template`, {
        headers,
        responseType: "blob",
      }),
    );
  }

  /**
   * Upload an Excel file and report progress.
   * Emits UploadProgress objects while uploading, then the final ImportResult.
   */
  uploadFile(
    file: File,
  ): Observable<
    | { type: "progress"; progress: UploadProgress }
    | { type: "result"; result: ImportResult }
  > {
    const headers = this.getAuthHeaders();
    const formData = new FormData();
    formData.append("file", file, file.name);

    return this.requestWithPortFallback((baseUrl) =>
      this.http
        .post(`${baseUrl}/import/upload`, formData, {
          headers,
          reportProgress: true,
          observe: "events",
        })
        .pipe(
          map((event) => {
            if (event.type === HttpEventType.UploadProgress) {
              const total = event.total ?? file.size;
              const percent = Math.round((event.loaded / total) * 100);
              return {
                type: "progress" as const,
                progress: { percent, loaded: event.loaded, total },
              };
            }

            if (event.type === HttpEventType.Response) {
              const body =
                event.body && typeof event.body === "object"
                  ? (event.body as Record<string, unknown>)
                  : {};
              const summary =
                body["summary"] && typeof body["summary"] === "object"
                  ? (body["summary"] as Record<string, unknown>)
                  : {};

              const insertedDaily = Number(summary["inserted_daily"] ?? 0);
              const insertedDreams = Number(summary["inserted_dreams"] ?? 0);
              const skippedDaily = Number(summary["skipped_daily"] ?? 0);
              const skippedDreams = Number(summary["skipped_dreams"] ?? 0);

              const rawStatus = String(body["status"] ?? "failed");
              const status = this.mapBackendStatus(rawStatus);

              const errors = this.toStringArray(body["errors"]);
              const warnings = this.toStringArray(body["warnings"]);

              const message =
                typeof body["message"] === "string"
                  ? body["message"]
                  : rawStatus === "empty"
                    ? "No valid entries were found in the uploaded file."
                    : status === "partial"
                      ? "Import completed with duplicates skipped."
                      : "Upload complete.";

              // Normalise backend shape into stable frontend ImportResult
              const result: ImportResult = {
                status,
                message,
                imported_count: Number(
                  body["imported_count"] ?? insertedDaily + insertedDreams,
                ),
                skipped_count: Number(
                  body["skipped_count"] ?? skippedDaily + skippedDreams,
                ),
                error_count: Number(body["error_count"] ?? errors.length),
                errors,
                warnings,
              };
              return { type: "result" as const, result };
            }

            // Intermediate events (Sent, ResponseHeader, etc.) — skip
            return null as unknown as never;
          }),
          // Filter out null events from intermediate HttpEventTypes
          map((val) => val),
        ),
    );
  }

  /** Fetch the import history for the current user. */
  getHistory(): Observable<ImportHistoryItem[]> {
    const headers = this.getAuthHeaders();
    return this.requestWithPortFallback((baseUrl) =>
      this.http.get<unknown>(`${baseUrl}/import/history`, { headers }).pipe(
        map((response) => {
          const rawItems = Array.isArray(response)
            ? response
            : response &&
                typeof response === "object" &&
                Array.isArray((response as Record<string, unknown>)["history"])
              ? ((response as Record<string, unknown>)["history"] as unknown[])
              : [];

          return rawItems
            .map((item) => this.normaliseHistoryItem(item))
            .filter((item): item is ImportHistoryItem => item !== null);
        }),
      ),
    );
  }

  /** Client-side validation — returns an error string or null if valid. */
  validateFile(file: File): string | null {
    const extension = "." + file.name.split(".").pop()?.toLowerCase();

    if (!this.allowedExtensions.includes(extension)) {
      return `Invalid file type. Only Excel files (.xlsx, .xls) are accepted.`;
    }

    if (!this.allowedMimeTypes.includes(file.type) && file.type !== "") {
      // Some browsers report empty MIME type for Excel — allow it if extension is correct
      if (file.type !== "") {
        return `Invalid file type. Only Excel files (.xlsx, .xls) are accepted.`;
      }
    }

    if (file.size > this.maxFileSizeBytes) {
      const maxMB = this.maxFileSizeBytes / (1024 * 1024);
      const fileMB = (file.size / (1024 * 1024)).toFixed(1);
      return `File is too large (${fileMB} MB). Maximum allowed size is ${maxMB} MB.`;
    }

    if (file.size === 0) {
      return "The selected file is empty. Please choose a valid Excel file.";
    }

    return null;
  }

  private getAuthHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({ Authorization: `Bearer ${token}` });
  }

  private requestWithPortFallback<T>(
    requestFactory: (baseUrl: string) => Observable<T>,
  ): Observable<T> {
    return requestFactory(this.primaryBaseUrl).pipe(
      catchError((err) => {
        if (!this.isConnectionLevelError(err)) {
          return throwError(() => this.normaliseError(err));
        }

        return requestFactory(this.fallbackBaseUrl).pipe(
          catchError((fallbackErr) =>
            throwError(() => this.normaliseError(fallbackErr)),
          ),
        );
      }),
    );
  }

  private isConnectionLevelError(err: unknown): boolean {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const httpErr = err as any;
    return httpErr?.status === 0;
  }

  private normaliseError(err: unknown): Error {
    if (err instanceof Error) return err;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const httpErr = err as any;

    if (httpErr?.status === 0) {
      return new Error(
        "Cannot reach the backend service on local API endpoints (ports 5001 or 500). Please confirm the server is running and CORS is configured.",
      );
    }

    const message =
      httpErr?.error?.message ||
      httpErr?.error?.error ||
      httpErr?.message ||
      "An unexpected error occurred. Please try again.";
    return new Error(message);
  }

  private normaliseHistoryItem(raw: unknown): ImportHistoryItem | null {
    if (!raw || typeof raw !== "object") {
      return null;
    }

    const item = raw as Record<string, unknown>;

    const insertedDaily = Number(item["inserted_daily"] ?? 0);
    const insertedDreams = Number(item["inserted_dreams"] ?? 0);
    const skippedDaily = Number(item["skipped_daily"] ?? 0);
    const skippedDreams = Number(item["skipped_dreams"] ?? 0);

    const importedCount = Number(
      item["imported_count"] ?? insertedDaily + insertedDreams,
    );
    const skippedCount = Number(
      item["skipped_count"] ?? skippedDaily + skippedDreams,
    );

    const rawStatus = String(item["status"] ?? "failed");
    const status = this.mapBackendStatus(rawStatus);

    return {
      id: Number(item["id"] ?? 0),
      imported_at: String(item["imported_at"] ?? ""),
      filename: String(item["filename"] ?? "Unknown file"),
      imported_count: importedCount,
      skipped_count: skippedCount,
      error_count: Number(item["error_count"] ?? 0),
      status,
      notes: typeof item["notes"] === "string" ? item["notes"] : undefined,
    };
  }

  private mapBackendStatus(
    rawStatus: string,
  ): ImportHistoryItem["status"] | ImportResult["status"] {
    if (rawStatus === "success") {
      return "success";
    }
    if (rawStatus === "skipped" || rawStatus === "partial") {
      return "partial";
    }
    if (rawStatus === "empty") {
      return "failed";
    }
    return "failed";
  }

  private toStringArray(value: unknown): string[] {
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string")
      : [];
  }
}
