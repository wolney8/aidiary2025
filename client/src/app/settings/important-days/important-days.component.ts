import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatNativeDateModule } from "@angular/material/core";
import { MatSelectModule } from "@angular/material/select";
import { MatTooltipModule } from "@angular/material/tooltip";
import { AppDialogService } from "../../core/services/app-dialog.service";
import {
  ImportantDay,
  ImportantDayAccentColor,
  ImportantDayCategory,
  ImportantDayIcon,
  ImportantDayPayload,
  ImportantDayRecurrence,
} from "../../core/models/important-day.model";
import { ImportantDaysService } from "../../core/services/important-days.service";

type ImportantDayDraft = {
  label: string;
  startsOn: Date | null;
  category: ImportantDayCategory;
  recurrence: ImportantDayRecurrence;
  icon_name: ImportantDayIcon;
  accent_color: ImportantDayAccentColor;
  note: string;
};

@Component({
  selector: "app-important-days",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatTooltipModule,
  ],
  template: `
    <section class="settings-section">
      <header class="section-header">
        <h2>Important Days</h2>
        <p>Add birthdays, anniversaries, and milestones that should appear in your calendar.</p>
        <p class="supporting-copy">
          This slice keeps them as personal recurring dates. Public holidays and richer linked-event
          behavior stay on the follow-on issues.
        </p>
      </header>

      <div class="layout-grid">
        <mat-card class="group-card">
          <mat-card-header>
            <mat-card-title>{{ editingId ? "Edit important day" : "Add important day" }}</mat-card-title>
            <mat-card-subtitle>
              Use one anchor date, choose recurrence, then set the visual cue you want in calendar.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <form class="important-day-form" (ngSubmit)="saveImportantDay()">
              <section class="form-section">
                <div class="form-section-heading">
                  <h3>Details</h3>
                  <p>Name the date and choose when it begins.</p>
                </div>
                <div class="form-two-column">
                  <mat-form-field appearance="outline" class="full-width">
                    <mat-label>Label</mat-label>
                    <input
                      matInput
                      [(ngModel)]="draft.label"
                      name="label"
                      maxlength="60"
                      placeholder="Katie birthday"
                    />
                  </mat-form-field>

                  <mat-form-field appearance="outline">
                    <mat-label>Date</mat-label>
                    <input
                      matInput
                      [matDatepicker]="importantDayPicker"
                      [(ngModel)]="draft.startsOn"
                      name="starts_on"
                    />
                    <mat-datepicker-toggle
                      matIconSuffix
                      [for]="importantDayPicker"
                    ></mat-datepicker-toggle>
                    <mat-datepicker #importantDayPicker></mat-datepicker>
                    <mat-hint *ngIf="getReadableDraftDateLabel()">{{
                      getReadableDraftDateLabel()
                    }}</mat-hint>
                  </mat-form-field>

                  <div class="recurrence-field-row">
                    <mat-form-field appearance="outline">
                      <mat-label>Recurrence</mat-label>
                      <mat-select [(ngModel)]="draft.recurrence" name="recurrence">
                        <mat-option value="yearly">Every year</mat-option>
                        <mat-option value="once">Once only</mat-option>
                      </mat-select>
                    </mat-form-field>

                    <button
                      mat-icon-button
                      type="button"
                      class="field-help-button"
                      matTooltip="Every year repeats from the chosen date. Once only stays in the selected year."
                      aria-label="Recurrence help"
                    >
                      <mat-icon>info</mat-icon>
                    </button>
                  </div>

                  <mat-form-field appearance="outline">
                    <mat-label>Category</mat-label>
                    <mat-select [(ngModel)]="draft.category" name="category">
                      <mat-option value="birthday">Birthday</mat-option>
                      <mat-option value="anniversary">Anniversary</mat-option>
                      <mat-option value="milestone">Milestone</mat-option>
                      <mat-option value="other">Other</mat-option>
                    </mat-select>
                  </mat-form-field>
                </div>
              </section>

              <section class="form-section">
                <div class="form-section-heading">
                  <h3>Appearance</h3>
                  <p>Pick a quick visual marker for calendar view.</p>
                </div>
                <div class="icon-colour-picker">
                <div class="picker-header">
                  <span>Icon and colour</span>
                  <button
                    mat-stroked-button
                    type="button"
                    class="icon-trigger"
                    [ngClass]="'accent-' + draft.accent_color"
                    (click)="toggleIconPicker()"
                    [attr.aria-expanded]="iconPickerOpen"
                  >
                    <mat-icon>{{ draft.icon_name }}</mat-icon>
                    Choose icon
                  </button>
                </div>

                <div class="icon-picker-panel" *ngIf="iconPickerOpen">
                  <button
                    mat-icon-button
                    type="button"
                    class="icon-choice"
                    *ngFor="let option of iconOptions"
                    [class.is-selected]="draft.icon_name === option.value"
                    [attr.aria-label]="option.label"
                    [matTooltip]="option.label"
                    (click)="selectIcon(option.value)"
                  >
                    <mat-icon>{{ option.value }}</mat-icon>
                  </button>
                </div>

                <div class="colour-picker-row" aria-label="Accent colour choices">
                  <button
                    type="button"
                    class="colour-choice"
                    *ngFor="let option of accentOptions"
                    [class.is-selected]="draft.accent_color === option.value"
                    [ngClass]="'accent-' + option.value"
                    [attr.aria-label]="option.label"
                    [matTooltip]="option.label"
                    (click)="selectAccent(option.value)"
                  >
                    <span class="accent-swatch" [ngClass]="'accent-' + option.value"></span>
                  </button>
                </div>
                </div>

                <div class="preview-panel" [ngClass]="'accent-' + draft.accent_color">
                  <div class="preview-icon">
                    <mat-icon>{{ draft.icon_name }}</mat-icon>
                  </div>
                  <div class="preview-copy">
                    <strong>{{ draft.label.trim() || "Preview important day" }}</strong>
                    <span>{{ getDraftSummaryLine() }}</span>
                  </div>
                </div>
              </section>

              <section class="form-section">
                <div class="form-section-heading">
                  <h3>Notes</h3>
                  <p>Optional context for this date.</p>
                </div>
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Note</mat-label>
                  <textarea
                    matInput
                    rows="3"
                    maxlength="160"
                    [(ngModel)]="draft.note"
                    name="note"
                    placeholder="Optional reminder or context"
                  ></textarea>
                </mat-form-field>
              </section>

              <div class="actions">
                <button mat-stroked-button type="button" (click)="resetDraft()" [disabled]="saving">
                  {{ editingId ? "Cancel edit" : "Clear" }}
                </button>
                <button mat-raised-button color="primary" type="submit" [disabled]="saving">
                  {{ editingId ? "Save changes" : "Add important day" }}
                </button>
              </div>
            </form>
          </mat-card-content>
        </mat-card>

        <mat-card class="group-card">
          <mat-card-header>
            <mat-card-title>Your important days</mat-card-title>
            <mat-card-subtitle>
              These feed the calendar markers and the month detail list.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <div class="empty-state" *ngIf="!loading && importantDays.length === 0">
              <mat-icon>event</mat-icon>
              <div>
                <strong>No important days yet.</strong>
                <p>Add one to surface it in the monthly calendar view.</p>
              </div>
            </div>

            <div class="important-day-list" *ngIf="importantDays.length > 0">
              <article
                class="important-day-item"
                *ngFor="let importantDay of importantDays"
                [ngClass]="'accent-' + importantDay.accent_color"
              >
                <div class="important-day-icon" aria-hidden="true">
                  <mat-icon>{{ importantDay.icon_name }}</mat-icon>
                </div>
                <div class="important-day-copy">
                  <div class="important-day-heading">
                    <strong>{{ importantDay.label }}</strong>
                    <span class="important-day-category">
                      {{ getCategoryLabel(importantDay.category) }}
                    </span>
                  </div>
                  <p class="important-day-date">{{ formatDateLabel(importantDay) }}</p>
                  <p class="important-day-note" *ngIf="importantDay.note">{{ importantDay.note }}</p>
                </div>
                <div class="important-day-actions">
                  <button mat-stroked-button type="button" (click)="startEditing(importantDay)">
                    Edit
                  </button>
                  <button
                    mat-stroked-button
                    type="button"
                    class="delete-button"
                    (click)="deleteImportantDay(importantDay)"
                  >
                    Delete
                  </button>
                </div>
              </article>
            </div>

            <p class="status success" *ngIf="successMessage">{{ successMessage }}</p>
            <p class="status error" *ngIf="errorMessage">{{ errorMessage }}</p>
          </mat-card-content>
        </mat-card>
      </div>
    </section>
  `,
  styles: [
    `
      .settings-section {
        display: grid;
        gap: var(--spacing-md);
      }

      .section-header h2 {
        margin: 0 0 var(--spacing-xs);
      }

      .section-header p {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .supporting-copy {
        margin-top: var(--spacing-xs);
      }

      .layout-grid {
        display: grid;
        gap: var(--spacing-md);
        grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
        align-items: start;
      }

      .group-card {
        border: 1px solid var(--colour-border);
      }

      .important-day-form {
        display: grid;
        gap: var(--spacing-md);
      }

      .form-section {
        display: grid;
        gap: 0.9rem;
        padding: 1rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: linear-gradient(180deg, #fcfcfd 0%, #ffffff 100%);
      }

      .form-section-heading h3 {
        margin: 0 0 0.2rem;
        font-size: 1rem;
      }

      .form-section-heading p {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .form-two-column {
        display: grid;
        gap: var(--spacing-md);
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .full-width {
        grid-column: 1 / -1;
      }

      .field-help-button {
        align-self: center;
        color: var(--colour-text-secondary);
      }

      .recurrence-field-row {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 0.5rem;
        align-items: start;
      }

      .recurrence-field-row mat-form-field {
        min-width: 0;
      }

      .accent-swatch {
        width: 0.85rem;
        height: 0.85rem;
        border-radius: 999px;
        display: inline-block;
      }

      .preview-panel,
      .important-day-item {
        border-left: 4px solid transparent;
      }

      .preview-panel {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: 0.85rem;
        align-items: center;
        padding: 0.95rem 1rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
      }

      .icon-colour-picker {
        display: grid;
        gap: 0.75rem;
      }

      .picker-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        flex-wrap: wrap;
      }

      .picker-header span {
        font-weight: 600;
      }

      .icon-trigger {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
      }

      .icon-picker-panel {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(2.75rem, 1fr));
        gap: 0.55rem;
        padding: 0.75rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .icon-choice,
      .colour-choice {
        border: 1px solid var(--colour-border);
        border-radius: 0.85rem;
        background: #ffffff;
      }

      .icon-choice.is-selected,
      .colour-choice.is-selected {
        border-color: var(--colour-primary);
        box-shadow: 0 0 0 2px rgba(103, 80, 164, 0.12);
      }

      .colour-picker-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
      }

      .colour-choice {
        width: 2.6rem;
        height: 2.6rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
      }

      .preview-icon,
      .important-day-icon {
        width: 2.6rem;
        height: 2.6rem;
        border-radius: 0.9rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(15, 23, 42, 0.06);
      }

      .preview-copy,
      .important-day-copy {
        min-width: 0;
      }

      .preview-copy strong,
      .important-day-heading strong {
        display: block;
      }

      .preview-copy span,
      .important-day-category,
      .important-day-date {
        color: var(--colour-text-secondary);
      }

      .actions {
        grid-column: 1 / -1;
        display: flex;
        justify-content: flex-end;
        gap: var(--spacing-sm);
      }

      .important-day-list {
        display: grid;
        gap: 0.9rem;
      }

      .important-day-item {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        gap: 0.9rem;
        align-items: start;
        padding: 0.95rem 1rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
      }

      .important-day-heading {
        display: flex;
        gap: 0.65rem;
        align-items: center;
        flex-wrap: wrap;
      }

      .important-day-date,
      .important-day-note {
        margin: 0.25rem 0 0;
      }

      .important-day-note {
        color: var(--colour-text-primary);
      }

      .important-day-actions {
        display: flex;
        gap: 0.65rem;
        flex-wrap: wrap;
        justify-content: flex-end;
      }

      .delete-button {
        border-color: #ef4444 !important;
        color: #b91c1c !important;
      }

      .delete-button:hover {
        background: #fef2f2 !important;
      }

      .empty-state {
        display: flex;
        gap: 0.85rem;
        align-items: center;
        padding: 1rem;
        border: 1px dashed var(--colour-border);
        border-radius: var(--radius-md);
        color: var(--colour-text-secondary);
      }

      .empty-state mat-icon {
        color: var(--colour-primary);
      }

      .empty-state p,
      .status {
        margin: 0;
      }

      .accent-amber {
        border-left-color: #d97706;
      }

      .accent-rose {
        border-left-color: #e11d48;
      }

      .accent-blue {
        border-left-color: #2563eb;
      }

      .accent-violet {
        border-left-color: #7c3aed;
      }

      .accent-emerald {
        border-left-color: #059669;
      }

      .accent-slate {
        border-left-color: #475569;
      }

      .accent-amber .important-day-icon,
      .accent-amber .preview-icon,
      .accent-swatch.accent-amber {
        background: #fef3c7;
        color: #b45309;
      }

      .accent-rose .important-day-icon,
      .accent-rose .preview-icon,
      .accent-swatch.accent-rose {
        background: #ffe4e6;
        color: #be123c;
      }

      .accent-blue .important-day-icon,
      .accent-blue .preview-icon,
      .accent-swatch.accent-blue {
        background: #dbeafe;
        color: #1d4ed8;
      }

      .accent-violet .important-day-icon,
      .accent-violet .preview-icon,
      .accent-swatch.accent-violet {
        background: #ede9fe;
        color: #6d28d9;
      }

      .accent-emerald .important-day-icon,
      .accent-emerald .preview-icon,
      .accent-swatch.accent-emerald {
        background: #d1fae5;
        color: #047857;
      }

      .accent-slate .important-day-icon,
      .accent-slate .preview-icon,
      .accent-swatch.accent-slate {
        background: #e2e8f0;
        color: #334155;
      }

      .success {
        color: #2e7d32;
      }

      .error {
        color: #c62828;
      }

      @media (max-width: 900px) {
        .layout-grid {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 640px) {
        .form-two-column {
          grid-template-columns: 1fr;
        }

        .important-day-item {
          grid-template-columns: auto minmax(0, 1fr);
        }

        .important-day-actions {
          grid-column: 1 / -1;
          justify-content: flex-start;
        }
      }
    `,
  ],
})
export class ImportantDaysComponent implements OnInit {
  private readonly importantDaysService = inject(ImportantDaysService);
  private readonly appDialog = inject(AppDialogService);

