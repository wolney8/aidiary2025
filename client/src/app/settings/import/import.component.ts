// Import component — full UX journey: template download → file selection → upload → result feedback
import {
  Component,
  ElementRef,
  OnInit,
  ViewChild,
  inject,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatTableModule } from "@angular/material/table";
import { MatChipsModule } from "@angular/material/chips";
import { MatTooltipModule } from "@angular/material/tooltip";
import { MatDividerModule } from "@angular/material/divider";
import { trigger, transition, style, animate } from "@angular/animations";
import { filter } from "rxjs/operators";
import {
  ImportService,
  ImportHistoryItem,
  ImportResult,
  UploadProgress,
} from "../../core/services/import.service";

type UploadState = "idle" | "uploading" | "success" | "partial" | "error";

@Component({
  selector: "app-import",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatTableModule,
    MatChipsModule,
    MatTooltipModule,
    MatDividerModule,
  ],
  animations: [
    trigger("fadeSlideIn", [
      transition(":enter", [
        style({ opacity: 0, transform: "translateY(-8px)" }),
        animate(
          "250ms cubic-bezier(0.4,0,0.2,1)",
          style({ opacity: 1, transform: "translateY(0)" }),
        ),
      ]),
      transition(":leave", [
        animate(
          "180ms cubic-bezier(0.4,0,1,1)",
          style({ opacity: 0, transform: "translateY(-8px)" }),
        ),
      ]),
    ]),
  ],
  template: `
    <!-- Hidden file input -->
    <input
      #fileInput
      type="file"
      accept=".xlsx,.xls"
      class="sr-only"
      aria-hidden="true"
      (change)="onFileSelected($event)"
    />

    <div class="import-container" role="main" aria-label="Import entries">
      <!-- ── Step 1: Download Template ── -->
      <mat-card class="step-card">
        <mat-card-header>
          <mat-icon mat-card-avatar class="step-icon">download</mat-icon>
          <mat-card-title>Step 1 — Download Template</mat-card-title>
          <mat-card-subtitle>
            Get the Excel template, fill it with your entries, then upload
            below.
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <p class="hint-text">
            The template contains separate sheets for <strong>Daily</strong> and
            <strong>Dream</strong> entries with all required columns
            pre-defined.
          </p>
        </mat-card-content>
        <mat-card-actions>
          <button
            mat-raised-button
            color="primary"
            (click)="downloadTemplate()"
            [disabled]="isDownloading"
            aria-label="Download Excel import template"
          >
            <mat-icon>download</mat-icon>
            {{ isDownloading ? "Downloading…" : "Download Template" }}
          </button>
        </mat-card-actions>
      </mat-card>

      <!-- ── Step 2: Select & Upload File ── -->
      <mat-card class="step-card">
        <mat-card-header>
          <mat-icon mat-card-avatar class="step-icon">upload_file</mat-icon>
          <mat-card-title>Step 2 — Upload Completed Template</mat-card-title>
          <mat-card-subtitle>
            Select your completed Excel file (.xlsx or .xls, max 5 MB).
          </mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <!-- Drop-zone / file selector -->
          <div
            class="drop-zone"
            [class.drop-zone--has-file]="selectedFile && !validationError"
            [class.drop-zone--invalid]="!!validationError"
            role="button"
            tabindex="0"
            aria-label="Click to choose an Excel file for import"
            (click)="triggerFilePicker()"
            (keydown.enter)="triggerFilePicker()"
            (keydown.space)="triggerFilePicker()"
          >
            <mat-icon class="drop-icon" aria-hidden="true">
              {{ selectedFile && !validationError ? "task" : "upload_file" }}
            </mat-icon>

            <ng-container *ngIf="!selectedFile; else fileSelected">
              <p class="drop-primary">Click to choose a file</p>
              <p class="drop-secondary">
                Accepts .xlsx and .xls — maximum 5 MB
              </p>
            </ng-container>

            <ng-template #fileSelected>
              <p class="drop-primary file-name" [title]="selectedFile!.name">
                {{ selectedFile!.name }}
              </p>
              <p class="drop-secondary">
                {{ formatFileSize(selectedFile!.size) }}
              </p>
            </ng-template>
          </div>

          <!-- Validation error -->
          <div
            *ngIf="validationError"
            class="feedback feedback--error"
            role="alert"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">error_outline</mat-icon>
            <span>{{ validationError }}</span>
          </div>

          <!-- Upload progress bar -->
          <div
            *ngIf="uploadState === 'uploading'"
            class="progress-wrapper"
            role="status"
            aria-live="polite"
            [@fadeSlideIn]
          >
            <mat-progress-bar
              mode="determinate"
              [value]="uploadProgress.percent"
              aria-label="Upload progress"
            ></mat-progress-bar>
            <p class="progress-label">
              Uploading… {{ uploadProgress.percent }}% ({{
                formatFileSize(uploadProgress.loaded)
              }}
              of {{ formatFileSize(uploadProgress.total) }})
            </p>
          </div>

          <!-- Result feedback — success -->
          <div
            *ngIf="uploadState === 'success'"
            class="feedback feedback--success"
            role="status"
            aria-live="polite"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">check_circle</mat-icon>
            <div class="feedback-body">
              <p class="feedback-title">Import successful</p>
              <p>
                {{ importResult!.imported_count }} entries imported,
                {{ importResult!.skipped_count }} skipped.
              </p>
              <p
                *ngIf="importResult!.warnings && importResult!.warnings!.length"
              >
                <strong>Warnings:</strong>
                {{ importResult!.warnings!.join("; ") }}
              </p>
            </div>
          </div>

          <!-- Result feedback — partial -->
          <div
            *ngIf="uploadState === 'partial'"
            class="feedback feedback--warning"
            role="alert"
            aria-live="assertive"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">warning_amber</mat-icon>
            <div class="feedback-body">
              <p class="feedback-title">Import completed with warnings</p>
              <p>
                {{ importResult!.imported_count }} entries imported,
                {{ importResult!.skipped_count }} skipped,
                {{ importResult!.error_count }} rows had errors.
              </p>
              <ul
                *ngIf="importResult!.errors && importResult!.errors!.length"
                class="error-list"
              >
                <li *ngFor="let err of importResult!.errors">{{ err }}</li>
              </ul>
            </div>
          </div>

          <!-- Result feedback — error -->
          <div
            *ngIf="uploadState === 'error'"
            class="feedback feedback--error"
            role="alert"
            aria-live="assertive"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">cancel</mat-icon>
            <div class="feedback-body">
              <p class="feedback-title">Import failed</p>
              <p>{{ importErrorMessage }}</p>
            </div>
          </div>
        </mat-card-content>

        <mat-card-actions class="upload-actions">
          <button
            mat-stroked-button
            (click)="clearSelection()"
            [disabled]="!selectedFile || uploadState === 'uploading'"
            aria-label="Clear selected file"
          >
            <mat-icon>clear</mat-icon>
            Clear
          </button>

          <button
            mat-raised-button
            color="primary"
            (click)="uploadFile()"
            [disabled]="
              !selectedFile || !!validationError || uploadState === 'uploading'
            "
            aria-label="Upload selected file and import entries"
          >
            <mat-icon>cloud_upload</mat-icon>
            {{ uploadState === "uploading" ? "Uploading…" : "Import Entries" }}
          </button>
        </mat-card-actions>
      </mat-card>

      <!-- ── Step 3: Import History ── -->
      <mat-card class="step-card">
        <mat-card-header>
          <mat-icon mat-card-avatar class="step-icon">history</mat-icon>
          <mat-card-title>Import History</mat-card-title>
          <mat-card-subtitle
            >Recent import sessions for your account.</mat-card-subtitle
          >
        </mat-card-header>

        <mat-card-content>
          <!-- Loading -->
          <div
            *ngIf="historyLoading"
            class="history-loading"
            role="status"
            aria-live="polite"
          >
            <mat-progress-bar
              mode="indeterminate"
              aria-label="Loading import history"
            ></mat-progress-bar>
            <p class="loading-label">Loading import history…</p>
          </div>

          <!-- History error -->
          <div
            *ngIf="historyError && !historyLoading"
            class="feedback feedback--error"
            role="alert"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">error_outline</mat-icon>
            <span>{{ historyError }}</span>
          </div>

          <!-- Empty state -->
          <div
            *ngIf="!historyLoading && !historyError && history.length === 0"
            class="empty-history"
            aria-live="polite"
          >
            <mat-icon aria-hidden="true">inbox</mat-icon>
            <p>No imports yet. Complete Step 2 to see your history here.</p>
          </div>

          <!-- History table -->
          <div
            *ngIf="!historyLoading && !historyError && history.length > 0"
            class="table-wrapper"
          >
            <table
              mat-table
              [dataSource]="history"
              aria-label="Import history table"
              class="history-table"
            >
              <!-- Date column -->
              <ng-container matColumnDef="imported_at">
                <th mat-header-cell *matHeaderCellDef scope="col">Date</th>
                <td mat-cell *matCellDef="let row">
                  {{ formatDate(row.imported_at) }}
                </td>
              </ng-container>

              <!-- Filename column -->
              <ng-container matColumnDef="filename">
                <th mat-header-cell *matHeaderCellDef scope="col">File</th>
                <td mat-cell *matCellDef="let row">
                  <span class="filename-cell" [matTooltip]="row.filename">
                    {{ row.filename }}
                  </span>
                </td>
              </ng-container>

              <!-- Imported column -->
              <ng-container matColumnDef="imported_count">
                <th mat-header-cell *matHeaderCellDef scope="col">Imported</th>
                <td mat-cell *matCellDef="let row">{{ row.imported_count }}</td>
              </ng-container>

              <!-- Skipped column -->
              <ng-container matColumnDef="skipped_count">
                <th mat-header-cell *matHeaderCellDef scope="col">Skipped</th>
                <td mat-cell *matCellDef="let row">{{ row.skipped_count }}</td>
              </ng-container>

              <!-- Errors column -->
              <ng-container matColumnDef="error_count">
                <th mat-header-cell *matHeaderCellDef scope="col">Errors</th>
                <td mat-cell *matCellDef="let row">{{ row.error_count }}</td>
              </ng-container>

              <!-- Status column -->
              <ng-container matColumnDef="status">
                <th mat-header-cell *matHeaderCellDef scope="col">Status</th>
                <td mat-cell *matCellDef="let row">
                  <mat-chip
                    [class]="'status-chip status-chip--' + row.status"
                    [attr.aria-label]="'Status: ' + row.status"
                    disabled
                  >
                    <mat-icon class="chip-icon" aria-hidden="true">{{
                      statusIcon(row.status)
                    }}</mat-icon>
                    {{ statusLabel(row.status) }}
                  </mat-chip>
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="historyColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: historyColumns"></tr>
            </table>
          </div>
        </mat-card-content>

        <mat-card-actions>
          <button
            mat-stroked-button
            (click)="loadHistory()"
            [disabled]="historyLoading"
            aria-label="Refresh import history"
          >
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
        </mat-card-actions>
      </mat-card>
    </div>
  `,
  styles: [
    `
      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      .import-container {
        max-width: 780px;
        margin: 0 auto;
        padding: var(--spacing-md, 16px);
        display: flex;
        flex-direction: column;
        gap: 24px;
      }

      .step-card {
        border-radius: 12px;
      }

      .step-icon {
        color: #7b3ff2;
      }

      mat-card-actions {
        padding: 8px 16px 16px;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .hint-text {
        color: var(--colour-text-secondary);
        font-size: 14px;
        margin: 0;
        line-height: 1.5;
      }

      /* ── Drop zone ── */
      .drop-zone {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        border: 2px dashed #bdbdbd;
        border-radius: 8px;
        padding: 32px 16px;
        cursor: pointer;
        transition:
          border-color 200ms ease,
          background-color 200ms ease;
        outline: none;
        text-align: center;
        min-height: 120px;
      }

      .drop-zone:hover,
      .drop-zone:focus-visible {
        border-color: #7b3ff2;
        background-color: rgba(123, 63, 242, 0.04);
      }

      .drop-zone--has-file {
        border-color: #388e3c;
        background-color: rgba(56, 142, 60, 0.04);
      }

      .drop-zone--invalid {
        border-color: #c62828;
        background-color: rgba(198, 40, 40, 0.04);
      }

      .drop-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: #9e9e9e;
      }

      .drop-zone--has-file .drop-icon {
        color: #388e3c;
      }

      .drop-zone--invalid .drop-icon {
        color: #c62828;
      }

      .drop-primary {
        margin: 0;
        font-size: 15px;
        font-weight: 500;
        color: var(--colour-text-primary);
      }

      .drop-secondary {
        margin: 0;
        font-size: 13px;
        color: var(--colour-text-secondary);
      }

      .file-name {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      /* ── Progress ── */
      .progress-wrapper {
        margin-top: 16px;
      }

      .progress-label {
        font-size: 13px;
        color: #555;
        margin: 6px 0 0;
        text-align: right;
      }

      /* ── Feedback banners ── */
      .feedback {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 16px;
        border-radius: 8px;
        margin-top: 16px;
        font-size: 14px;
        line-height: 1.5;
      }

      .feedback mat-icon {
        flex-shrink: 0;
        margin-top: 2px;
      }

      .feedback--success {
        background: #e8f5e9;
        color: #1b5e20;
      }

      .feedback--warning {
        background: #fff8e1;
        color: #6d4c10;
      }

      .feedback--error {
        background: #ffebee;
        color: #b71c1c;
      }

      .feedback-body {
        flex: 1;
      }

      .feedback-title {
        font-weight: 600;
        margin: 0 0 4px;
      }

      .feedback-body p {
        margin: 0 0 4px;
      }

      .error-list {
        margin: 6px 0 0 16px;
        padding: 0;
        font-size: 13px;
      }

      /* ── Upload actions ── */
      .upload-actions {
        justify-content: flex-end;
      }

      /* ── History ── */
      .history-loading {
        padding: 8px 0;
      }

      .loading-label {
        font-size: 13px;
        color: #757575;
        margin: 6px 0 0;
      }

      .empty-history {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 24px 0;
        color: #9e9e9e;
        font-size: 14px;
        text-align: center;
      }

      .empty-history mat-icon {
        font-size: 40px;
        width: 40px;
        height: 40px;
      }

      .empty-history p {
        margin: 0;
      }

      .table-wrapper {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
      }

      .history-table {
        width: 100%;
        font-size: 13px;
      }

      .filename-cell {
        display: inline-block;
        max-width: 180px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        vertical-align: middle;
      }

      /* Status chips */
      .status-chip {
        font-size: 12px;
        font-weight: 500;
        height: 24px;
        min-height: 24px;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        border-radius: var(--radius-pill);
        padding: 0 10px;
        cursor: default;
      }

      .chip-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }

      .status-chip--success {
        background: #e8f5e9;
        color: #1b5e20;
      }

      .status-chip--partial {
        background: #fff8e1;
        color: #6d4c10;
      }

      .status-chip--failed {
        background: #ffebee;
        color: #b71c1c;
      }

      @media (max-width: 600px) {
        .import-container {
          padding: 8px;
        }
      }
    `,
  ],
})
export class ImportComponent implements OnInit {
  @ViewChild("fileInput") fileInputRef!: ElementRef<HTMLInputElement>;

