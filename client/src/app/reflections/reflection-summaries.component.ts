import { CommonModule } from "@angular/common";
import { Component, DestroyRef, OnInit, inject } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatNativeDateModule } from "@angular/material/core";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatSelectModule } from "@angular/material/select";
import {
  ReflectionSummary,
  ReflectionSummaryPeriodType,
} from "../core/models/reflection-summary.model";
import { AppDialogService } from "../core/services/app-dialog.service";
import { ReflectionSummaryService } from "../core/services/reflection-summary.service";

@Component({
  selector: "app-reflection-summaries",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatNativeDateModule,
    MatProgressSpinnerModule,
    MatSelectModule,
  ],
  template: `
    <section class="reflection-dashboard" data-testid="reflection-summaries">
      <header class="reflection-dashboard-header">
        <div>
          <p class="reflection-eyebrow">Period summaries</p>
          <h1>Reflection summaries</h1>
          <p>
            Generate opt-in weekly or monthly reflections from your own entries,
            dreams, and thought records.
          </p>
        </div>
      </header>

      <mat-card class="summary-generator-card">
        <mat-card-header>
          <mat-card-title>Generate a reflection</mat-card-title>
          <mat-card-subtitle>
            This uses AI only when you click generate. Detailed settings or larger periods may cost more.
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <div class="generator-grid">
            <mat-form-field appearance="outline">
              <mat-label>Period</mat-label>
              <mat-select [(ngModel)]="selectedPeriodType" name="periodType">
                <mat-option value="weekly">Weekly</mat-option>
                <mat-option value="monthly">Monthly</mat-option>
              </mat-select>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Period date</mat-label>
              <input
                matInput
                [matDatepicker]="periodPicker"
                [(ngModel)]="selectedDate"
                name="periodDate"
              />
              <mat-datepicker-toggle matIconSuffix [for]="periodPicker"></mat-datepicker-toggle>
              <mat-datepicker #periodPicker></mat-datepicker>
            </mat-form-field>

            <button
              mat-flat-button
              color="primary"
              type="button"
              (click)="generateSummary()"
              [disabled]="isGenerating || !selectedDate"
              data-testid="generate-reflection-summary"
            >
              <mat-icon aria-hidden="true">auto_awesome</mat-icon>
              {{ getGenerateLabel() }}
            </button>
          </div>
          <div class="summary-status" *ngIf="isGenerating" role="status">
            <mat-progress-spinner mode="indeterminate" diameter="28" />
            <span>Generating reflection summary…</span>
          </div>
          <p class="status error" *ngIf="errorMessage" role="alert">{{ errorMessage }}</p>
          <p class="status success" *ngIf="successMessage">{{ successMessage }}</p>
        </mat-card-content>
      </mat-card>

      <div class="summary-status" *ngIf="isLoading" role="status">
        <mat-progress-spinner mode="indeterminate" diameter="42" />
        <span>Loading reflection summaries…</span>
      </div>

      <section class="summary-list-section" *ngIf="!isLoading">
        <div class="summary-list-heading">
          <div>
            <h2>Generated reflections</h2>
            <p>Review, regenerate, or delete summaries without changing source entries.</p>
          </div>
          <span class="summary-count-pill">{{ summaries.length }}</span>
        </div>

        <div class="summary-grid" *ngIf="summaries.length; else emptySummaries">
          <mat-card class="summary-card" *ngFor="let summary of summaries">
            <mat-card-header>
              <mat-icon mat-card-avatar aria-hidden="true">summarize</mat-icon>
              <mat-card-title>{{ summary.title }}</mat-card-title>
              <mat-card-subtitle>
                {{ getPeriodLabel(summary) }} · {{ summary.model }}
              </mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              <p>{{ summary.summary_text }}</p>
              <mat-chip-set aria-label="Reflection themes" *ngIf="summary.themes.length">
                <mat-chip *ngFor="let theme of summary.themes">{{ theme }}</mat-chip>
              </mat-chip-set>
              <details class="source-details">
                <summary>{{ summary.source_refs.length }} source reference{{ summary.source_refs.length === 1 ? "" : "s" }}</summary>
                <ul>
                  <li *ngFor="let ref of summary.source_refs">
                    {{ getSourceTypeLabel(ref.type) }} · {{ ref.date | date: "d MMM y" }} · {{ ref.theme }}
                  </li>
                </ul>
              </details>
            </mat-card-content>
            <mat-card-actions align="end">
              <button mat-button type="button" class="delete-button" (click)="deleteSummary(summary)">
                <mat-icon aria-hidden="true">delete</mat-icon>
                Delete
              </button>
              <button mat-stroked-button type="button" (click)="regenerateSummary(summary)" [disabled]="isGenerating">
                <mat-icon aria-hidden="true">refresh</mat-icon>
                Regenerate
              </button>
            </mat-card-actions>
          </mat-card>
        </div>
        <ng-template #emptySummaries>
          <div class="empty-state">
            <mat-icon aria-hidden="true">summarize</mat-icon>
            <p>No reflection summaries yet.</p>
          </div>
        </ng-template>
      </section>
    </section>
  `,
  styles: [
    `
      .reflection-dashboard {
        display: grid;
        gap: var(--spacing-md);
        color: var(--colour-text-primary);
      }

      .reflection-dashboard-header {
        padding: clamp(1.25rem, 3vw, 2.25rem);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background:
          radial-gradient(circle at 88% 12%, color-mix(in srgb, var(--colour-primary) 18%, transparent), transparent 32%),
          var(--colour-surface-elevated);
      }

      .reflection-dashboard-header h1,
      .reflection-dashboard-header p,
      .summary-list-heading h2,
      .summary-list-heading p,
      .summary-card p,
      .status {
        margin: 0;
      }

      .reflection-dashboard-header h1 {
        margin-bottom: 0.5rem;
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1.1;
      }

      .reflection-dashboard-header > div > p:last-child,
      .summary-list-heading p,
      .source-details,
      .empty-state {
        color: var(--colour-text-secondary);
      }

      .reflection-eyebrow {
        margin-bottom: var(--spacing-xs);
        color: var(--colour-primary);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }

      .summary-generator-card,
      .summary-card {
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-elevated);
      }

      .generator-grid {
        display: grid;
        grid-template-columns: minmax(0, 12rem) minmax(0, 16rem) auto;
        gap: var(--spacing-sm);
        align-items: start;
      }

      .generator-grid button {
        min-height: 3.5rem;
        border-radius: var(--radius-pill);
      }

      .summary-status,
      .empty-state {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
      }

      .summary-list-section {
        display: grid;
        gap: var(--spacing-sm);
      }

      .summary-list-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
      }

      .summary-count-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 1.75rem;
        padding: 0.2rem 0.65rem;
        border-radius: var(--radius-pill);
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
        font-size: 0.8rem;
        font-weight: 800;
      }

      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
        gap: var(--spacing-sm);
      }

      .summary-card mat-card-content {
        display: grid;
        gap: var(--spacing-sm);
      }

      .source-details summary {
        cursor: pointer;
        font-weight: 800;
      }

      .source-details ul {
        margin: 0.5rem 0 0;
        padding-left: 1.2rem;
      }

      .delete-button {
        color: var(--colour-danger-text);
      }

      .success {
        color: var(--colour-success-text);
      }

      .error {
        color: var(--colour-danger-text);
      }

      @media (max-width: 48rem) {
        .generator-grid {
          grid-template-columns: 1fr;
        }

        .generator-grid button {
          width: 100%;
        }
      }
    `,
  ],
})
export class ReflectionSummariesComponent implements OnInit {
  private readonly summaryService = inject(ReflectionSummaryService);
  private readonly appDialog = inject(AppDialogService);
  private readonly destroyRef = inject(DestroyRef);