  readonly iconOptions: Array<{ value: ImportantDayIcon; label: string }> = [
    { value: "cake", label: "Cake" },
    { value: "favorite", label: "Heart" },
    { value: "flag", label: "Flag" },
    { value: "event", label: "Calendar" },
    { value: "celebration", label: "Celebration" },
    { value: "star", label: "Star" },
    { value: "sentiment_neutral", label: "Neutral" },
    { value: "sentiment_dissatisfied", label: "Low mood" },
    { value: "mood_bad", label: "Hard day" },
  ];
  readonly accentOptions: Array<{
    value: ImportantDayAccentColor;
    label: string;
  }> = [
    { value: "amber", label: "Amber" },
    { value: "rose", label: "Rose" },
    { value: "blue", label: "Blue" },
    { value: "violet", label: "Violet" },
    { value: "emerald", label: "Emerald" },
    { value: "slate", label: "Slate" },
  ];

  importantDays: ImportantDay[] = [];
  draft: ImportantDayDraft = this.createEmptyDraft();
  editingId: number | null = null;
  iconPickerOpen = false;
  loading = false;
  saving = false;
  successMessage = "";
  errorMessage = "";

  ngOnInit(): void {
    this.loadImportantDays();
  }

  saveImportantDay(): void {
    const payload = this.buildPayload();
    if (!payload) {
      return;
    }

    this.saving = true;
    this.successMessage = "";
    this.errorMessage = "";

    const request$ = this.editingId
      ? this.importantDaysService.updateImportantDay(this.editingId, payload)
      : this.importantDaysService.createImportantDay(payload);

    request$.subscribe({
      next: (importantDay) => {
        if (this.editingId) {
          this.importantDays = this.importantDays.map((item) =>
            item.id === importantDay.id ? importantDay : item,
          );
          this.successMessage = "Important day updated.";
        } else {
          this.importantDays = [...this.importantDays, importantDay];
          this.successMessage = "Important day added.";
        }
        this.sortImportantDays();
        this.resetDraft();
        this.saving = false;
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Unable to save important day.";
        this.saving = false;
      },
    });
  }