  private importService = inject(ImportService);

  // File selection state
  selectedFile: File | null = null;
  validationError: string | null = null;

  // Upload state
  uploadState: UploadState = "idle";
  uploadProgress: UploadProgress = { percent: 0, loaded: 0, total: 0 };
  importResult: ImportResult | null = null;
  importErrorMessage = "";

  // Template download
  isDownloading = false;

  // History
  history: ImportHistoryItem[] = [];
  historyLoading = false;
  historyError: string | null = null;
  readonly historyColumns = [
    "imported_at",
    "filename",
    "imported_count",
    "skipped_count",
    "error_count",
    "status",
  ];

  ngOnInit(): void {
    this.loadHistory();
  }

  triggerFilePicker(): void {
    this.fileInputRef.nativeElement.click();
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;

    // Reset input so re-selecting the same file fires the event again
    input.value = "";

    if (!file) return;

    this.selectedFile = file;
    this.validationError = this.importService.validateFile(file);

    // Reset any previous result when a new file is chosen
    this.uploadState = "idle";
    this.importResult = null;
    this.importErrorMessage = "";
  }

  clearSelection(): void {
    this.selectedFile = null;
    this.validationError = null;
    this.uploadState = "idle";
    this.importResult = null;
    this.importErrorMessage = "";
    this.uploadProgress = { percent: 0, loaded: 0, total: 0 };
  }

