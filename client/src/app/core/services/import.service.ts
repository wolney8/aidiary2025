// Import service — handles template download, file upload, and history retrieval

import {
  HttpClient,
  HttpEventType,
  HttpHeaders,
  HttpParams,
  HttpResponse,
} from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { type Observable, throwError } from "rxjs";
import { catchError, map } from "rxjs/operators";
import { AuthService } from "./auth.service";

export interface ImportHistoryItem {
  id: number;
  imported_at: string;
  filename: string;
  imported_count: number;
  skipped_count: number;
  status: "success" | "partial" | "failed" | "empty";
  notes?: string;
}

export interface ImportResult {
  status: "success" | "partial" | "failed" | "empty" | "review";
  message: string;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  inserted_daily?: number;
  inserted_dreams?: number;
  skipped_daily?: number;
  skipped_dreams?: number;
  ready_daily?: number;
  ready_dreams?: number;
  duplicate_daily?: number;
  duplicate_dreams?: number;
  errors?: string[];
  warnings?: string[];
  duplicate_entries?: ImportDuplicateEntry[];
  import_session_id?: string;
}

export interface ImportDuplicateEntry {
  row_id: string;
  entry_type: "daily" | "dream";
  entry_date: string;
  title: string;
  reason: string;
  content_preview?: string;
}

export interface UploadProgress {
  percent: number;
  loaded: number;
  total: number;
}

export interface ExportFilters {
  fromDate?: string;
  toDate?: string;
  includeDaily?: boolean;
  includeDreams?: boolean;
}

export interface ExportDownloadResult {
  blob: Blob;
  guardToken?: string;
}

export interface BulkDeleteReadiness {
  first_entry_date: string | null;
  last_entry_date: string | null;
  daily_count: number;
  dream_count: number;
  total_entries: number;
  has_entries: boolean;
  eligible_for_delete: boolean;
  guard_token_present: boolean;
  requires_full_export: boolean;
}

export interface BulkDeleteResult {
  message: string;
  deleted_daily: number;
  deleted_dreams: number;
  deleted_total: number;
}

interface UploadSummaryPayload {
  inserted_daily?: unknown;
  inserted_dreams?: unknown;
  skipped_daily?: unknown;
  skipped_dreams?: unknown;
  ready_daily?: unknown;
  ready_dreams?: unknown;
  duplicate_daily?: unknown;
  duplicate_dreams?: unknown;
}

interface UploadResponsePayload {
  summary?: UploadSummaryPayload;
  status?: unknown;
  errors?: unknown;
  warnings?: unknown;
  duplicate_entries?: unknown;
  import_session_id?: unknown;
  message?: unknown;
  imported_count?: unknown;
  skipped_count?: unknown;
  error_count?: unknown;
}

interface HistoryResponsePayload {
  history?: unknown[];
}

interface HistoryItemPayload {
  id?: unknown;
  imported_at?: unknown;
  filename?: unknown;
  imported_count?: unknown;
  skipped_count?: unknown;
  inserted_daily?: unknown;
  inserted_dreams?: unknown;
  skipped_daily?: unknown;
  skipped_dreams?: unknown;
  status?: unknown;
  notes?: unknown;
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

  /** Download user entries as an Excel export, optionally filtered by date/type. */
  downloadExport(filters?: ExportFilters): Observable<ExportDownloadResult> {
    const headers = this.getAuthHeaders();
    const params = this.buildExportParams(filters);
    return this.requestWithPortFallback((baseUrl) =>
      this.http
        .get(`${baseUrl}/import/export`, {
          headers,
          params,
          responseType: "blob",
          observe: "response",
        })
        .pipe(
          map((response: HttpResponse<Blob>) => ({
            blob: response.body ?? new Blob(),
            guardToken:
              response.headers.get("X-AiDiary-Export-Token") ?? undefined,
          })),
        ),
    );
  }

  getBulkDeleteReadiness(
    guardToken?: string,
  ): Observable<BulkDeleteReadiness> {
    const headers = this.getAuthHeaders();
    let params = new HttpParams();
    if (guardToken) {
      params = params.set("guard_token", guardToken);
    }

    return this.requestWithPortFallback((baseUrl) =>
      this.http.get<BulkDeleteReadiness>(
        `${baseUrl}/entries/bulk-delete-readiness`,
        {
          headers,
          params,
        },
      ),
    );
  }