  summaries: ReflectionSummary[] = [];
  selectedPeriodType: ReflectionSummaryPeriodType = "monthly";
  selectedDate: Date | null = new Date();
  isLoading = false;
  isGenerating = false;
  errorMessage = "";
  successMessage = "";

  ngOnInit(): void {
    this.loadSummaries();
  }

  loadSummaries(): void {
    this.isLoading = true;
    this.errorMessage = "";
    this.summaryService
      .listSummaries()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (summaries) => {
          this.summaries = summaries;
          this.isLoading = false;
        },
        error: () => {
          this.errorMessage = "Reflection summaries could not be loaded.";
          this.isLoading = false;
        },
      });
  }

  generateSummary(): void {
    if (!this.selectedDate || this.isGenerating) return;
    this.isGenerating = true;
    this.errorMessage = "";
    this.successMessage = "";
    this.summaryService
      .generateSummary(this.selectedPeriodType, this.toLocalDate(this.selectedDate))
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (summary) => {
          this.upsertSummary(summary);
          this.successMessage = "Reflection summary generated.";
          this.isGenerating = false;
        },
        error: (error) => {
          this.errorMessage =
            error?.error?.error || "Reflection summary could not be generated.";
          this.isGenerating = false;
        },
      });
  }

  regenerateSummary(summary: ReflectionSummary): void {
    this.selectedPeriodType = summary.period_type;
    this.selectedDate = new Date(`${summary.period_start}T12:00:00`);
    this.generateSummary();
  }

  async deleteSummary(summary: ReflectionSummary): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "Delete reflection summary?",
      message: "This removes the generated summary only. Source entries stay unchanged.",
      variant: "danger",
      confirmText: "Delete summary",
      cancelText: "Keep",
    });
    if (!confirmed) return;

    this.summaryService
      .deleteSummary(summary.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.summaries = this.summaries.filter((item) => item.id !== summary.id);
          this.successMessage = "Reflection summary deleted.";
        },
        error: () => {
          void this.appDialog.alert({
            title: "Summary not deleted",
            message: "The reflection summary could not be deleted. Try again.",
            variant: "error",
            confirmText: "Close",
          });
        },
      });
  }

  getGenerateLabel(): string {
    return this.isGenerating ? "Generating…" : "Generate reflection";
  }

  getPeriodLabel(summary: ReflectionSummary): string {
    const start = new Date(`${summary.period_start}T12:00:00`);
    const end = new Date(`${summary.period_end}T12:00:00`);
    if (summary.period_type === "monthly") {
      return start.toLocaleDateString("en-GB", {
        month: "long",
        year: "numeric",
      });
    }
    return `${start.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    })} to ${end.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    })}`;
  }

  getSourceTypeLabel(type: string): string {
    if (type === "daily") return "Diary";
    if (type === "dream") return "Dream";
    return "Thought record";
  }

  private upsertSummary(summary: ReflectionSummary): void {
    const existingIndex = this.summaries.findIndex((item) => item.id === summary.id);
    if (existingIndex >= 0) {
      this.summaries = this.summaries.map((item) =>
        item.id === summary.id ? summary : item,
      );
    } else {
      this.summaries = [summary, ...this.summaries];
    }
    this.summaries = [...this.summaries].sort((a, b) =>
      b.period_start.localeCompare(a.period_start),
    );
  }

  private toLocalDate(date: Date): string {
    return [
      date.getFullYear(),
      String(date.getMonth() + 1).padStart(2, "0"),
      String(date.getDate()).padStart(2, "0"),
    ].join("-");
  }
}
