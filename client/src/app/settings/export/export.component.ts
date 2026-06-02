import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatIconModule } from "@angular/material/icon";
import {
  type ExportFilters,
  ImportService,
} from "../../core/services/import.service";

@Component({
  selector: "app-export",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatCheckboxModule,
  ],
  template: `
    <mat-card class="export-card">
      <mat-card-header>
        <mat-icon mat-card-avatar>download</mat-icon>
        <mat-card-title>Export Entries</mat-card-title>
        <mat-card-subtitle>
          Download all your daily and dream entries as a single Excel file.
        </mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <p class="hint">
          The export file contains two sheets: <strong>Daily</strong> and
          <strong>Dreams</strong>.
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
    `,
  ],
})
export class ExportComponent {
  private importService = inject(ImportService);

  isDownloading = false;
  successMessage = "";
  errorMessage = "";
  fromDate = "";
  toDate = "";
  includeDaily = true;
  includeDreams = true;

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
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        const stamp = new Date().toISOString().slice(0, 10);
        anchor.href = url;
        anchor.download = `aidiary_export_${stamp}.xlsx`;
        anchor.click();
        window.URL.revokeObjectURL(url);

        this.isDownloading = false;
        this.successMessage = "Export downloaded successfully.";
      },
      error: (err: Error) => {
        this.isDownloading = false;
        this.errorMessage = err.message || "Export failed. Please try again.";
      },
    });
  }

  private clearFeedback(): void {
    this.successMessage = "";
    this.errorMessage = "";
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
}
