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
    <mat-card class="export-card">
      <mat-card-header>
        <mat-icon mat-card-avatar>download</mat-icon>
        <mat-card-title>Export Entries</mat-card-title>
        <mat-card-subtitle>
          Download all your daily and dream entries as a package containing the workbook and any bundled hero images.
        </mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <p class="hint">
          The export package contains an <strong>entries.xlsx</strong> workbook
          plus any bundled Daily and Dream hero images.
        </p>

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
      </mat-card-actions>
    </mat-card>

    <mat-card class="bulk-delete-card">
      <mat-card-header>
        <mat-icon mat-card-avatar>warning</mat-icon>
        <mat-card-title>Delete All Entries</mat-card-title>
        <mat-card-subtitle>
          This permanently deletes every daily and dream entry for your account.
        </mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <p class="hint destructive">
          To reduce accidental data loss, you must export the full range of your
          entries in this session before bulk delete is unlocked.
        </p>

        <div class="range-summary" *ngIf="readiness">
          <p *ngIf="readiness.has_entries">
            First entry: <strong>{{ formatReadableDate(readiness.first_entry_date) }}</strong>
          </p>
          <p *ngIf="readiness.has_entries">
            Last entry: <strong>{{ formatReadableDate(readiness.last_entry_date) }}</strong>
          </p>
          <p>
            Total entries:
            <strong>{{ readiness.total_entries }}</strong>
            ({{ readiness.daily_count }} daily, {{ readiness.dream_count }} dreams)
          </p>
          <p *ngIf="!readiness.has_entries">No entries found to delete.</p>
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
            Export full range first
          </button>

          <p class="feedback success" *ngIf="bulkDeleteSuccessMessage">
            {{ bulkDeleteSuccessMessage }}
          </p>

          <div class="bulk-delete-stage" *ngIf="readiness?.eligible_for_delete">
            <p class="warning-copy">
              Full-range export completed for this session. Type
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
              {{ isDeleting ? "Deleting..." : "Delete all entries" }}
            </button>
          </div>
        </div>
      </mat-card-content>
    </mat-card>
  `,
  styles: [
    `
      .export-card {
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }

      .hint {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .filters {
        margin-top: var(--spacing-md);
        display: grid;
        gap: var(--spacing-sm);
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
        border-radius: var(--radius-sm);
        background: var(--colour-background);
        color: var(--colour-text);
        padding: 8px 10px;
      }

      .type-row {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
      }

      .feedback {
        margin-top: var(--spacing-sm);
      }

      .success {
        color: #1b5e20;
      }

      .error {
        color: #b71c1c;
      }

      .bulk-delete-card {
        margin-top: var(--spacing-md);
        border-radius: var(--radius-md);
        border: 1px solid #f3d1d1;
        background: #fff7f7;
      }

      .destructive {
        color: #991b1b;
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

      .warning-copy {
        margin: 0;
        color: #7f1d1d;
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
            `Deleted ${result.deleted_total} entries successfully.`;
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
    if (!this.includeDaily && !this.includeDreams) {
      return "Select at least one entry type to export (Daily or Dreams).";
    }

    if (this.fromDate && this.toDate && this.fromDate > this.toDate) {
      return "From date must be on or before To date.";
    }

    return null;
  }

  private getExportFilters(): ExportFilters | undefined {
    const hasDateFilter = Boolean(this.fromDate || this.toDate);
    const usesDefaultTypeFilter = this.includeDaily && this.includeDreams;

    if (!hasDateFilter && usesDefaultTypeFilter) {
      return undefined;
    }

    return {
      fromDate: this.fromDate || undefined,
      toDate: this.toDate || undefined,
      includeDaily: this.includeDaily,
      includeDreams: this.includeDreams,
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
    anchor.download = filename || `aidiary_export_${stamp}.zip`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  }
}
