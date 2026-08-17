import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import {
  type BulkDeleteReadiness,
  type ExportFilters,
  ImportService,
} from "../../core/services/import.service";
import { formatReadableLongDate } from "../../shared/utils/date-display";

@Component({
  selector: "app-export",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatCheckboxModule,
    MatInputModule,
  ],
  template: `
    <mat-card class="export-card" data-testid="export-settings-card">
      <mat-card-header>
        <mat-icon mat-card-avatar>download</mat-icon>
        <mat-card-title>Export Data</mat-card-title>
        <mat-card-subtitle>
          Download a portable OpenMynd package for selected journal data.
        </mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <p class="hint">
          The export package contains an <strong>entries.xlsx</strong> workbook
          plus bundled media files where supported.
        </p>

        <div class="portability-note" role="note">
          <strong>Portability limits</strong>
          <p>
            Daily, Dream, Important Day, and Thought Record content can be
            restored from the package. Account settings, public-holiday
            preferences, chat history, and attachment-derived text or transcripts
            are not included.
          </p>
        </div>

        <div class="filters" aria-label="Export filters">
          <div class="date-row">
            <label class="filter-field" for="from-date">
              <span>From date</span>
              <input
                id="from-date"
                type="date"
                [value]="fromDate"
                [disabled]="isDownloading"
                (change)="onFromDateChange($event)"
              />
            </label>

            <label class="filter-field" for="to-date">
              <span>To date</span>
              <input
                id="to-date"
                type="date"
                [value]="toDate"
                [disabled]="isDownloading"
                (change)="onToDateChange($event)"
              />
            </label>
          </div>

          <div class="type-row">
            <mat-checkbox
              [checked]="includeDaily"
              [disabled]="isDownloading"
              (change)="onIncludeDailyChange($event.checked)"
            >
              Include Daily
            </mat-checkbox>

            <mat-checkbox
              [checked]="includeDreams"
              [disabled]="isDownloading"
              (change)="onIncludeDreamsChange($event.checked)"
            >
              Include Dreams
            </mat-checkbox>

            <mat-checkbox
              [checked]="includeImportantDays"
              [disabled]="isDownloading"
              (change)="onIncludeImportantDaysChange($event.checked)"
            >
              Include Important Days
            </mat-checkbox>

            <mat-checkbox
              [checked]="includeThoughtRecords"
              [disabled]="isDownloading"
              (change)="onIncludeThoughtRecordsChange($event.checked)"
            >
              Include Thought Records
            </mat-checkbox>
          </div>
        </div>

        <p class="feedback success" *ngIf="successMessage">
          {{ successMessage }}
        </p>

        <p class="feedback error" *ngIf="errorMessage">
          {{ errorMessage }}
        </p>
      </mat-card-content>

      <mat-card-actions>
        <button
          mat-raised-button
          color="primary"
          (click)="downloadExport()"
          [disabled]="isDownloading"
        >
          <mat-icon>download</mat-icon>
          {{ isDownloading ? "Preparing export..." : "Download Export" }}
        </button>
        <button
          mat-stroked-button
          type="button"
          (click)="downloadAllData()"
          [disabled]="isDownloading"
        >
          <mat-icon>inventory_2</mat-icon>
          Export all data
        </button>
      </mat-card-actions>
    </mat-card>

    <mat-card class="bulk-delete-card" data-testid="bulk-delete-settings-card">
      <mat-card-header>
        <mat-icon mat-card-avatar>warning</mat-icon>
        <mat-card-title>Delete all journal data</mat-card-title>
        <mat-card-subtitle>
          This permanently deletes entries, important days, and thought records for your account.
        </mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <p class="hint destructive">
          To reduce accidental data loss, export all journal data in this session
          before bulk delete is unlocked.
        </p>

        <div class="range-summary" *ngIf="readiness">
          <p *ngIf="readiness.has_entries">
            First entry: <strong>{{ formatReadableDate(readiness.first_entry_date) }}</strong>
          </p>
          <p *ngIf="readiness.has_entries">
            Last entry: <strong>{{ formatReadableDate(readiness.last_entry_date) }}</strong>
          </p>
          <p>
            Total journal records:
            <strong>{{ readiness.total_entries }}</strong>
            ({{ readiness.daily_count }} daily, {{ readiness.dream_count }} dreams,
            {{ readiness.important_day_count || 0 }} important days,
            {{ readiness.thought_record_count || 0 }} thought records)
          </p>
          <p *ngIf="!readiness.has_entries">No journal data found to delete.</p>
        </div>

        <div class="danger-zone" *ngIf="readiness?.has_entries">
          <button
            mat-stroked-button
            color="primary"
            type="button"
            (click)="downloadRequiredFullExport()"
            [disabled]="isDownloading || isDeleting"
          >
            <mat-icon>download</mat-icon>
            Export all data first
          </button>

          <p class="feedback success" *ngIf="bulkDeleteSuccessMessage">
            {{ bulkDeleteSuccessMessage }}
          </p>

          <div class="bulk-delete-stage" *ngIf="readiness?.eligible_for_delete">
            <p class="warning-copy">
              Full export completed for this session. Type
              <strong>DELETE ALL</strong> to unlock permanent deletion.
            </p>

            <label class="filter-field" for="bulk-delete-confirmation">
              <span>Confirmation</span>
              <input
                id="bulk-delete-confirmation"
                type="text"
                [(ngModel)]="bulkDeleteConfirmation"
                [disabled]="isDeleting"
                placeholder="Type DELETE ALL"
              />
            </label>

            <button
              mat-raised-button
              color="warn"
              type="button"
              (click)="deleteAllEntries()"
              [disabled]="
                isDeleting || bulkDeleteConfirmation.trim() !== 'DELETE ALL'
              "
            >
              <mat-icon>delete_forever</mat-icon>
              {{ isDeleting ? "Deleting..." : "Delete all journal data" }}
            </button>
          </div>
        </div>
      </mat-card-content>
    </mat-card>
  `,
  styles: [
    `
      .export-card {
        border-radius: var(--radius-lg);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }

      mat-card-content {
        display: grid;
        gap: var(--spacing-md);
      }

      .hint {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .portability-note {
        padding: var(--spacing-sm) var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
        color: var(--colour-text-secondary);
      }

      .portability-note strong {
        color: var(--colour-text-primary);
      }

      .portability-note p {
        margin: var(--spacing-xs) 0 0;
      }

      .filters {
        display: grid;
        gap: var(--spacing-md);
      }

      .date-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: var(--spacing-sm);
      }

      .filter-field {
        display: flex;
        flex-direction: column;
        gap: 6px;
        color: var(--colour-text-secondary);
        font-size: 0.9rem;
      }

      .filter-field input {
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
        color: var(--colour-text-primary);
        padding: 10px 14px;
        min-height: 44px;
      }

      .filter-field input:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .type-row {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
      }

      .feedback {
        margin: 0;
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--radius-lg);
        font-weight: 700;
      }

      .success {
        border: 1px solid var(--colour-emerald-border);
        background: var(--colour-success-bg);
        color: var(--colour-success-text);
      }

      .error {
        border: 1px solid var(--colour-rose-border);
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
      }

      .bulk-delete-card {
        margin-top: var(--spacing-md);
        border-radius: var(--radius-lg);
        border: 1px solid
          color-mix(in srgb, var(--colour-danger-text) 35%, transparent);
        background: color-mix(
          in srgb,
          var(--colour-danger-bg) 72%,
          var(--colour-surface)
        );
      }

      .destructive {
        color: var(--colour-danger-text);
      }

      .range-summary {
        margin-top: var(--spacing-sm);
      }

      .range-summary p {
        margin: 0 0 0.4rem;
      }

      .danger-zone {
        margin-top: var(--spacing-md);
        display: grid;
        gap: var(--spacing-sm);
      }

      .bulk-delete-stage {
        display: grid;
        gap: var(--spacing-sm);
        padding-top: var(--spacing-sm);
      }

      mat-card-actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md) var(--spacing-md);
      }

      mat-card-actions button,
      .danger-zone button,
      .bulk-delete-stage button {
        border-radius: var(--radius-pill);
        min-height: 44px;
      }

      .warning-copy {
        margin: 0;
        color: var(--colour-danger-text);
      }
    `,
  ],
})
export class ExportComponent implements OnInit {
  private importService = inject(ImportService);

