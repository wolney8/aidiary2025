// Import component — full UX journey: template download → file selection → upload → result feedback

import { animate, style, transition, trigger } from "@angular/animations";
import { CommonModule } from "@angular/common";
import {
  Component,
  type ElementRef,
  HostListener,
  inject,
  type OnInit,
  ViewChild,
} from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatChipsModule } from "@angular/material/chips";
import { MatDividerModule } from "@angular/material/divider";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatTableModule } from "@angular/material/table";
import { MatTooltipModule } from "@angular/material/tooltip";
import { filter } from "rxjs/operators";
import { AppDialogService } from "../../core/services/app-dialog.service";
import {
  type ImportHistoryItem,
  type ImportResult,
  ImportService,
  type UploadProgress,
} from "../../core/services/import.service";
import { formatReadableLongDate } from "../../shared/utils/date-display";

type UploadState =
  | "idle"
  | "uploading"
  | "processing"
  | "review"
  | "success"
  | "partial"
  | "empty"
  | "error";

@Component({
  selector: "app-import",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatCheckboxModule,
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
      accept=".xlsx,.zip"
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
            Get the Excel template, fill it with your entries, then upload a
            workbook or full export package below.
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <p class="hint-text">
            The template contains separate sheets for <strong>Daily</strong> and
            <strong>Dream</strong> entries with all required columns
            pre-defined. You can also import a full .zip export package to
            restore bundled entry images.
          </p>

          <div
            *ngIf="templateDownloadError"
            class="feedback feedback--error"
            role="alert"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">error_outline</mat-icon>
            <span>{{ templateDownloadError }}</span>
          </div>
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
            Select your completed workbook or export package (.xlsx or
            .zip, max 50 MB).
          </mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <!-- Drop-zone / file selector -->
          <div
            class="drop-zone"
            [class.drop-zone--has-file]="selectedFile && !validationError"
            [class.drop-zone--invalid]="!!validationError"
            [class.drop-zone--dragging]="isDragging"
            role="button"
            tabindex="0"
            aria-label="Choose a workbook or export package for import"
            [attr.aria-describedby]="validationError ? validationErrorId : null"
            (click)="triggerFilePicker()"
            (keydown.enter)="triggerFilePicker()"
            (keydown.space)="triggerFilePicker()"
            (dragover)="onDragOver($event)"
            (dragleave)="onDragLeave()"
            (drop)="onDrop($event)"
          >
            <mat-icon class="drop-icon" aria-hidden="true">
              {{ selectedFile && !validationError ? "task" : "upload_file" }}
            </mat-icon>

            <ng-container *ngIf="!selectedFile; else fileSelected">
              <p class="drop-primary">Click to choose a file</p>
              <p class="drop-secondary">
                Accepts .xlsx and .zip — maximum 50 MB
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
            [id]="validationErrorId"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">error_outline</mat-icon>
            <span>{{ validationError }}</span>
          </div>

          <!-- Upload progress bar -->
          <div
            *ngIf="uploadState === 'uploading' || uploadState === 'processing'"
            class="progress-wrapper"
            role="status"
            aria-live="polite"
            [@fadeSlideIn]
          >
            <mat-progress-bar
              *ngIf="uploadState === 'uploading'"
              mode="determinate"
              [value]="uploadProgress.percent"
              aria-label="Upload progress"
            ></mat-progress-bar>
            <p class="progress-label" *ngIf="uploadState === 'uploading'">
              Uploading… {{ uploadProgress.percent }}% ({{
                formatFileSize(uploadProgress.loaded)
              }}
              of {{ formatFileSize(uploadProgress.total) }})
            </p>
            <div class="processing-indicator" *ngIf="uploadState === 'processing'">
              <div class="processing-spinner" aria-hidden="true"></div>
              <p class="processing-title">This may take a moment…</p>
              <p class="processing-copy">{{ getProcessingStatusMessage() }}</p>
            </div>
          </div>

          <!-- Result feedback — review required -->
          <div
            *ngIf="uploadState === 'review'"
            class="feedback feedback--warning"
            role="alert"
            aria-live="assertive"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">rule</mat-icon>
            <div class="feedback-body">
              <p class="feedback-title">Duplicate review required</p>
              <p>
                {{ importResult!.ready_daily ?? 0 }} daily and
                {{ importResult!.ready_dreams ?? 0 }} dream entries are ready to
                import.
              </p>
              <p>
                {{ getDuplicateCount(importResult!) }} duplicate
                {{ getDuplicateCount(importResult!) === 1 ? "entry" : "entries" }}
                need your decision before anything is imported.
              </p>
              <p *ngIf="importResult!.warnings && importResult!.warnings!.length">
                <strong>Warnings:</strong>
                {{ importResult!.warnings!.join("; ") }}
              </p>
              <div class="review-actions">
                <button
                  mat-stroked-button
                  type="button"
                  (click)="openDuplicateReview()"
                >
                  <mat-icon>table_view</mat-icon>
                  Show duplicates
                </button>
              </div>
            </div>
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
              <p *ngIf="shouldShowTypeBreakdown(importResult!)">
                Daily: {{ importResult!.inserted_daily ?? 0 }} inserted,
                {{ importResult!.skipped_daily ?? 0 }} skipped — Dreams:
                {{ importResult!.inserted_dreams ?? 0 }} inserted,
                {{ importResult!.skipped_dreams ?? 0 }} skipped
              </p>
              <p *ngIf="importResult!.warnings && importResult!.warnings!.length">
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
              <p *ngIf="shouldShowTypeBreakdown(importResult!)">
                Daily: {{ importResult!.inserted_daily ?? 0 }} inserted,
                {{ importResult!.skipped_daily ?? 0 }} skipped — Dreams:
                {{ importResult!.inserted_dreams ?? 0 }} inserted,
                {{ importResult!.skipped_dreams ?? 0 }} skipped
              </p>
              <p *ngIf="importResult!.warnings && importResult!.warnings!.length">
                <strong>Warnings:</strong>
                {{ importResult!.warnings!.join("; ") }}
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

          <!-- Result feedback — empty file -->
          <div
            *ngIf="uploadState === 'empty'"
            class="feedback feedback--info"
            role="status"
            aria-live="polite"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">info</mat-icon>
            <div class="feedback-body">
              <p class="feedback-title">No entries found</p>
              <p>
                No entries were found in this file. Please check the file has
                data rows.
              </p>
            </div>
          </div>
        </mat-card-content>

        <mat-card-actions class="upload-actions">
          <button
            mat-stroked-button
            (click)="clearSelection()"
            [disabled]="
              !selectedFile ||
              uploadState === 'uploading' ||
              uploadState === 'processing' ||
              isCommittingReview
            "
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
              !selectedFile ||
              !!validationError ||
              uploadState === 'uploading' ||
              uploadState === 'processing' ||
              uploadState === 'review' ||
              isCommittingReview
            "
            aria-label="Upload selected file and import entries"
          >
            <mat-icon>cloud_upload</mat-icon>
            {{
              uploadState === "uploading"
                ? "Uploading…"
                : uploadState === "processing"
                  ? "Processing…"
                  : "Import Entries"
            }}
          </button>
        </mat-card-actions>
      </mat-card>

      <div
        *ngIf="isDuplicateModalOpen && importResult"
        class="duplicate-modal-backdrop"
        role="presentation"
        (click)="closeDuplicateReview()"
      >
        <div
          class="duplicate-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="duplicate-review-title"
          (click)="$event.stopPropagation()"
        >
          <div class="duplicate-modal__header">
            <div>
              <h3 id="duplicate-review-title">Review duplicate entries</h3>
              <p>
                Nothing will be imported until you confirm this review.
              </p>
            </div>
            <button
              mat-icon-button
              type="button"
              aria-label="Close duplicate review"
              (click)="closeDuplicateReview()"
            >
              <mat-icon>close</mat-icon>
            </button>
          </div>

          <div class="duplicate-modal__table-wrapper">
            <table class="duplicate-table">
              <thead>
                <tr>
                  <th scope="col">Include</th>
                  <th scope="col">Date</th>
                  <th scope="col">Type</th>
                  <th scope="col">Title</th>
                  <th scope="col">Preview</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let duplicate of importResult.duplicate_entries ?? []">
                  <td>
                    <mat-checkbox
                      [checked]="isDuplicateSelected(duplicate.row_id)"
                      (change)="toggleDuplicateSelection(duplicate.row_id, $event.checked)"
                      [aria-label]="'Include duplicate ' + duplicate.title"
                    ></mat-checkbox>
                  </td>
                  <td>{{ formatDuplicateDate(duplicate.entry_date) }}</td>
                  <td>{{ duplicate.entry_type === "daily" ? "Daily" : "Dream" }}</td>
                  <td>{{ duplicate.title }}</td>
                  <td>{{ duplicate.content_preview || "—" }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="duplicate-modal__footer">
            <button
              mat-stroked-button
              type="button"
              (click)="commitReviewedImport(false)"
              [disabled]="isCommittingReview"
            >
              Accept and import without duplicates
            </button>
            <button
              mat-raised-button
              color="warn"
              type="button"
              (click)="commitReviewedImport(true)"
              [disabled]="isCommittingReview"
            >
              {{
                isCommittingReview
                  ? "Importing…"
                  : "Accept and import with " + selectedDuplicateRowIds.size + " duplicates"
              }}
            </button>
          </div>
        </div>
      </div>

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
            aria-live="polite"
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

              <!-- Status column -->
              <ng-container matColumnDef="status">
                <th mat-header-cell *matHeaderCellDef scope="col">Status</th>
                <td mat-cell *matCellDef="let row">
                  <span
                    [class]="'status-chip status-chip--' + row.status"
                    role="status"
                    [attr.aria-label]="
                      'Import status: ' + statusLabel(row.status)
                    "
                  >
                    <mat-icon class="chip-icon" aria-hidden="true">{{
                      statusIcon(row.status)
                    }}</mat-icon>
                    {{ statusLabel(row.status) }}
                  </span>
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

      .drop-zone--dragging {
        border-color: #1565c0;
        background-color: rgba(21, 101, 192, 0.08);
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

      .processing-indicator {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.45rem;
        padding: 1rem 0 0.15rem;
        text-align: center;
      }

      .processing-spinner {
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        border: 3px solid rgba(99, 102, 241, 0.18);
        border-top-color: var(--colour-primary);
        animation: import-processing-spin 900ms linear infinite;
      }

      .processing-title {
        margin: 0;
        font-weight: 700;
        color: var(--colour-text-primary);
      }

      .processing-copy {
        margin: 0;
        font-size: 0.92rem;
        color: var(--colour-text-secondary);
      }

      @keyframes import-processing-spin {
        from {
          transform: rotate(0deg);
        }

        to {
          transform: rotate(360deg);
        }
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

      .feedback--info {
        background: #e3f2fd;
        color: #0d47a1;
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

      .review-actions {
        margin-top: 10px;
      }

      .duplicate-modal-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(15, 23, 42, 0.52);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 24px;
        z-index: 1200;
      }

      .duplicate-modal {
        width: min(980px, 100%);
        max-height: min(80vh, 720px);
        overflow: hidden;
        display: flex;
        flex-direction: column;
        background: #fffef8;
        border-radius: 18px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        box-shadow: 0 28px 60px rgba(15, 23, 42, 0.24);
      }

      .duplicate-modal__header,
      .duplicate-modal__footer {
        padding: 18px 20px;
        background: #fffdf4;
      }

      .duplicate-modal__header {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: flex-start;
        border-bottom: 1px solid rgba(148, 163, 184, 0.24);
      }

      .duplicate-modal__header h3 {
        margin: 0 0 6px;
      }

      .duplicate-modal__header p {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .duplicate-modal__table-wrapper {
        overflow: auto;
        padding: 0 20px 20px;
      }

      .duplicate-table {
        width: 100%;
        border-collapse: collapse;
      }

      .duplicate-table th,
      .duplicate-table td {
        padding: 12px 10px;
        text-align: left;
        vertical-align: top;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
      }

      .duplicate-table th {
        position: sticky;
        top: 0;
        background: #fffef8;
        z-index: 1;
      }

      .duplicate-modal__footer {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        border-top: 1px solid rgba(148, 163, 184, 0.24);
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

      .status-chip--empty {
        background: #e3f2fd;
        color: #0d47a1;
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
  private appDialog = inject(AppDialogService);

  // File selection state
  selectedFile: File | null = null;
  isDragging = false;
  validationError: string | null = null;
  readonly validationErrorId = "import-validation-error";

  // Upload state
  uploadState: UploadState = "idle";
  uploadProgress: UploadProgress = { percent: 0, loaded: 0, total: 0 };
  importResult: ImportResult | null = null;
  importErrorMessage = "";
  importSessionId: string | null = null;
  isDuplicateModalOpen = false;
  isCommittingReview = false;
  selectedDuplicateRowIds = new Set<string>();
  private processingMessageIndex = 0;
  private processingMessageTimerId: number | null = null;
  private readonly processingMessages = [
    "Setting up the analysis engine…",
    "Reading files…",
    "Preparing images and package data…",
    "Comparing entries and checking duplicates…",
    "Uploading to database…",
  ];

  // Template download
  isDownloading = false;
  templateDownloadError: string | null = null;

  // History
  history: ImportHistoryItem[] = [];
  historyLoading = false;
  historyError: string | null = null;
  readonly historyColumns = [
    "imported_at",
    "filename",
    "imported_count",
    "skipped_count",
    "status",
  ];

  ngOnInit(): void {
    this.loadHistory();
  }

  canDeactivate(): boolean | Promise<boolean> {
    if (!this.hasPendingReview()) {
      return true;
    }
    return this.appDialog.confirm({
      title: "Leave import review?",
      message:
        "This import review will be cancelled and lost if you leave now.",
      confirmText: "Leave review",
      cancelText: "Stay here",
      variant: "danger",
    });
  }

  @HostListener("window:beforeunload", ["$event"])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (!this.hasPendingReview()) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  }

  triggerFilePicker(): void {
    this.fileInputRef.nativeElement.click();
  }

  async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;

    // Reset input so re-selecting the same file fires the event again
    input.value = "";

    if (!file) return;
    await this.applySelectedFile(file);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  onDragLeave(): void {
    this.isDragging = false;
  }

  async onDrop(event: DragEvent): Promise<void> {
    event.preventDefault();
    this.isDragging = false;
    const file = event.dataTransfer?.files?.[0] ?? null;
    if (!file) return;
    await this.applySelectedFile(file);
  }

  async clearSelection(): Promise<void> {
    if (!(await this.confirmResetPendingReview())) {
      return;
    }
    this.resetImportState();
  }

  uploadFile(): void {
    if (!this.selectedFile || this.validationError) return;

    this.stopProcessingIndicator();
    this.uploadState = "uploading";
    this.uploadProgress = {
      percent: 0,
      loaded: 0,
      total: this.selectedFile.size,
    };
    this.importResult = null;
    this.importErrorMessage = "";
    this.importSessionId = null;
    this.isDuplicateModalOpen = false;
    this.selectedDuplicateRowIds.clear();

    this.importService
      .uploadFile(this.selectedFile)
      .pipe(filter((event) => event !== null && event !== undefined))
      .subscribe({
        next: (event) => {
          if (!event) return;
          if (event.type === "progress") {
            this.uploadProgress = event.progress;
            if (
              event.progress.total > 0 &&
              event.progress.loaded >= event.progress.total &&
              this.uploadState === "uploading"
            ) {
              this.startProcessingIndicator();
            }
          } else if (event.type === "result") {
            this.stopProcessingIndicator();
            this.importResult = event.result;
            const resultStatus = event.result.status;
            this.importSessionId = event.result.import_session_id ?? null;
            // Map backend 'failed' status to local 'error' UI state
            if (resultStatus === "failed") {
              this.uploadState = "error";
              this.importErrorMessage =
                event.result.message || "Import failed.";
            } else {
              this.uploadState = resultStatus;
            }
            if (this.shouldRefreshHistory(resultStatus)) {
              this.loadHistory();
            }
          }
        },
        error: (err: Error) => {
          this.stopProcessingIndicator();
          this.uploadState = "error";
          this.importErrorMessage =
            err.message || "Upload failed. Please try again.";
        },
      });
  }

  downloadTemplate(): void {
    this.templateDownloadError = null;
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
        this.templateDownloadError = null;
      },
      error: () => {
        this.isDownloading = false;
        this.templateDownloadError =
          "Could not download the import template. Please check that the backend service is running and try again.";
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
      return d.toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      });
    } catch {
      return isoString;
    }
  }

  private shouldRefreshHistory(status: ImportResult["status"]): boolean {
    return status === "success" || status === "partial" || status === "empty";
  }

  statusIcon(status: ImportHistoryItem["status"]): string {
    const icons: Record<ImportHistoryItem["status"], string> = {
      success: "check_circle",
      partial: "warning_amber",
      failed: "cancel",
      empty: "info",
    };
    return icons[status] ?? "help_outline";
  }

  statusLabel(status: ImportHistoryItem["status"]): string {
    const labels: Record<ImportHistoryItem["status"], string> = {
      success: "Success",
      partial: "Partial",
      failed: "Failed",
      empty: "Empty",
    };
    return labels[status] ?? status;
  }

  shouldShowTypeBreakdown(result: ImportResult): boolean {
    const hasSplitData =
      result.inserted_daily !== undefined ||
      result.inserted_dreams !== undefined;
    return hasSplitData && result.imported_count > 0;
  }

  formatDuplicateDate(value: string): string {
    return formatReadableLongDate(value) || value;
  }

  private async applySelectedFile(file: File): Promise<void> {
    if (!(await this.confirmResetPendingReview())) {
      return;
    }
    this.selectedFile = file;
    this.validationError = this.importService.validateFile(file);

    // Reset any previous result when a new file is chosen
    this.resetImportFeedback();
  }

  getDuplicateCount(result: ImportResult): number {
    return (result.duplicate_entries?.length ?? 0) || 0;
  }

  openDuplicateReview(): void {
    this.isDuplicateModalOpen = true;
  }

  closeDuplicateReview(): void {
    this.isDuplicateModalOpen = false;
  }

  toggleDuplicateSelection(rowId: string, checked: boolean): void {
    if (checked) {
      this.selectedDuplicateRowIds.add(rowId);
      return;
    }
    this.selectedDuplicateRowIds.delete(rowId);
  }

  isDuplicateSelected(rowId: string): boolean {
    return this.selectedDuplicateRowIds.has(rowId);
  }

  commitReviewedImport(includeSelectedDuplicates: boolean): void {
    if (!this.importSessionId) {
      return;
    }

    this.isCommittingReview = true;
    const acceptedDuplicateRowIds = includeSelectedDuplicates
      ? Array.from(this.selectedDuplicateRowIds)
      : [];

    this.importService
      .commitImportSession(this.importSessionId, acceptedDuplicateRowIds)
      .subscribe({
        next: (result) => {
          this.stopProcessingIndicator();
          this.importResult = result;
          this.uploadState = result.status === "failed" ? "error" : result.status;
          this.importSessionId = null;
          this.isDuplicateModalOpen = false;
          this.selectedDuplicateRowIds.clear();
          this.isCommittingReview = false;
          if (this.shouldRefreshHistory(result.status)) {
            this.loadHistory();
          }
        },
        error: (err: Error) => {
          this.stopProcessingIndicator();
          this.isCommittingReview = false;
          this.uploadState = "error";
          this.importErrorMessage =
            err.message || "Import commit failed. Please try again.";
        },
      });
  }

  private hasPendingReview(): boolean {
    return this.uploadState === "review" && !!this.importSessionId;
  }

  private confirmResetPendingReview(): boolean | Promise<boolean> {
    if (!this.hasPendingReview()) {
      return true;
    }
    return this.appDialog.confirm({
      title: "Discard current import review?",
      message:
        "The current import review will be cancelled and lost if you continue.",
      confirmText: "Discard review",
      cancelText: "Keep reviewing",
      variant: "danger",
    });
  }

  private resetImportFeedback(): void {
    this.stopProcessingIndicator();
    this.uploadState = "idle";
    this.importResult = null;
    this.importErrorMessage = "";
    this.importSessionId = null;
    this.isDuplicateModalOpen = false;
    this.selectedDuplicateRowIds.clear();
  }

  private resetImportState(): void {
    this.selectedFile = null;
    this.isDragging = false;
    this.validationError = null;
    this.resetImportFeedback();
    this.uploadProgress = { percent: 0, loaded: 0, total: 0 };
  }

  getProcessingStatusMessage(): string {
    return (
      this.processingMessages[this.processingMessageIndex] ??
      "Working on your import…"
    );
  }

  private startProcessingIndicator(): void {
    if (this.uploadState === "processing") {
      return;
    }
    this.uploadState = "processing";
    this.processingMessageIndex = 0;
    if (this.processingMessageTimerId !== null) {
      window.clearInterval(this.processingMessageTimerId);
    }
    this.processingMessageTimerId = window.setInterval(() => {
      this.processingMessageIndex =
        (this.processingMessageIndex + 1) % this.processingMessages.length;
    }, 1800);
  }

  private stopProcessingIndicator(): void {
    this.processingMessageIndex = 0;
    if (this.processingMessageTimerId !== null) {
      window.clearInterval(this.processingMessageTimerId);
      this.processingMessageTimerId = null;
    }
  }
}
