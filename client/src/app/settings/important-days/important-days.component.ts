import { CommonModule } from "@angular/common";
import { Component, OnDestroy, OnInit, inject } from "@angular/core";
import { ActivatedRoute } from "@angular/router";
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
    <section class="important-days-dashboard" data-testid="important-days-dashboard">
      <header class="important-days-dashboard-header">
        <div>
          <p class="important-days-eyebrow">Calendar markers</p>
          <h1>Important days</h1>
          <p>
            Add birthdays, anniversaries, milestones, and personal dates that
            should appear in your calendar.
          </p>
        </div>
        <button
          mat-flat-button
          color="primary"
          type="button"
          (click)="startCreating()"
          [disabled]="viewMode === 'form' && !editingId"
          data-testid="important-days-start-create"
        >
          <mat-icon aria-hidden="true">add</mat-icon>
          New important day
        </button>
      </header>

      <ng-container *ngIf="viewMode === 'form'; else dashboardView">
        <mat-card class="group-card important-day-editor-card" data-testid="important-day-editor">
          <button
            mat-stroked-button
            type="button"
            class="editor-back-button"
            (click)="returnToDashboard()"
            [disabled]="saving"
          >
            <mat-icon aria-hidden="true">arrow_back</mat-icon>
            Back to important days
          </button>
          <mat-card-header>
            <mat-card-title>{{ editingId ? "Edit Important Day" : "Create New Important Day" }}</mat-card-title>
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
                  <div class="preview-art-stack">
                    <div class="preview-icon">
                      <mat-icon>{{ draft.icon_name }}</mat-icon>
                    </div>
                    <button
                      *ngIf="draftImagePreviewUrl"
                      type="button"
                      class="important-day-image-preview"
                      (click)="openImportantDayImage(draftImagePreviewUrl, draft.label.trim() || 'Preview important day', getDraftSummaryLine())"
                      aria-label="View important day image preview"
                    >
                      <img [src]="draftImagePreviewUrl" alt="" />
                    </button>
                  </div>
                  <div class="preview-copy">
                    <strong>{{ draft.label.trim() || "Preview important day" }}</strong>
                    <span>{{ getDraftSummaryLine() }}</span>
                  </div>
                </div>

                <div class="important-day-image-control">
                  <input
                    #importantDayImageInput
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    class="visually-hidden"
                    aria-label="Choose important day image"
                    (change)="onImageSelected($event)"
                  />
                  <button
                    mat-stroked-button
                    type="button"
                    (click)="importantDayImageInput.click()"
                    [disabled]="saving"
                  >
                    <mat-icon>add_photo_alternate</mat-icon>
                    {{ draftImagePreviewUrl ? "Replace image" : "Add image" }}
                  </button>
                  <button
                    mat-stroked-button
                    type="button"
                    class="delete-button"
                    *ngIf="draftImagePreviewUrl"
                    (click)="removeDraftImage()"
                    [disabled]="saving"
                  >
                    <mat-icon>delete</mat-icon>
                    Remove image
                  </button>
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
                <button mat-stroked-button type="button" (click)="returnToDashboard()" [disabled]="saving">
                  Cancel
                </button>
                <button mat-raised-button color="primary" type="submit" [disabled]="saving">
                  {{ editingId ? "Save changes" : "Add important day" }}
                </button>
              </div>
            </form>
          </mat-card-content>
        </mat-card>
      </ng-container>

      <ng-template #dashboardView>
        <mat-card class="group-card important-days-list-card" data-testid="important-days-list">
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
                <div class="important-day-media-stack">
                  <div class="important-day-icon" aria-hidden="true">
                    <mat-icon>{{ importantDay.icon_name }}</mat-icon>
                  </div>
                  <button
                    type="button"
                    class="important-day-thumb"
                    *ngIf="getImportantDayImageUrl(importantDay) as imageUrl"
                    (click)="openImportantDayImage(imageUrl, importantDay.label, formatDateLabel(importantDay))"
                    [attr.aria-label]="'View image for ' + importantDay.label"
                  >
                    <img [src]="imageUrl" alt="" />
                  </button>
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
      </ng-template>

      <div
        class="important-day-image-modal"
        *ngIf="imageModal"
        (click)="closeImportantDayImage()"
        role="dialog"
        aria-modal="true"
        [attr.aria-label]="'Image for ' + imageModal.label"
      >
        <div class="important-day-image-modal-dialog" (click)="$event.stopPropagation()">
          <header class="important-day-image-modal-header">
            <div>
              <strong>{{ imageModal.label }}</strong>
              <span>{{ imageModal.dateLabel }}</span>
            </div>
            <button
              mat-icon-button
              type="button"
              (click)="closeImportantDayImage()"
              aria-label="Close important day image"
            >
              <mat-icon>close</mat-icon>
            </button>
          </header>
          <div class="important-day-image-modal-body">
            <img [src]="imageModal.imageUrl" [alt]="imageModal.label" />
          </div>
          <div class="important-day-image-modal-actions">
            <button mat-stroked-button type="button" (click)="closeImportantDayImage()">
              Close
            </button>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [
    `
      .important-days-dashboard {
        display: grid;
        gap: var(--spacing-md);
        color: var(--colour-text-primary);
      }

      .important-days-dashboard-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--spacing-md);
        padding: clamp(1.25rem, 3vw, 2.25rem);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background:
          radial-gradient(circle at 88% 12%, color-mix(in srgb, var(--colour-primary) 18%, transparent), transparent 32%),
          var(--colour-surface-elevated);
      }

      .important-days-dashboard-header h1,
      .important-days-dashboard-header p {
        margin: 0;
      }

      .important-days-dashboard-header h1 {
        margin-bottom: 0.5rem;
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1.1;
      }

      .important-days-dashboard-header > div > p:last-child {
        color: var(--colour-text-secondary);
      }

      .important-days-dashboard-header > button {
        min-height: 2.75rem;
      }

      .important-days-eyebrow {
        margin-bottom: var(--spacing-xs);
        color: var(--colour-primary);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }

      .group-card {
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-elevated);
      }

      .important-day-editor-card {
        display: grid;
        gap: var(--spacing-sm);
      }

      .editor-back-button {
        justify-self: start;
        margin: var(--spacing-sm) var(--spacing-sm) 0;
        min-height: 2.75rem;
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
        background: linear-gradient(
          180deg,
          var(--colour-surface-elevated) 0%,
          var(--colour-surface) 100%
        );
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
        align-items: flex-start;
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
        background: linear-gradient(
          180deg,
          var(--colour-surface-elevated) 0%,
          var(--colour-surface) 100%
        );
      }

      .preview-art-stack {
        display: grid;
        gap: 0.55rem;
        justify-items: center;
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
        background: var(--colour-surface-elevated);
      }

      .icon-choice.is-selected,
      .colour-choice.is-selected {
        border-color: var(--colour-primary);
        box-shadow: 0 0 0 2px var(--colour-info-bg);
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
        background: var(--colour-surface-strong);
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
        grid-template-columns: 5.5rem minmax(0, 1fr) auto;
        gap: 0.9rem;
        align-items: flex-start;
        padding: 0.95rem 1rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: linear-gradient(
          180deg,
          var(--colour-surface-elevated) 0%,
          var(--colour-surface) 100%
        );
      }

      .important-day-media-stack {
        display: grid;
        gap: 0.55rem;
        justify-items: center;
        width: 5.5rem;
      }

      .important-day-image-control {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: wrap;
      }

      .important-day-image-control button {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
      }

      .important-day-image-preview,
      .important-day-thumb {
        overflow: hidden;
        border: 1px solid var(--colour-border);
        background: var(--colour-surface-muted);
      }

      .important-day-image-preview {
        width: 5.25rem;
        height: 3.5rem;
        padding: 0;
        border-radius: var(--radius-md);
        cursor: zoom-in;
      }

      .important-day-thumb {
        width: 4.75rem;
        height: 3.45rem;
        padding: 0;
        border-radius: 0.9rem;
        cursor: zoom-in;
      }

      .important-day-image-preview:focus-visible,
      .important-day-thumb:focus-visible {
        outline: 3px solid var(--colour-primary);
        outline-offset: 3px;
      }

      .important-day-image-preview img,
      .important-day-thumb img {
        display: block;
        width: 100%;
        height: 100%;
        object-fit: cover;
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
        flex-direction: column;
        gap: 0.65rem;
        flex-wrap: wrap;
        justify-content: flex-start;
        align-items: stretch;
        margin-left: auto;
        min-width: 7.5rem;
      }

      .important-day-actions button {
        width: 100%;
      }

      .delete-button {
        border-color: var(--colour-danger-text) !important;
        color: var(--colour-danger-text) !important;
      }

      .delete-button:hover {
        background: var(--colour-danger-bg) !important;
      }

      .important-day-image-modal {
        position: fixed;
        inset: 0;
        z-index: 1200;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 1.25rem;
        background: rgba(15, 23, 42, 0.62);
      }

      .important-day-image-modal-dialog {
        width: min(52rem, calc(100vw - 2rem));
        max-height: calc(100vh - 2rem);
        display: grid;
        gap: 0.9rem;
        padding: 1rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-elevated);
        box-shadow: 0 24px 64px rgba(15, 23, 42, 0.28);
      }

      .important-day-image-modal-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.75rem;
      }

      .important-day-image-modal-header strong,
      .important-day-image-modal-header span {
        display: block;
      }

      .important-day-image-modal-header span {
        margin-top: 0.2rem;
        color: var(--colour-text-secondary);
        font-size: 0.88rem;
      }

      .important-day-image-modal-body {
        max-height: min(72vh, 42rem);
        overflow: auto;
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .important-day-image-modal-body img {
        display: block;
        width: 100%;
        height: auto;
      }

      .important-day-image-modal-actions {
        display: flex;
        justify-content: flex-end;
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
        border-left-color: var(--colour-amber-border);
      }

      .accent-rose {
        border-left-color: var(--colour-rose-border);
      }

      .accent-blue {
        border-left-color: var(--colour-blue-border);
      }

      .accent-violet {
        border-left-color: var(--colour-violet-border);
      }

      .accent-emerald {
        border-left-color: var(--colour-emerald-border);
      }

      .accent-slate {
        border-left-color: var(--colour-slate-border);
      }

      .accent-amber .important-day-icon,
      .accent-amber .preview-icon,
      .accent-swatch.accent-amber {
        background: var(--colour-amber-bg);
        color: var(--colour-amber-text);
      }

      .accent-rose .important-day-icon,
      .accent-rose .preview-icon,
      .accent-swatch.accent-rose {
        background: var(--colour-rose-bg);
        color: var(--colour-rose-text);
      }

      .accent-blue .important-day-icon,
      .accent-blue .preview-icon,
      .accent-swatch.accent-blue {
        background: var(--colour-blue-bg);
        color: var(--colour-blue-text);
      }

      .accent-violet .important-day-icon,
      .accent-violet .preview-icon,
      .accent-swatch.accent-violet {
        background: var(--colour-violet-bg);
        color: var(--colour-violet-text);
      }

      .accent-emerald .important-day-icon,
      .accent-emerald .preview-icon,
      .accent-swatch.accent-emerald {
        background: var(--colour-emerald-bg);
        color: var(--colour-emerald-text);
      }

      .accent-slate .important-day-icon,
      .accent-slate .preview-icon,
      .accent-swatch.accent-slate {
        background: var(--colour-slate-bg);
        color: var(--colour-slate-text);
      }

      .success {
        color: var(--colour-success-text);
      }

      .error {
        color: var(--colour-danger-text);
      }

      @media (max-width: 900px) {
        .important-days-dashboard-header {
          align-items: stretch;
          flex-direction: column;
        }

        .important-days-dashboard-header > button {
          width: 100%;
        }
      }

      @media (max-width: 640px) {
        .form-two-column {
          grid-template-columns: 1fr;
        }

        .important-day-item {
          grid-template-columns: 1fr;
        }

        .important-day-actions {
          grid-column: 1 / -1;
          width: 100%;
          margin-left: 0;
        }
      }
    `,
  ],
})
export class ImportantDaysComponent implements OnInit, OnDestroy {
  private readonly importantDaysService = inject(ImportantDaysService);
  private readonly appDialog = inject(AppDialogService);
  private readonly route = inject(ActivatedRoute);

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
  viewMode: "dashboard" | "form" = "dashboard";
  editingId: number | null = null;
  iconPickerOpen = false;
  loading = false;
  saving = false;
  successMessage = "";
  errorMessage = "";
  pendingImageFile: File | null = null;
  draftImagePreviewUrl = "";
  imageModal: { imageUrl: string; label: string; dateLabel: string } | null =
    null;
  private objectUrlToRevoke = "";