  startEditing(importantDay: ImportantDay): void {
    this.editingId = importantDay.id;
    this.successMessage = "";
    this.errorMessage = "";
    this.draft = {
      label: importantDay.label,
      startsOn: this.toDate(importantDay.starts_on),
      category: importantDay.category,
      recurrence: importantDay.recurrence,
      icon_name: importantDay.icon_name,
      accent_color: importantDay.accent_color,
      note: importantDay.note || "",
    };
    this.iconPickerOpen = false;
  }

  async deleteImportantDay(importantDay: ImportantDay): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "Delete important day?",
      message: `Remove "${importantDay.label}" from your recurring calendar dates?`,
      confirmText: "Delete",
      cancelText: "Keep",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }

    this.successMessage = "";
    this.errorMessage = "";

    this.importantDaysService.deleteImportantDay(importantDay.id).subscribe({
      next: () => {
        this.importantDays = this.importantDays.filter(
          (item) => item.id !== importantDay.id,
        );
        if (this.editingId === importantDay.id) {
          this.resetDraft();
        }
        this.successMessage = "Important day deleted.";
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Unable to delete important day.";
      },
    });
  }

  resetDraft(): void {
    this.draft = this.createEmptyDraft();
    this.editingId = null;
    this.iconPickerOpen = false;
  }

  toggleIconPicker(): void {
    this.iconPickerOpen = !this.iconPickerOpen;
  }

  selectIcon(icon: ImportantDayIcon): void {
    this.draft.icon_name = icon;
    this.iconPickerOpen = false;
  }

  selectAccent(accent: ImportantDayAccentColor): void {
    this.draft.accent_color = accent;
  }

  getCategoryLabel(category: ImportantDayCategory): string {
    if (category === "birthday") return "Birthday";
    if (category === "anniversary") return "Anniversary";
    if (category === "milestone") return "Milestone";
    return "Other";
  }

  getReadableDraftDateLabel(): string {
    if (!this.draft.startsOn) {
      return "";
    }

    return this.draft.startsOn.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  getDraftSummaryLine(): string {
    const dateLabel = this.draft.startsOn
      ? this.draft.startsOn.toLocaleDateString("en-GB", {
          day: "numeric",
          month: "long",
          year: "numeric",
        })
      : "Choose a date";
    const recurrenceLabel =
      this.draft.recurrence === "yearly"
        ? "Repeats every year"
        : "Happens once only";
    return `${dateLabel} · ${recurrenceLabel}`;
  }

  formatDateLabel(importantDay: ImportantDay): string {
    const date = this.toDate(importantDay.starts_on);
    const dateLabel = date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: importantDay.recurrence === "once" ? "numeric" : undefined,
    });
    const recurrenceLabel =
      importantDay.recurrence === "yearly"
        ? importantDay.original_year
          ? `Repeats yearly · since ${importantDay.original_year}`
          : "Repeats yearly"
        : "One-time date";
    return `${dateLabel} · ${recurrenceLabel}`;
  }

  private loadImportantDays(): void {
    this.loading = true;
    this.importantDaysService.getImportantDays().subscribe({
      next: (importantDays) => {
        this.importantDays = importantDays;
        this.sortImportantDays();
        this.loading = false;
      },
      error: () => {
        this.errorMessage = "Unable to load important days.";
        this.loading = false;
      },
    });
  }

  private buildPayload(): ImportantDayPayload | null {
    const label = this.draft.label.trim();
    if (!label) {
      this.errorMessage = "Label is required.";
      this.successMessage = "";
      return null;
    }
    if (label.length > 60) {
      this.errorMessage = "Label must be 60 characters or fewer.";
      this.successMessage = "";
      return null;
    }
    if (!this.draft.startsOn || Number.isNaN(this.draft.startsOn.getTime())) {
      this.errorMessage = "Date is required.";
      this.successMessage = "";
      return null;
    }

    const note = this.draft.note.trim();
    if (note.length > 160) {
      this.errorMessage = "Note must be 160 characters or fewer.";
      this.successMessage = "";
      return null;
    }

    const starts_on = this.toIsoDate(this.draft.startsOn);
    const originalYear =
      this.draft.startsOn.getFullYear();

    return {
      label,
      starts_on,
      original_year: originalYear,
      category: this.draft.category,
      recurrence: this.draft.recurrence,
      icon_name: this.draft.icon_name,
      accent_color: this.draft.accent_color,
      note,
    };
  }

  private createEmptyDraft(): ImportantDayDraft {
    const today = new Date();
    return {
      label: "",
      startsOn: today,
      category: "other",
      recurrence: "yearly",
      icon_name: "event",
      accent_color: "amber",
      note: "",
    };
  }

  private sortImportantDays(): void {
    this.importantDays = [...this.importantDays].sort((left, right) => {
      if (left.month !== right.month) {
        return left.month - right.month;
      }
      if (left.day !== right.day) {
        return left.day - right.day;
      }
      return left.label.localeCompare(right.label);
    });
  }

  private toIsoDate(value: Date): string {
    const year = value.getFullYear();
    const month = `${value.getMonth() + 1}`.padStart(2, "0");
    const day = `${value.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  private toDate(value: string): Date {
    return new Date(`${value}T12:00:00`);
  }
}