  bulkDeleteAllEntries(
    guardToken: string,
    confirmationText: string,
  ): Observable<BulkDeleteResult> {
    const headers = this.getAuthHeaders();
    return this.requestWithPortFallback((baseUrl) =>
      this.http.post<BulkDeleteResult>(
        `${baseUrl}/entries/bulk-delete`,
        {
          guard_token: guardToken,
          confirmation_text: confirmationText,
        },
        { headers },
      ),
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
                  ? (event.body as UploadResponsePayload)
                  : {};
              const summary =
                body.summary && typeof body.summary === "object"
                  ? (body.summary as UploadSummaryPayload)
                  : {};

              const optionalNumber = (value: unknown): number | undefined => {
                if (value === null || value === undefined) {
                  return undefined;
                }
                const numericValue = Number(value);
                return Number.isFinite(numericValue) ? numericValue : undefined;
              };

              const insertedDaily = Number(summary.inserted_daily ?? 0);
              const insertedDreams = Number(summary.inserted_dreams ?? 0);
              const skippedDaily = Number(summary.skipped_daily ?? 0);
              const skippedDreams = Number(summary.skipped_dreams ?? 0);

              const rawStatus = String(body.status ?? "failed");
              const status = this.mapBackendStatus(rawStatus);

              const errors = this.toStringArray(body.errors);
              const warnings = this.toStringArray(body.warnings);
              const duplicateEntries = this.toDuplicateEntryArray(
                body.duplicate_entries,
              );

              const message =
                typeof body.message === "string"
                  ? body.message
                  : rawStatus === "empty"
                    ? "No valid entries were found in the uploaded file."
                    : status === "review"
                      ? "Duplicates found. Review and confirm before importing."
                    : status === "partial"
                      ? "Import completed with duplicates skipped."
                      : "Upload complete.";

              // Normalise backend shape into stable frontend ImportResult
              const result: ImportResult = {
                status,
                message,
                imported_count: Number(
                  body.imported_count ?? insertedDaily + insertedDreams,
                ),
                skipped_count: Number(
                  body.skipped_count ?? skippedDaily + skippedDreams,
                ),
                error_count: Number(body.error_count ?? errors.length),
                inserted_daily: optionalNumber(summary.inserted_daily),
                inserted_dreams: optionalNumber(summary.inserted_dreams),
                skipped_daily: optionalNumber(summary.skipped_daily),
                skipped_dreams: optionalNumber(summary.skipped_dreams),
                ready_daily: optionalNumber(summary.ready_daily),
                ready_dreams: optionalNumber(summary.ready_dreams),
                duplicate_daily: optionalNumber(summary.duplicate_daily),
                duplicate_dreams: optionalNumber(summary.duplicate_dreams),
                errors,
                warnings,
                duplicate_entries: duplicateEntries,
                import_session_id:
                  typeof body.import_session_id === "string"
                    ? body.import_session_id
                    : undefined,
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

  commitImportSession(
    importSessionId: string,
    acceptedDuplicateRowIds: string[],
  ): Observable<ImportResult> {
    const headers = this.getAuthHeaders();
    return this.requestWithPortFallback((baseUrl) =>
      this.http
        .post<unknown>(
          `${baseUrl}/import/commit`,
          {
            import_session_id: importSessionId,
            accepted_duplicate_row_ids: acceptedDuplicateRowIds,
          },
          { headers },
        )
        .pipe(map((response) => this.normaliseUploadResult(response))),
    );
  }

  /** Fetch the import history for the current user. */
  getHistory(): Observable<ImportHistoryItem[]> {
    const headers = this.getAuthHeaders();
    return this.requestWithPortFallback((baseUrl) =>
      this.http.get<unknown>(`${baseUrl}/import/history`, { headers }).pipe(
        map((response) => {
          const payload =
            response && typeof response === "object"
              ? (response as HistoryResponsePayload)
              : undefined;
          const rawItems = Array.isArray(response)
            ? response
            : payload && Array.isArray(payload.history)
              ? payload.history
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
    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;

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

  private buildExportParams(filters?: ExportFilters): HttpParams {
    let params = new HttpParams();

    if (!filters) {
      return params;
    }

    if (filters.fromDate) {
      params = params.set("from_date", filters.fromDate);
    }

    if (filters.toDate) {
      params = params.set("to_date", filters.toDate);
    }

    const includeDaily = filters.includeDaily ?? true;
    const includeDreams = filters.includeDreams ?? true;

    // Keep defaults compact: when both are true, omit both params.
    if (!(includeDaily && includeDreams)) {
      params = params.set("include_daily", String(includeDaily));
      params = params.set("include_dreams", String(includeDreams));
    }

    return params;
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

    const item = raw as HistoryItemPayload;

    const insertedDaily = Number(item.inserted_daily ?? 0);
    const insertedDreams = Number(item.inserted_dreams ?? 0);
    const skippedDaily = Number(item.skipped_daily ?? 0);
    const skippedDreams = Number(item.skipped_dreams ?? 0);

    const importedCount = Number(
      item.imported_count ?? insertedDaily + insertedDreams,
    );
    const skippedCount = Number(
      item.skipped_count ?? skippedDaily + skippedDreams,
    );

    const rawStatus = String(item.status ?? "failed");
    const status: ImportHistoryItem["status"] =
      rawStatus === "success"
        ? "success"
        : rawStatus === "empty"
          ? "empty"
          : rawStatus === "skipped" || rawStatus === "partial"
            ? "partial"
            : "failed";

    return {
      id: Number(item.id ?? 0),
      imported_at: String(item.imported_at ?? ""),
      filename: String(item.filename ?? "Unknown file"),
      imported_count: importedCount,
      skipped_count: skippedCount,
      status,
      notes: typeof item.notes === "string" ? item.notes : undefined,
    };
  }

  private mapBackendStatus(
    rawStatus: string,
  ): ImportHistoryItem["status"] | ImportResult["status"] {
    if (rawStatus === "review_required" || rawStatus === "review") {
      return "review";
    }
    if (rawStatus === "success") {
      return "success";
    }
    if (rawStatus === "skipped" || rawStatus === "partial") {
      return "partial";
    }
    if (rawStatus === "empty") {
      return "empty";
    }
    return "failed";
  }

  private normaliseUploadResult(response: unknown): ImportResult {
    const body =
      response && typeof response === "object"
        ? (response as UploadResponsePayload)
        : {};
    const summary =
      body.summary && typeof body.summary === "object"
        ? (body.summary as UploadSummaryPayload)
        : {};

    const optionalNumber = (value: unknown): number | undefined => {
      if (value === null || value === undefined) {
        return undefined;
      }
      const numericValue = Number(value);
      return Number.isFinite(numericValue) ? numericValue : undefined;
    };

    const insertedDaily = Number(summary.inserted_daily ?? 0);
    const insertedDreams = Number(summary.inserted_dreams ?? 0);
    const skippedDaily = Number(summary.skipped_daily ?? 0);
    const skippedDreams = Number(summary.skipped_dreams ?? 0);
    const rawStatus = String(body.status ?? "failed");
    const status = this.mapBackendStatus(rawStatus);
    const errors = this.toStringArray(body.errors);
    const warnings = this.toStringArray(body.warnings);

    return {
      status,
      message:
        typeof body.message === "string"
          ? body.message
          : status === "review"
            ? "Duplicates found. Review and confirm before importing."
            : status === "partial"
              ? "Import completed with duplicates skipped."
              : rawStatus === "empty"
                ? "No valid entries were found in the uploaded file."
                : "Upload complete.",
      imported_count: Number(body.imported_count ?? insertedDaily + insertedDreams),
      skipped_count: Number(body.skipped_count ?? skippedDaily + skippedDreams),
      error_count: Number(body.error_count ?? errors.length),
      inserted_daily: optionalNumber(summary.inserted_daily),
      inserted_dreams: optionalNumber(summary.inserted_dreams),
      skipped_daily: optionalNumber(summary.skipped_daily),
      skipped_dreams: optionalNumber(summary.skipped_dreams),
      ready_daily: optionalNumber(summary.ready_daily),
      ready_dreams: optionalNumber(summary.ready_dreams),
      duplicate_daily: optionalNumber(summary.duplicate_daily),
      duplicate_dreams: optionalNumber(summary.duplicate_dreams),
      errors,
      warnings,
      duplicate_entries: this.toDuplicateEntryArray(body.duplicate_entries),
      import_session_id:
        typeof body.import_session_id === "string"
          ? body.import_session_id
          : undefined,
    };
  }

  private toStringArray(value: unknown): string[] {
    return Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string")
      : [];
  }

  private toDuplicateEntryArray(value: unknown): ImportDuplicateEntry[] {
    if (!Array.isArray(value)) {
      return [];
    }

    const entries: Array<ImportDuplicateEntry | null> = value
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }

        const raw = item as Record<string, unknown>;
        const rowId = raw["row_id"];
        const entryType = raw["entry_type"];
        const entryDate = raw["entry_date"];
        const title = raw["title"];
        const reason = raw["reason"];
        const contentPreview = raw["content_preview"];

        if (
          typeof rowId !== "string" ||
          (entryType !== "daily" && entryType !== "dream") ||
          typeof entryDate !== "string" ||
          typeof title !== "string" ||
          typeof reason !== "string"
        ) {
          return null;
        }

        return {
          row_id: rowId,
          entry_type: entryType,
          entry_date: entryDate,
          title,
          reason,
          content_preview:
            typeof contentPreview === "string" ? contentPreview : undefined,
        };
      });

    return entries.filter(
      (item): item is ImportDuplicateEntry => item !== null,
    );
  }
}