  ngOnInit(): void {
    const requestedDate = this.route.snapshot.queryParamMap.get("date");
    if (this.route.snapshot.queryParamMap.get("create") === "true") {
      this.viewMode = "form";
      if (requestedDate) {
        const parsedDate = new Date(`${requestedDate}T12:00:00`);
        if (!Number.isNaN(parsedDate.getTime())) {
          this.draft.startsOn = parsedDate;
        }
      }
    }
    this.loadImportantDays();
  }

  ngOnDestroy(): void {
    this.revokeDraftImagePreview();
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
        this.persistPendingImageIfNeeded(importantDay);
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Unable to save important day.";
        this.saving = false;
      },
    });
  }

  startEditing(importantDay: ImportantDay): void {
    this.viewMode = "form";
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
    this.pendingImageFile = null;
    this.setDraftImagePreview(importantDay.image_url || "", false);
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
    this.pendingImageFile = null;
    this.setDraftImagePreview("", false);
  }

  startCreating(): void {
    this.resetDraft();
    this.viewMode = "form";
    this.successMessage = "";
    this.errorMessage = "";
  }

  returnToDashboard(): void {
    this.resetDraft();
    this.viewMode = "dashboard";
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

  onImageSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    input.value = "";
    if (!file) {
      return;
    }

    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      this.errorMessage = "Use a JPG, PNG, or WEBP image.";
      this.successMessage = "";
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.errorMessage = "Image must be 5 MB or smaller.";
      this.successMessage = "";
      return;
    }

    this.pendingImageFile = file;
    this.setDraftImagePreview(URL.createObjectURL(file), true);
    this.errorMessage = "";
  }

  async removeDraftImage(): Promise<void> {
    if (this.pendingImageFile) {
      this.pendingImageFile = null;
      this.setDraftImagePreview(this.getEditingImportantDay()?.image_url || "", false);
      return;
    }

    const importantDay = this.getEditingImportantDay();
    if (!importantDay?.image_url) {
      this.setDraftImagePreview("", false);
      return;
    }

    const confirmed = await this.appDialog.confirm({
      title: "Remove important day image?",
      message: `Remove the image from "${importantDay.label}"?`,
      confirmText: "Remove image",
      cancelText: "Keep",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }

    this.saving = true;
    this.importantDaysService.deleteImportantDayImage(importantDay.id).subscribe({
      next: () => {
        this.importantDays = this.importantDays.map((item) =>
          item.id === importantDay.id
            ? { ...item, has_image: false, image_url: null }
            : item,
        );
        this.setDraftImagePreview("", false);
        this.successMessage = "Image removed.";
        this.errorMessage = "";
        this.saving = false;
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Unable to remove important day image.";
        this.saving = false;
      },
    });
  }

  getEditingImportantDay(): ImportantDay | null {
    if (!this.editingId) {
      return null;
    }
    return (
      this.importantDays.find((importantDay) => importantDay.id === this.editingId) ||
      null
    );
  }

  openImportantDayImage(
    imageUrl: string | null | undefined,
    label: string,
    dateLabel: string,
  ): void {
    const trimmedUrl = String(imageUrl || "").trim();
    if (!trimmedUrl) return;
    this.imageModal = { imageUrl: trimmedUrl, label, dateLabel };
  }

  getImportantDayImageUrl(importantDay: ImportantDay): string | null {
    const imageUrl = String(importantDay.image_url || "").trim();
    return imageUrl || null;
  }

  closeImportantDayImage(): void {
    this.imageModal = null;
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
        this.openLinkedImportantDay();
      },
      error: () => {
        this.errorMessage = "Unable to load important days.";
        this.loading = false;
      },
    });
  }

  private openLinkedImportantDay(): void {
    const requestedId = Number(this.route.snapshot.queryParamMap.get("importantDayId"));
    if (!Number.isInteger(requestedId) || requestedId <= 0) {
      return;
    }

    const importantDay = this.importantDays.find((item) => item.id === requestedId);
    if (!importantDay) {
      this.errorMessage = "Important day not found.";
      return;
    }

    this.startEditing(importantDay);
  }

  private persistPendingImageIfNeeded(importantDay: ImportantDay): void {
    const wasEditing = Boolean(this.editingId);
    if (!this.pendingImageFile) {
      this.applySavedImportantDay(importantDay);
      this.resetDraft();
      this.viewMode = "dashboard";
      this.saving = false;
      return;
    }

    const imageFile = this.pendingImageFile;
    this.importantDaysService.uploadImportantDayImage(importantDay.id, imageFile).subscribe({
      next: (imageResult) => {
        this.applySavedImportantDay({
          ...importantDay,
          has_image: imageResult.has_image,
          image_url: imageResult.image_url,
        });
        this.resetDraft();
        this.viewMode = "dashboard";
        this.successMessage = wasEditing
          ? "Important day updated."
          : "Important day added.";
        this.saving = false;
      },
      error: (error) => {
        this.applySavedImportantDay(importantDay);
        this.pendingImageFile = null;
        this.resetDraft();
        this.viewMode = "dashboard";
        this.errorMessage =
          error?.error?.error || "Important day saved, but image upload failed.";
        this.successMessage = wasEditing
          ? "Important day updated."
          : "Important day added.";
        this.saving = false;
      },
    });
  }

  private applySavedImportantDay(importantDay: ImportantDay): void {
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
  }

  private setDraftImagePreview(url: string, isObjectUrl: boolean): void {
    this.revokeDraftImagePreview();
    this.draftImagePreviewUrl = url;
    this.objectUrlToRevoke = isObjectUrl ? url : "";
  }

  private revokeDraftImagePreview(): void {
    if (this.objectUrlToRevoke) {
      URL.revokeObjectURL(this.objectUrlToRevoke);
      this.objectUrlToRevoke = "";
    }
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