  uploadFile(): void {
    if (!this.selectedFile || this.validationError) return;

    this.uploadState = "uploading";
    this.uploadProgress = {
      percent: 0,
      loaded: 0,
      total: this.selectedFile.size,
    };
    this.importResult = null;
    this.importErrorMessage = "";

    this.importService
      .uploadFile(this.selectedFile)
      .pipe(filter((event) => event !== null && event !== undefined))
      .subscribe({
        next: (event) => {
          if (!event) return;
          if (event.type === "progress") {
            this.uploadProgress = event.progress;
          } else if (event.type === "result") {
            this.importResult = event.result;
            // Map backend 'failed' status to local 'error' UI state
            if (event.result.status === "failed") {
              this.uploadState = "error";
              this.importErrorMessage =
                event.result.message || "Import failed.";
            } else {
              this.uploadState = event.result.status;
            }
            if (
              this.uploadState === "success" ||
              this.uploadState === "partial"
            ) {
              this.loadHistory();
            }
          }
        },
        error: (err: Error) => {
          this.uploadState = "error";
          this.importErrorMessage =
            err.message || "Upload failed. Please try again.";
        },
      });
  }

  downloadTemplate(): void {
    this.isDownloading = true;
    this.importService.downloadTemplate().subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "ai_diary_import_template.xlsx";
        link.click();
        URL.revokeObjectURL(url);
        this.isDownloading = false;
      },
      error: () => {
        this.isDownloading = false;
        // Template download failure is non-critical; user can still proceed
      },
    });
  }

  loadHistory(): void {
    this.historyLoading = true;
    this.historyError = null;

    this.importService.getHistory().subscribe({
      next: (items) => {
        this.history = items;
        this.historyLoading = false;
      },
      error: (err: Error) => {
        this.historyError = err.message || "Unable to load import history.";
        this.historyLoading = false;
      },
    });
  }

  // ── Formatting helpers ──

  formatFileSize(bytes: number): string {
    if (bytes === 0) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  formatDate(isoString: string): string {
    if (!isoString) return "—";
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  }

  statusIcon(status: ImportHistoryItem["status"]): string {
    const icons: Record<ImportHistoryItem["status"], string> = {
      success: "check_circle",
      partial: "warning_amber",
      failed: "cancel",
    };
    return icons[status] ?? "help_outline";
  }

  statusLabel(status: ImportHistoryItem["status"]): string {
    const labels: Record<ImportHistoryItem["status"], string> = {
      success: "Success",
      partial: "Partial",
      failed: "Failed",
    };
    return labels[status] ?? status;
  }
}
