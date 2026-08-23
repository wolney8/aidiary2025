// Import component — full UX journey: template download → file selection → upload → result feedback

import { animate, style, transition, trigger } from "@angular/animations";
import { CommonModule } from "@angular/common";
import { A11yModule } from "@angular/cdk/a11y";
import {
  Component,
  DestroyRef,
  type ElementRef,
  HostListener,
  inject,
  type OnInit,
  ViewChild,
} from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatChipsModule } from "@angular/material/chips";
import { MatDividerModule } from "@angular/material/divider";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatSelectModule } from "@angular/material/select";
import { MatTableModule } from "@angular/material/table";
import { MatTooltipModule } from "@angular/material/tooltip";
import { filter } from "rxjs/operators";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { ImportJobService } from "../../core/services/import-job.service";
import {
  type ImportHistoryItem,
  type ImportResult,
  type ImportReviewEntry,
  type ImportSource,
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
    A11yModule,
    MatCardModule,
    MatButtonModule,
    MatCheckboxModule,
    MatIconModule,
    MatProgressBarModule,
    MatSelectModule,
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
      [accept]="acceptedFileTypes"
      class="sr-only"
      aria-hidden="true"
      tabindex="-1"
      (change)="onFileSelected($event)"
    />

    <div class="import-container" role="main" aria-label="Import entries" data-testid="import-settings-page">
      <mat-card class="step-card source-card" data-testid="import-source-card">
        <mat-card-header>
          <mat-icon mat-card-avatar class="step-icon">move_to_inbox</mat-icon>
          <mat-card-title>Choose your import source</mat-card-title>
          <mat-card-subtitle>Select the format that created your file.</mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="source-options" aria-label="Import source">
            <button
              type="button"
              class="source-option"
              [class.source-option--selected]="importSource === 'aidiary'"
              [attr.aria-pressed]="importSource === 'aidiary'"
              [disabled]="isImportSourceLocked()"
              (click)="changeImportSource('aidiary')"
              data-testid="import-source-openmynd"
            >
              <span class="source-option__icon" aria-hidden="true">
                <mat-icon>description</mat-icon>
              </span>
              <span class="source-option__copy">
                <strong>Internal XLSX</strong>
              </span>
              <mat-icon class="source-option__check" aria-hidden="true">
                {{ importSource === "aidiary" ? "check_circle" : "radio_button_unchecked" }}
              </mat-icon>
            </button>

            <button
              type="button"
              class="source-option"
              [class.source-option--selected]="importSource === 'daylio'"
              [attr.aria-pressed]="importSource === 'daylio'"
              [disabled]="isImportSourceLocked()"
              (click)="changeImportSource('daylio')"
              data-testid="import-source-daylio"
            >
              <span class="source-option__icon" aria-hidden="true">
                  <mat-icon>mood</mat-icon>
              </span>
              <span class="source-option__copy">
                <strong>Daylio</strong>
              </span>
              <mat-icon class="source-option__check" aria-hidden="true">
                {{ importSource === "daylio" ? "check_circle" : "radio_button_unchecked" }}
              </mat-icon>
            </button>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- ── Step 1: Download Template ── -->
      <mat-card class="step-card" *ngIf="importSource === 'aidiary'" data-testid="import-template-card">
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
            restore supported entry data, bundled images, and attachments.
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
      <mat-card class="step-card" data-testid="import-upload-card">
        <mat-card-header>
          <mat-icon mat-card-avatar class="step-icon">upload_file</mat-icon>
          <mat-card-title>{{ uploadCardTitle }}</mat-card-title>
          <mat-card-subtitle>
            {{ uploadSourceDescription }}
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
            [attr.aria-label]="filePickerLabel"
            [attr.aria-describedby]="validationError ? validationErrorId : null"
            data-testid="import-file-picker"
            (click)="triggerFilePicker()"
            (keydown.enter)="triggerFilePicker()"
            (keydown.space)="$event.preventDefault(); triggerFilePicker()"
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
                {{ acceptedFileDescription }}
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

          <ng-container *ngIf="importJob$ | async as job">
            <div
              *ngIf="job.status === 'queued' || job.status === 'running'"
              class="background-import-progress"
              role="status"
              aria-live="polite"
              [@fadeSlideIn]
            >
              <div class="processing-spinner" aria-hidden="true"></div>
              <div class="background-import-progress__body">
                <p class="feedback-title">Import running in the background</p>
                <p>{{ job.message }}</p>
                <mat-progress-bar
                  mode="determinate"
                  [value]="job.percent"
                  aria-label="Background import progress"
                ></mat-progress-bar>
                <p class="background-import-progress__hint">
                  You can continue browsing. Progress is available from the notification bell.
                </p>
                <p *ngIf="job.is_delayed" class="background-import-progress__warning">
                  This is taking longer than expected. The import is still being monitored.
                </p>
              </div>
            </div>
          </ng-container>

          <!-- Result feedback — review required -->
          <div
            *ngIf="uploadState === 'review'"
            class="feedback feedback--success"
            role="status"
            aria-live="polite"
            [@fadeSlideIn]
          >
            <mat-icon aria-hidden="true">task_alt</mat-icon>
            <div class="feedback-body">
              <p class="feedback-title">File ready to review</p>
              <p *ngIf="getDuplicateCount(importResult!) > 0">
                {{ importResult!.ready_daily ?? 0 }} daily and
                {{ importResult!.ready_dreams ?? 0 }} dream entries are ready to
                import.
              </p>
              <p>
                {{ getDuplicateCount(importResult!) }} duplicate
                {{ getDuplicateCount(importResult!) === 1 ? "entry" : "entries" }}
                need your decision before anything is imported.
              </p>
              <p *ngIf="getDuplicateCount(importResult!) > 0">
                A duplicate has the same type, date, time, title, and entry text.
                Other entries from the same day remain available to import.
              </p>
              <p *ngIf="importResult!.warnings && importResult!.warnings!.length">
                <strong>Warnings:</strong>
                {{ importResult!.warnings!.join("; ") }}
              </p>
              <div class="review-actions">
                <button
                  mat-stroked-button
                  type="button"
                  data-testid="import-review-open"
                  (click)="openDuplicateReview()"
                >
                  <mat-icon>table_view</mat-icon>
                  Review entries
                </button>
                <button mat-button type="button" (click)="removePendingImport()">
                  <mat-icon>delete_outline</mat-icon>
                  Remove
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
              isCommittingReview ||
              isBackgroundImportActive
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
              isCommittingReview ||
              isBackgroundImportActive
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
        data-testid="import-review-backdrop"
        role="presentation"
        (click)="closeDuplicateReview()"
      >
        <div
          class="duplicate-modal"
          data-testid="import-review-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="duplicate-review-title"
          cdkTrapFocus
          [cdkTrapFocusAutoCapture]="true"
          (keydown.escape)="closeDuplicateReview()"
          (click)="$event.stopPropagation()"
        >
          <div class="duplicate-modal__header">
            <div>
              <h3 id="duplicate-review-title">Review entries before import</h3>
              <p>
                Nothing will be imported until you confirm this review.
              </p>
              <p>
                Matching type, date, time, title, and entry text are marked as
                duplicates. Other same-day entries are allowed.
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

          <div
            #reviewTableWrapper
            class="duplicate-modal__table-wrapper"
            data-testid="import-review-table-wrapper"
          >
            <div class="review-selection-bar" data-testid="import-review-selection-bar">
              <button mat-stroked-button type="button" (click)="selectAllReviewEntries()" data-testid="import-review-select-all">
                Select all
              </button>
              <button mat-stroked-button type="button" (click)="clearReviewSelection()" data-testid="import-review-clear-all">
                Clear all
              </button>
              <span aria-live="polite">{{ selectedReviewRowIds.size }} of {{ importResult.review_entries?.length ?? 0 }} selected</span>
            </div>
            <div class="review-pagination review-pagination--top" *ngIf="reviewPageCount > 1">
              <button mat-icon-button type="button" (click)="changeReviewPage(-1)" [disabled]="reviewPage === 0" aria-label="Previous review page"><mat-icon>chevron_left</mat-icon></button>
              <span>Page {{ reviewPage + 1 }} of {{ reviewPageCount }}</span>
              <button mat-icon-button type="button" (click)="changeReviewPage(1)" [disabled]="reviewPage + 1 >= reviewPageCount" aria-label="Next review page"><mat-icon>chevron_right</mat-icon></button>
            </div>
            <table class="duplicate-table" data-testid="import-review-table">
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
                <tr *ngFor="let duplicate of paginatedReviewEntries">
                  <td>
                    <mat-checkbox
                      [checked]="isReviewEntrySelected(duplicate.row_id)"
                      (change)="toggleReviewSelection(duplicate.row_id, $event.checked)"
                      [aria-label]="'Include ' + duplicate.title"
                    ></mat-checkbox>
                  </td>
                  <td>{{ formatDuplicateDate(duplicate.entry_date) }}</td>
                  <td>
                    <mat-select
                      *ngIf="canChangeReviewEntryType(duplicate); else fixedReviewType"
                      class="review-type-select"
                      [value]="getReviewEntryType(duplicate)"
                      (selectionChange)="setReviewEntryType(duplicate.row_id, $event.value)"
                      [attr.aria-label]="'Entry type for ' + duplicate.title"
                    >
                      <mat-option value="daily">Daily entry</mat-option>
                      <mat-option value="dream">Dream entry</mat-option>
                    </mat-select>
                    <ng-template #fixedReviewType>
                      <span class="fixed-review-type">{{ formatReviewEntryType(duplicate.entry_type) }}</span>
                    </ng-template>
                    <span *ngIf="duplicate.is_duplicate" class="duplicate-label">Duplicate</span>
                    <span *ngIf="duplicate.source_record_kind === 'mood_checkin'" class="mood-checkin-label">Mood check-in</span>
                  </td>
                  <td>
                    <span class="review-title" [class]="'review-title mood-' + getMoodTone(duplicate.mood)">
                      <mat-icon aria-hidden="true">{{ getMoodIcon(duplicate.mood) }}</mat-icon>
                      {{ duplicate.title }}
                    </span>
                  </td>
                  <td>{{ duplicate.content_preview || "—" }}</td>
                </tr>
              </tbody>
            </table>
            <div class="review-pagination" *ngIf="reviewPageCount > 1">
              <button mat-icon-button type="button" (click)="changeReviewPage(-1)" [disabled]="reviewPage === 0" aria-label="Previous review page"><mat-icon>chevron_left</mat-icon></button>
              <span>Page {{ reviewPage + 1 }} of {{ reviewPageCount }}</span>
              <button mat-icon-button type="button" (click)="changeReviewPage(1)" [disabled]="reviewPage + 1 >= reviewPageCount" aria-label="Next review page"><mat-icon>chevron_right</mat-icon></button>
              <button mat-stroked-button type="button" (click)="scrollReviewToTop()">
                <mat-icon>vertical_align_top</mat-icon>
                Back to top
              </button>
            </div>
          </div>

          <div class="duplicate-modal__footer">
            <button
              mat-stroked-button
              type="button"
              (click)="closeDuplicateReview()"
              [disabled]="isCommittingReview"
            >
              Continue reviewing later
            </button>
            <button
              mat-raised-button
              class="commit-import-action"
              data-testid="import-review-commit"
              type="button"
              (click)="commitReviewedImport()"
              [disabled]="isCommittingReview || selectedReviewRowIds.size === 0"
            >
              {{
                isCommittingReview
                  ? "Importing…"
                  : "Import " + selectedReviewRowIds.size + " selected records"
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

              <ng-container matColumnDef="actions">
                <th mat-header-cell *matHeaderCellDef scope="col">Actions</th>
                <td mat-cell *matCellDef="let row">
                  <button
                    mat-stroked-button
                    class="destructive-action"
                    type="button"
                    *ngIf="row.status !== 'reverted' && row.imported_count > 0"
                    [disabled]="revertingImportId === row.id"
                    (click)="revertImport(row)"
                  >
                    <mat-icon>undo</mat-icon>
                    {{ revertingImportId === row.id ? "Reverting…" : "Revert import" }}
                  </button>
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
        gap: var(--spacing-md);
      }

      .step-card {
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface);
      }

      .step-icon {
        color: var(--colour-primary);
      }

      mat-card-actions {
        padding: var(--spacing-xs) var(--spacing-md) var(--spacing-md);
        display: flex;
        gap: var(--spacing-xs);
        flex-wrap: wrap;
      }

      mat-card-actions button,
      .review-actions button,
      .review-pagination button,
      .review-selection-bar button,
      .commit-import-action {
        border-radius: var(--radius-pill);
        min-height: 44px;
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
        gap: var(--spacing-xs);
        border: 2px dashed var(--colour-border);
        border-radius: var(--radius-lg);
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
        border-color: var(--colour-primary);
        background-color: var(--colour-info-bg);
      }

      .drop-zone:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .drop-zone--has-file {
        border-color: var(--colour-success-text);
        background-color: var(--colour-success-bg);
      }

      .drop-zone--invalid {
        border-color: var(--colour-danger-text);
        background-color: var(--colour-danger-bg);
      }

      .drop-zone--dragging {
        border-color: var(--colour-info-text);
        background-color: var(--colour-info-bg);
      }

      .drop-icon {
        font-size: 48px;
        width: 48px;
        height: 48px;
        color: var(--colour-text-secondary);
      }

      .drop-zone--has-file .drop-icon {
        color: var(--colour-success-text);
      }

      .drop-zone--invalid .drop-icon {
        color: var(--colour-danger-text);
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
        color: var(--colour-text-secondary);
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
        border-radius: var(--radius-pill);
        border: 3px solid var(--colour-border);
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
        gap: var(--spacing-xs);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-lg);
        margin-top: 16px;
        font-size: 14px;
        line-height: 1.5;
      }

      .feedback mat-icon {
        flex-shrink: 0;
        margin-top: 2px;
      }

      .feedback--success {
        background: var(--colour-success-bg);
        color: var(--colour-success-text);
      }

      .feedback--warning {
        background: var(--colour-warning-bg);
        color: var(--colour-warning-text);
        border: 1px solid color-mix(in srgb, var(--colour-warning-text) 35%, transparent);
      }

      .feedback--error {
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
      }

      .feedback--info {
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
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
        background: var(--colour-overlay);
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
        background: var(--colour-surface-elevated);
        color: var(--colour-text-primary);
        border-radius: var(--radius-lg);
        border: 1px solid var(--colour-border);
        box-shadow: 0 28px 60px var(--colour-shadow-strong);
      }

      .duplicate-modal__header,
      .duplicate-modal__footer {
        padding: 18px 20px;
        background: var(--colour-surface-muted);
      }

      .duplicate-modal__header {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: flex-start;
        border-bottom: 1px solid var(--colour-border);
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

      .review-selection-bar,
      .review-pagination {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        padding-block: var(--spacing-sm);
      }

      .review-selection-bar span {
        margin-left: auto;
        color: var(--colour-text-secondary);
      }

      .review-pagination {
        justify-content: center;
      }

      .review-pagination--top {
        background: var(--colour-surface-elevated);
        border-block: 1px solid var(--colour-border);
      }

      .commit-import-action:not(:disabled) {
        background: var(--colour-success-text);
        color: var(--colour-on-primary);
      }

      .background-import-progress {
        display: flex;
        align-items: flex-start;
        gap: var(--spacing-md);
        margin-top: var(--spacing-md);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-info-text);
        border-radius: var(--radius-lg);
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
      }

      .background-import-progress__body {
        flex: 1;
        min-width: 0;
      }

      .background-import-progress__body p {
        margin: 0 0 var(--spacing-sm);
      }

      .background-import-progress__hint {
        color: var(--colour-text-secondary);
        font-size: 0.875rem;
      }

      .background-import-progress__warning {
        color: var(--colour-warning-text);
        font-weight: 600;
      }

      .duplicate-label {
        display: inline-flex;
        margin-left: var(--spacing-xs);
        padding: 0.1rem 0.5rem;
        border-radius: var(--radius-pill);
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
        font-size: 0.75rem;
        font-weight: 700;
      }

      .mood-checkin-label {
        display: inline-flex;
        margin-top: var(--spacing-xs);
        padding: 0.1rem 0.5rem;
        border-radius: var(--radius-pill);
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
        font-size: 0.75rem;
      }

      .review-type-select {
        min-width: 8.5rem;
      }

      .fixed-review-type {
        display: inline-flex;
        align-items: center;
        min-height: 32px;
        padding: 0 0.75rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
        color: var(--colour-text-primary);
        font-weight: 700;
      }

      .review-title {
        display: inline-flex;
        align-items: flex-start;
        gap: var(--spacing-xs);
      }

      .review-title mat-icon {
        flex: 0 0 auto;
        font-size: 1.25rem;
        width: 1.25rem;
        height: 1.25rem;
      }

      .review-title.mood-negative mat-icon {
        color: var(--colour-danger-text);
      }

      .review-title.mood-low mat-icon {
        color: var(--colour-warning-text);
      }

      .review-title.mood-positive mat-icon,
      .review-title.mood-high mat-icon {
        color: var(--colour-success-text);
      }

      .review-title.mood-neutral mat-icon {
        color: var(--colour-text-secondary);
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
        border-bottom: 1px solid var(--colour-border);
      }

      .duplicate-table th {
        position: sticky;
        top: 0;
        background: var(--colour-surface-elevated);
        color: var(--colour-text-primary);
        z-index: 2;
        box-shadow: 0 1px 0 var(--colour-border);
      }

      .duplicate-modal__footer {
        display: flex;
        justify-content: flex-end;
        gap: 12px;
        border-top: 1px solid var(--colour-border);
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

      .source-options {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: var(--spacing-md);
      }

      .source-option {
        box-sizing: border-box;
        width: 100%;
        min-height: 4rem;
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
        color: var(--colour-text-primary);
        text-align: left;
      }

      .source-option:hover:not(:disabled) {
        border-color: var(--colour-primary);
        background: var(--colour-surface-strong);
      }

      .source-option--selected {
        border-color: var(--colour-primary);
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
      }

      .source-option__icon {
        width: 2.5rem;
        height: 2.5rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: var(--radius-pill);
        background: var(--colour-surface-elevated);
        color: var(--colour-primary);
      }

      .source-option__copy {
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
      }

      .source-option__copy strong,
      .source-option__copy small {
        white-space: normal;
        line-height: 1.3;
      }

      .source-option__copy small {
        color: var(--colour-text-secondary);
      }

      .source-option__check {
        color: var(--colour-primary);
      }

      @media (max-width: 700px) {
        .source-options {
          grid-template-columns: 1fr;
        }
      }

      /* ── History ── */
      .history-loading {
        padding: 8px 0;
      }

      .loading-label {
        font-size: 13px;
        color: var(--colour-text-secondary);
        margin: 6px 0 0;
      }

      .empty-history {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 24px 0;
        color: var(--colour-text-secondary);
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
        background: var(--colour-success-bg);
        color: var(--colour-success-text);
      }

      .status-chip--partial {
        background: var(--colour-warning-bg);
        color: var(--colour-warning-text);
      }

      .status-chip--failed {
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
      }

      .status-chip--empty {
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
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
  @ViewChild("reviewTableWrapper") private reviewTableWrapper?: ElementRef<HTMLElement>;

  private importService = inject(ImportService);
  private importJobService = inject(ImportJobService);
  private appDialog = inject(AppDialogService);
  private destroyRef = inject(DestroyRef);
  readonly importJob$ = this.importJobService.job$;

  // File selection state
  selectedFile: File | null = null;
  isDragging = false;
  validationError: string | null = null;
  readonly validationErrorId = "import-validation-error";
  importSource: ImportSource = "aidiary";

  get acceptedFileTypes(): string {
    return this.importSource === "daylio" ? ".daylio,.csv" : ".xlsx,.zip";
  }

  get acceptedFileDescription(): string {
    return this.importSource === "daylio"
      ? "Accepts *.Daylio export/backup files - maximum 50 MB"
      : "Accepts .xlsx and .zip - maximum 50 MB";
  }

  get uploadSourceDescription(): string {
    return this.importSource === "daylio"
      ? "Select a *.Daylio export/backup file (max 50 MB)."
      : "Select your completed workbook or export package (.xlsx or .zip, max 50 MB).";
  }

  get uploadCardTitle(): string {
    return this.importSource === "daylio"
      ? "Import Daylio entries"
      : "Step 2 - Upload completed template";
  }

  get filePickerLabel(): string {
    return this.importSource === "daylio"
      ? "Choose a Daylio backup or CSV export for import"
      : "Choose a workbook or export package for import";
  }

  // Upload state
  uploadState: UploadState = "idle";
  uploadProgress: UploadProgress = { percent: 0, loaded: 0, total: 0 };
  importResult: ImportResult | null = null;
  importErrorMessage = "";
  importSessionId: string | null = null;
  isDuplicateModalOpen = false;
  isCommittingReview = false;
  selectedReviewRowIds = new Set<string>();
  reviewPage = 0;
  reviewEntryTypes = new Map<string, "daily" | "dream">();
  readonly reviewPageSize = 25;
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
    "actions",
  ];
  revertingImportId: number | null = null;
  isRemovingReview = false;
  isBackgroundImportActive = false;

  ngOnInit(): void {
    this.loadHistory();
    this.importJob$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((job) => {
        this.isBackgroundImportActive =
          job?.status === "queued" || job?.status === "running";
        if (!job) return;
        if (job.status === "completed" && job.result) {
          this.importResult = job.result;
          this.uploadState = job.result.status === "failed" ? "error" : job.result.status;
          this.loadHistory();
        } else if (job.status === "failed") {
          this.uploadState = "error";
          this.importErrorMessage = job.error || job.message;
        }
      });
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
    if (this.isBackgroundImportActive) return;
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
    if (!this.selectedFile || this.validationError || this.isBackgroundImportActive) return;

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

    this.importService
      .uploadFile(this.selectedFile, this.importSource)
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
            this.selectedReviewRowIds = new Set(
              (event.result.review_entries ?? [])
                .filter((entry) => !entry.is_duplicate && entry.source_record_kind !== "mood_checkin")
                .map((entry) => entry.row_id),
            );
            this.reviewEntryTypes.clear();
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
        link.download = "openmynd_import_template.xlsx";
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
      reverted: "undo",
    };
    return icons[status] ?? "help_outline";
  }

  statusLabel(status: ImportHistoryItem["status"]): string {
    const labels: Record<ImportHistoryItem["status"], string> = {
      success: "Success",
      partial: "Partial",
      failed: "Failed",
      empty: "Empty",
      reverted: "Reverted",
    };
    return labels[status] ?? status;
  }

  async revertImport(row: ImportHistoryItem): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "Revert this import?",
      message: `This permanently removes the ${row.imported_count} entries and attached media created by ${row.filename}. Other entries are not affected.`,
      confirmText: "Revert import",
      cancelText: "Keep entries",
      variant: "danger",
    });
    if (!confirmed) return;

    this.revertingImportId = row.id;
    this.importService.revertImport(row.id).subscribe({
      next: () => {
        this.revertingImportId = null;
        this.loadHistory();
      },
      error: (error: Error) => {
        this.revertingImportId = null;
        void this.appDialog.alert({
          title: "Import could not be reverted",
          message: error.message || "Please try again.",
          confirmText: "Close",
          variant: "error",
        });
      },
    });
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
    this.validationError = this.importService.validateFile(file, this.importSource);

    // Reset any previous result when a new file is chosen
    this.resetImportFeedback();
  }

  getDuplicateCount(result: ImportResult): number {
    return (result.duplicate_entries?.length ?? 0) || 0;
  }

  async changeImportSource(source: ImportSource): Promise<void> {
    if (source === this.importSource) {
      return;
    }
    if (!(await this.confirmResetPendingReview())) {
      return;
    }
    this.importSource = source;
    this.resetImportState();
  }

  isImportSourceLocked(): boolean {
    return (
      this.uploadState === "uploading" ||
      this.uploadState === "processing" ||
      this.uploadState === "review" ||
      this.isCommittingReview ||
      this.isBackgroundImportActive
    );
  }

  openDuplicateReview(): void {
    this.reviewPage = 0;
    this.isDuplicateModalOpen = true;
  }

  closeDuplicateReview(): void {
    this.isDuplicateModalOpen = false;
  }

  commitReviewedImport(): void {
    if (!this.importSessionId) {
      return;
    }

    this.isCommittingReview = true;
    const acceptedDuplicateRowIds = (this.importResult?.review_entries ?? [])
      .filter((entry) => entry.is_duplicate && this.selectedReviewRowIds.has(entry.row_id))
      .map((entry) => entry.row_id);

    this.importJobService
      .start(
        this.importSessionId,
        acceptedDuplicateRowIds,
        Array.from(this.selectedReviewRowIds),
        Object.fromEntries(this.reviewEntryTypes),
      )
      .subscribe({
        next: () => {
          this.importSessionId = null;
          this.isDuplicateModalOpen = false;
          this.isCommittingReview = false;
          this.uploadState = "idle";
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

  get paginatedReviewEntries(): ImportReviewEntry[] {
    const start = this.reviewPage * this.reviewPageSize;
    return (this.importResult?.review_entries ?? []).slice(start, start + this.reviewPageSize);
  }

  get reviewPageCount(): number {
    return Math.ceil((this.importResult?.review_entries?.length ?? 0) / this.reviewPageSize);
  }

  toggleReviewSelection(rowId: string, checked: boolean): void {
    if (checked) this.selectedReviewRowIds.add(rowId);
    else this.selectedReviewRowIds.delete(rowId);
  }

  isReviewEntrySelected(rowId: string): boolean {
    return this.selectedReviewRowIds.has(rowId);
  }

  selectAllReviewEntries(): void {
    this.selectedReviewRowIds = new Set(
      (this.importResult?.review_entries ?? []).map((entry) => entry.row_id),
    );
  }

  clearReviewSelection(): void {
    this.selectedReviewRowIds.clear();
  }

  changeReviewPage(delta: number): void {
    this.reviewPage = Math.max(0, Math.min(this.reviewPage + delta, this.reviewPageCount - 1));
    requestAnimationFrame(() => this.scrollReviewToTop());
  }

  scrollReviewToTop(): void {
    this.reviewTableWrapper?.nativeElement.scrollTo({ top: 0, behavior: "smooth" });
  }

  canChangeReviewEntryType(entry: ImportReviewEntry): boolean {
    return entry.entry_type === "daily" || entry.entry_type === "dream";
  }

  getReviewEntryType(entry: ImportReviewEntry): "daily" | "dream" {
    if (entry.entry_type !== "daily" && entry.entry_type !== "dream") {
      return "daily";
    }
    return this.reviewEntryTypes.get(entry.row_id) ?? entry.entry_type;
  }

  setReviewEntryType(rowId: string, entryType: "daily" | "dream"): void {
    this.reviewEntryTypes.set(rowId, entryType);
  }

  formatReviewEntryType(entryType: ImportReviewEntry["entry_type"]): string {
    switch (entryType) {
      case "important_day":
        return "Important day";
      case "thought_record":
        return "Thought record";
      case "dream":
        return "Dream entry";
      default:
        return "Daily entry";
    }
  }

  getMoodIcon(mood = ""): string {
    const value = mood.toLowerCase();
    if (/not too bad|not good|down|doubt|poor/.test(value)) return "sentiment_dissatisfied";
    if (/awful|terrible|very bad|sad|angry/.test(value)) return "sentiment_very_dissatisfied";
    if (/great|excellent|amazing|very good|happy/.test(value)) return "sentiment_very_satisfied";
    if (/good|content|calm|quiet/.test(value)) return "sentiment_satisfied";
    return "sentiment_neutral";
  }

  getMoodTone(mood = ""): "negative" | "low" | "neutral" | "positive" | "high" {
    const value = mood.toLowerCase();
    if (/not too bad|not good|down|doubt|poor/.test(value)) return "low";
    if (/awful|terrible|very bad|sad|angry/.test(value)) return "negative";
    if (/great|excellent|amazing|very good|happy/.test(value)) return "high";
    if (/good|content|calm|quiet/.test(value)) return "positive";
    return "neutral";
  }

  removePendingImport(): void {
    if (!this.importSessionId || this.isRemovingReview) return;
    this.isRemovingReview = true;
    this.importService.cancelImportSession(this.importSessionId).subscribe({
      next: () => {
        this.isRemovingReview = false;
        this.resetImportState();
      },
      error: () => {
        this.isRemovingReview = false;
        void this.appDialog.alert({
          title: "Review could not be removed",
          message: "Please try again.",
          confirmText: "Close",
          variant: "error",
        });
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
    this.selectedReviewRowIds.clear();
    this.reviewPage = 0;
    this.reviewEntryTypes.clear();
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