  isDownloading = false;
  isDeleting = false;
  successMessage = "";
  errorMessage = "";
  bulkDeleteSuccessMessage = "";
  fromDate = "";
  toDate = "";
  includeDaily = true;
  includeDreams = true;
  includeImportantDays = false;
  includeThoughtRecords = false;
  readiness: BulkDeleteReadiness | null = null;
  bulkDeleteConfirmation = "";
  private bulkDeleteGuardToken = "";

  ngOnInit(): void {
    this.refreshBulkDeleteReadiness();
  }

  onFromDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.fromDate = input.value;
    this.clearFeedback();
  }

  onToDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.toDate = input.value;
    this.clearFeedback();
  }

  onIncludeDailyChange(checked: boolean): void {
    this.includeDaily = checked;
    this.clearFeedback();
  }

  onIncludeDreamsChange(checked: boolean): void {
    this.includeDreams = checked;
    this.clearFeedback();
  }

  onIncludeImportantDaysChange(checked: boolean): void {
    this.includeImportantDays = checked;
    this.clearFeedback();
  }

  onIncludeThoughtRecordsChange(checked: boolean): void {
    this.includeThoughtRecords = checked;
    this.clearFeedback();
  }

  downloadExport(): void {
    this.clearFeedback();

    const validationError = this.validateFilters();
    if (validationError) {
      this.errorMessage = validationError;
      return;
    }

    this.isDownloading = true;
    const filters = this.getExportFilters();

    this.importService.downloadExport(filters).subscribe({
      next: (result) => {
        this.handleDownloadSuccess(result.blob, result.filename);
        this.bulkDeleteGuardToken = result.guardToken ?? this.bulkDeleteGuardToken;
        this.isDownloading = false;
        this.successMessage = "Export downloaded successfully.";
        this.refreshBulkDeleteReadiness();
      },
      error: (err: Error) => {
        this.isDownloading = false;
        this.errorMessage = err.message || "Export failed. Please try again.";
      },
    });
  }

  downloadAllData(): void {
    this.clearFeedback();
    this.isDownloading = true;

    this.importService.downloadExport({ exportAll: true }).subscribe({
      next: (result) => {
        this.handleDownloadSuccess(result.blob, result.filename);
        this.isDownloading = false;
        this.successMessage = "Full data export downloaded successfully.";
      },
      error: (err: Error) => {
        this.isDownloading = false;
        this.errorMessage = err.message || "Export failed. Please try again.";
      },
    });
  }

  downloadRequiredFullExport(): void {
    this.clearFeedback();
    if (!this.readiness?.has_entries) {
      return;
    }

    this.fromDate = this.readiness.first_entry_date ?? "";
    this.toDate = this.readiness.last_entry_date ?? "";
    this.includeDaily = true;
    this.includeDreams = true;
    this.isDownloading = true;

    this.importService
      .downloadExport({
        fromDate: this.fromDate,
        toDate: this.toDate,
        includeDaily: true,
        includeDreams: true,
      })
      .subscribe({
        next: (result) => {
          this.handleDownloadSuccess(result.blob, result.filename);
          this.bulkDeleteGuardToken = result.guardToken ?? "";
          this.isDownloading = false;
          this.successMessage =
            "Full-range export downloaded. Bulk delete is now unlocked for this session.";
          this.refreshBulkDeleteReadiness();
        },
        error: (err: Error) => {
          this.isDownloading = false;
          this.errorMessage = err.message || "Export failed. Please try again.";
        },
      });
  }

  deleteAllEntries(): void {
    this.clearFeedback();
    if (!this.bulkDeleteGuardToken) {
      this.errorMessage = "A same-session full export is required before delete.";
      return;
    }

    this.isDeleting = true;
    this.importService
      .bulkDeleteAllEntries(
        this.bulkDeleteGuardToken,
        this.bulkDeleteConfirmation.trim(),
      )
      .subscribe({
        next: (result) => {
          this.isDeleting = false;
          this.bulkDeleteSuccessMessage =
            result.message ||
            `Deleted ${result.deleted_total} journal records successfully.`;
          this.bulkDeleteConfirmation = "";
          this.bulkDeleteGuardToken = "";
          this.refreshBulkDeleteReadiness();
        },
        error: (err: Error) => {
          this.isDeleting = false;
          this.errorMessage =
            err.message || "Bulk delete failed. Please try again.";
          this.refreshBulkDeleteReadiness();
        },
      });
  }

  formatReadableDate(value: string | null): string {
    return formatReadableLongDate(value) || "To confirm";
  }

  private clearFeedback(): void {
    this.successMessage = "";
    this.errorMessage = "";
    this.bulkDeleteSuccessMessage = "";
  }

  private validateFilters(): string | null {
    if (
      !this.includeDaily &&
      !this.includeDreams &&
      !this.includeImportantDays &&
      !this.includeThoughtRecords
    ) {
      return "Select at least one data type to export.";
    }

    if (this.fromDate && this.toDate && this.fromDate > this.toDate) {
      return "From date must be on or before To date.";
    }

    return null;
  }

  private getExportFilters(): ExportFilters | undefined {
    const hasDateFilter = Boolean(this.fromDate || this.toDate);
    const usesDefaultTypeFilter =
      this.includeDaily &&
      this.includeDreams &&
      !this.includeImportantDays &&
      !this.includeThoughtRecords;

    if (!hasDateFilter && usesDefaultTypeFilter) {
      return undefined;
    }

    return {
      fromDate: this.fromDate || undefined,
      toDate: this.toDate || undefined,
      includeDaily: this.includeDaily,
      includeDreams: this.includeDreams,
      includeImportantDays: this.includeImportantDays,
      includeThoughtRecords: this.includeThoughtRecords,
    };
  }

  private refreshBulkDeleteReadiness(): void {
    this.importService
      .getBulkDeleteReadiness(this.bulkDeleteGuardToken || undefined)
      .subscribe({
        next: (readiness) => {
          this.readiness = readiness;
        },
        error: () => {
          this.readiness = null;
        },
      });
  }

  private handleDownloadSuccess(blob: Blob, filename?: string): void {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 10);
    anchor.href = url;
    anchor.download = filename || `openmynd_export_${stamp}.zip`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  }
}
