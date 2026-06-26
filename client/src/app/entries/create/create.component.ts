// Create entry with support for daily and dream flows
import {
  Component,
  ElementRef,
  HostListener,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
} from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { HttpErrorResponse } from "@angular/common/http";
import { Router, ActivatedRoute, RouterModule } from "@angular/router";
import { firstValueFrom } from "rxjs";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatDatepickerModule } from "@angular/material/datepicker";
import {
  MatNativeDateModule,
  MAT_DATE_FORMATS,
  MAT_DATE_LOCALE,
} from "@angular/material/core";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatChipsModule, MatChipInputEvent } from "@angular/material/chips";
import { MatIconModule } from "@angular/material/icon";
import { MatSelectModule } from "@angular/material/select";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { COMMA, ENTER } from "@angular/cdk/keycodes";
import { MatButtonToggleChange } from "@angular/material/button-toggle";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { AuthService } from "../../core/services/auth.service";
import { EntriesService } from "../../core/services/entries.service";
import { AnalysisService } from "../../core/services/analysis.service";
import { BackToTopComponent } from "../../shared/components/back-to-top/back-to-top.component";
import {
  formatReadableLongDate,
  parseLocalIsoDate,
} from "../../shared/utils/date-display";
import {
  DailyAnalysisResponse,
  DreamAnalysisResponse,
  EntryAsset,
  MoodOption,
  AIStyleOption,
  DreamFieldOptions,
} from "../../core/models/entry.model";

const UK_DATE_FORMATS = {
  parse: {
    dateInput: "dd/MM/yyyy",
  },
  display: {
    dateInput: "dd/MM/yyyy",
    monthYearLabel: "MMMM yyyy",
    dateA11yLabel: "dd/MM/yyyy",
    monthYearA11yLabel: "MMMM yyyy",
  },
};

interface PendingAttachment {
  file: File;
  previewUrl: string | null;
  kind: "image" | "pdf" | "audio" | "other";
}

const MAX_ATTACHMENTS_PER_ENTRY = 3;
const MAX_IMAGE_OR_PDF_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const MAX_AUDIO_ATTACHMENT_BYTES = 25 * 1024 * 1024;
const ALLOWED_ATTACHMENT_EXTENSIONS = new Set([
  "jpg",
  "jpeg",
  "png",
  "webp",
  "pdf",
  "mp3",
  "wav",
  "m4a",
  "ogg",
  "webm",
  "aiff",
]);

@Component({
  selector: "app-create",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatButtonToggleModule,
    MatChipsModule,
    MatIconModule,
    MatSelectModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    BackToTopComponent,
  ],
  providers: [
    { provide: MAT_DATE_LOCALE, useValue: "en-GB" },
    { provide: MAT_DATE_FORMATS, useValue: UK_DATE_FORMATS },
  ],
  template: `
    <div class="create-container">
      <mat-card>
        <mat-card-header>
          <button
            mat-stroked-button
            type="button"
            class="header-back"
            (click)="goBack()"
            [disabled]="isSaving"
            aria-label="Go back to entries"
          >
            <mat-icon>arrow_back</mat-icon>
            Back
          </button>

          <mat-card-title
            >{{ isEditing ? "Edit" : "New" }} Diary Entry</mat-card-title
          >

          <mat-slide-toggle [(ngModel)]="leaveItToAI" [disabled]="isSaving">
            Respond with AI
          </mat-slide-toggle>
        </mat-card-header>

        <mat-card-content>
          <fieldset class="entry-form-shell" [disabled]="isSaving">
          <mat-button-toggle-group
            class="entry-type-toggle"
            [(ngModel)]="selectedType"
            name="entryType"
            [disabled]="isEditing || isSaving"
            aria-label="Entry type toggle"
            (change)="onTypeChange($event)"
          >
            <mat-button-toggle value="daily">Daily Entry</mat-button-toggle>
            <mat-button-toggle value="dream">Dream Entry</mat-button-toggle>
          </mat-button-toggle-group>
          <p class="hint" *ngIf="leaveItToAI">
            We'll run an AI analysis straight after saving this entry.
          </p>
          <div
            class="analysis-attachment-opt-in"
            *ngIf="leaveItToAI && hasAttachmentContextCandidates()"
          >
            <mat-checkbox
              [(ngModel)]="allowAiAttachmentContext"
              name="allowAiAttachmentContext"
            >
              {{ getAttachmentContextCheckboxLabel() }}
            </mat-checkbox>
            <p class="hint">
              {{ getAttachmentContextSummary() }} Change the default in
              <a routerLink="/settings/personalisation">Settings</a>.
            </p>
            <p
              class="hint subtle-hint"
              *ngIf="getAttachmentContextBlockedCount() > 0"
            >
              {{ getAttachmentContextBlockedCount() }} audio attachment{{
                getAttachmentContextBlockedCount() === 1 ? "" : "s"
              }}
              will only count after transcription from the saved entry view.
            </p>
          </div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Date</mat-label>
            <input
              matInput
              [matDatepicker]="picker"
              [(ngModel)]="entryDate"
              name="entry_date"
              [max]="maxDate"
              [matDatepickerFilter]="allowPastOrTodayOnly"
            />
            <mat-datepicker-toggle
              matIconSuffix
              [for]="picker"
            ></mat-datepicker-toggle>
            <mat-datepicker #picker></mat-datepicker>
            <mat-hint *ngIf="getReadableEntryDateLabel()">
              {{ getReadableEntryDateLabel() }}
            </mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Time</mat-label>
            <input
              matInput
              type="time"
              [(ngModel)]="entryTime"
              name="entry_time"
            />
            <mat-hint>Defaults to the time you started this entry.</mat-hint>
          </mat-form-field>

          <!-- AI Style Selection - only show when AI toggle is on -->
          <mat-form-field
            appearance="outline"
            class="full-width"
            *ngIf="leaveItToAI"
          >
            <mat-label>AI Response Style</mat-label>
            <mat-select [(ngModel)]="selectedAIStyle" name="aiStyle">
              <mat-select-trigger>
                {{ getSelectedAIStyleLabel() }}
              </mat-select-trigger>
              <mat-option
                *ngFor="let style of aiStyleOptions"
                [value]="style.value"
              >
                <div class="ai-style-option">
                  <span class="ai-style-option-label">{{ style.label }}</span>
                  <span class="ai-style-option-description">{{
                    style.description
                  }}</span>
                </div>
              </mat-option>
            </mat-select>
            <mat-hint class="ai-style-hint">
              Style changes the type of response. Depth is controlled by AI
              Verbosity in Customisation.
            </mat-hint>
          </mat-form-field>

          <!-- Mood Selection -->
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>How are you feeling?</mat-label>
            <mat-select [(ngModel)]="selectedMood" name="mood">
              <mat-option value="">Not specified</mat-option>
              <mat-option *ngFor="let mood of moodOptions" [value]="mood.value">
                {{ mood.emoji }} {{ mood.label }}
              </mat-option>
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Title</mat-label>
            <input matInput [(ngModel)]="entryTitle" name="title" />
          </mat-form-field>

          <!-- Content field only for daily entries -->
          <mat-form-field
            appearance="outline"
            class="full-width"
            *ngIf="selectedType === 'daily'"
          >
            <mat-label>Describe your day</mat-label>
            <textarea
              matInput
              [(ngModel)]="content"
              name="content"
              rows="10"
              placeholder="Share highlights, themes, or key moments..."
            ></textarea>
          </mat-form-field>

          <!-- Dream-specific fields -->
          <div *ngIf="selectedType === 'dream'" class="dream-fields">
            <h3>Dream Details (Optional)</h3>

            <div class="dream-row">
              <mat-form-field appearance="outline" class="half-width">
                <mat-label>Cast (Who was in your dream?)</mat-label>
                <textarea
                  matInput
                  [(ngModel)]="dreamCast"
                  name="dreamCast"
                  rows="2"
                ></textarea>
              </mat-form-field>

              <mat-form-field appearance="outline" class="half-width">
                <mat-label>Location</mat-label>
                <input
                  matInput
                  [(ngModel)]="dreamLocation"
                  name="dreamLocation"
                  placeholder="Describe the location"
                />
              </mat-form-field>
            </div>

            <div class="dream-row">
              <mat-form-field appearance="outline" class="half-width">
                <mat-label>Time Period</mat-label>
                <mat-select [(ngModel)]="dreamPeriod" name="dreamPeriod">
                  <mat-option value="">Type custom period below...</mat-option>
                  <mat-option
                    *ngFor="let period of dreamFieldOptions.periods"
                    [value]="period"
                  >
                    {{ period }}
                  </mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" class="half-width">
                <mat-label>Primary Emotion</mat-label>
                <mat-select [(ngModel)]="dreamEmotion" name="dreamEmotion">
                  <mat-option value="">Type custom emotion below...</mat-option>
                  <mat-option
                    *ngFor="let emotion of dreamFieldOptions.emotions"
                    [value]="emotion"
                  >
                    {{ emotion }}
                  </mat-option>
                </mat-select>
              </mat-form-field>
            </div>

            <div
              class="dream-row"
              *ngIf="dreamPeriod === '' || dreamEmotion === ''"
            >
              <mat-form-field
                appearance="outline"
                class="half-width"
                *ngIf="dreamPeriod === ''"
              >
                <mat-label>Custom Time Period</mat-label>
                <input
                  matInput
                  [(ngModel)]="dreamPeriod"
                  name="dreamPeriodCustom"
                  placeholder="Describe the time period"
                />
              </mat-form-field>

              <mat-form-field
                appearance="outline"
                class="half-width"
                *ngIf="dreamEmotion === ''"
              >
                <mat-label>Custom Emotion</mat-label>
                <input
                  matInput
                  [(ngModel)]="dreamEmotion"
                  name="dreamEmotionCustom"
                  placeholder="Describe the emotion"
                />
              </mat-form-field>
            </div>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Symbols & Imagery</mat-label>
              <textarea
                matInput
                [(ngModel)]="dreamSymbolsAndImagery"
                name="dreamSymbols"
                rows="3"
                placeholder="Notable symbols, colors, objects, or imagery"
              ></textarea>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Personal Insight</mat-label>
              <textarea
                matInput
                [(ngModel)]="dreamInsight"
                name="dreamInsight"
                rows="3"
                placeholder="What do you think this dream might mean?"
              ></textarea>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Actions Taken</mat-label>
              <textarea
                matInput
                [(ngModel)]="dreamAction"
                name="dreamAction"
                rows="2"
                placeholder="What did you do in the dream?"
              ></textarea>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Plot / Narrative</mat-label>
              <textarea
                matInput
                [(ngModel)]="dreamPlot"
                name="dreamPlot"
                rows="5"
                placeholder="Describe what happened in your dream"
              ></textarea>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Other Details</mat-label>
              <textarea
                matInput
                [(ngModel)]="dreamOther"
                name="dreamOther"
                rows="2"
                placeholder="Any other important details"
              ></textarea>
            </mat-form-field>
          </div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>My Tags</mat-label>
            <mat-chip-grid #chipGrid>
              <mat-chip-row *ngFor="let tag of tags" (removed)="removeTag(tag)">
                {{ tag }}
                <button matChipRemove type="button">
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
              <input
                placeholder="Type and press enter"
                [matChipInputFor]="chipGrid"
                [matChipInputSeparatorKeyCodes]="separatorKeysCodes"
                [matChipInputAddOnBlur]="true"
                (matChipInputTokenEnd)="addTag($event)"
                (keydown.tab)="handleChipInputTab($event, tags)"
              />
            </mat-chip-grid>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>People</mat-label>
            <mat-chip-grid #peopleChipGrid>
              <mat-chip-row
                *ngFor="let person of peopleNames"
                (removed)="removePeopleName(person)"
              >
                {{ person }}
                <button matChipRemove type="button">
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
              <input
                placeholder="Type and press enter"
                [matChipInputFor]="peopleChipGrid"
                [matChipInputSeparatorKeyCodes]="separatorKeysCodes"
                [matChipInputAddOnBlur]="true"
                (matChipInputTokenEnd)="addPeopleName($event)"
                (keydown.tab)="handleChipInputTab($event, peopleNames)"
              />
            </mat-chip-grid>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Places</mat-label>
            <mat-chip-grid #placesChipGrid>
              <mat-chip-row
                *ngFor="let place of places"
                (removed)="removePlace(place)"
              >
                {{ place }}
                <button matChipRemove type="button">
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
              <input
                placeholder="Type and press enter"
                [matChipInputFor]="placesChipGrid"
                [matChipInputSeparatorKeyCodes]="separatorKeysCodes"
                [matChipInputAddOnBlur]="true"
                (matChipInputTokenEnd)="addPlace($event)"
                (keydown.tab)="handleChipInputTab($event, places)"
              />
            </mat-chip-grid>
          </mat-form-field>

          <section class="entry-attachments" aria-label="Pending attachments">
            <div class="entry-attachments-header">
              <div>
                <h3>Attachments</h3>
                <p>
                  Add up to {{ maxAttachmentsPerEntry }} files. Images and PDFs
                  up to 10 MB, audio up to 25 MB.
                </p>
              </div>
              <div class="entry-attachments-actions">
                <input
                  #pendingAttachmentInput
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.mp3,.wav,.m4a,.ogg,.webm,.aiff,image/png,image/jpeg,image/webp,audio/mpeg,audio/mp3,audio/wav,audio/x-wav,audio/ogg,audio/mp4,audio/x-m4a,audio/webm,audio/aiff,audio/x-aiff,application/pdf"
                  class="hidden"
                  (change)="onPendingAttachmentSelected($event)"
                />
                <button
                  mat-stroked-button
                  type="button"
                  (click)="triggerPendingAttachmentSelection()"
                  [disabled]="!canAddPendingAttachment() || isSaving"
                >
                  <mat-icon>attach_file</mat-icon>
                  Add attachment
                </button>
              </div>
            </div>

            <p class="attachment-limit-copy">
              {{ getTotalAttachmentCount() }} / {{ maxAttachmentsPerEntry }}
              attachments selected
            </p>

            <div
              class="entry-attachments-list"
              *ngIf="pendingAttachments.length || existingAttachments.length; else noPendingAttachments"
            >
              <article
                class="entry-attachment-row existing"
                *ngFor="let attachment of existingAttachments"
              >
                <a
                  class="entry-attachment-preview"
                  [href]="attachment.url"
                  target="_blank"
                  rel="noopener"
                  [attr.aria-label]="'Open ' + attachment.original_filename"
                  [class.image]="attachment.is_image"
                  [class.audio]="attachment.is_audio"
                  [class.pdf]="attachment.is_pdf"
                >
                  <img
                    *ngIf="attachment.is_image"
                    [src]="attachment.url"
                    [alt]="attachment.original_filename"
                  />
                  <div class="entry-attachment-pdf-tile" *ngIf="attachment.is_pdf">
                    <mat-icon>picture_as_pdf</mat-icon>
                    <span>PDF</span>
                  </div>
                  <div class="entry-attachment-audio-tile" *ngIf="attachment.is_audio">
                    <mat-icon>graphic_eq</mat-icon>
                    <span>Audio</span>
                  </div>
                </a>
                <div class="entry-attachment-copy">
                  <h4>{{ attachment.original_filename }}</h4>
                  <p>
                    Existing attachment
                    <span *ngIf="attachment.file_size_bytes">
                      · {{ formatAttachmentFileSize(attachment.file_size_bytes) }}
                    </span>
                  </p>
                  <audio
                    *ngIf="attachment.is_audio"
                    class="entry-attachment-inline-audio"
                    controls
                    preload="metadata"
                    [src]="attachment.url"
                    [attr.aria-label]="'Audio preview for ' + attachment.original_filename"
                  ></audio>
                  <div
                    class="entry-attachment-derived-text"
                    *ngIf="attachment.has_derived_text && attachment.derived_text"
                  >
                    <p class="entry-attachment-derived-text-label">
                      {{ getAttachmentDerivedTextLabel(attachment) }}
                    </p>
                    <p>{{ getAttachmentDerivedTextPreview(attachment) }}</p>
                    <button
                      mat-button
                      type="button"
                      class="entry-attachment-derived-text-toggle"
                      (click)="openAttachmentDerivedText(attachment)"
                    >
                      View derived text
                    </button>
                  </div>
                  <p
                    class="entry-attachment-audio-note"
                    *ngIf="attachment.is_audio && !attachment.has_derived_text"
                  >
                    AI can only use this audio after you transcribe it from the
                    saved entry view.
                  </p>
                  <p
                    class="entry-attachment-audio-note"
                    *ngIf="attachment.is_pdf && !attachment.has_derived_text"
                  >
                    No derived text is saved for this PDF yet.
                  </p>
                </div>
                <div class="entry-attachment-row-actions">
                  <button
                    *ngIf="attachment.is_pdf"
                    mat-stroked-button
                    type="button"
                    (click)="deriveAttachmentText(attachment)"
                    [disabled]="isSaving || isDerivingAttachmentText(attachment)"
                  >
                    <mat-icon>{{
                      isDerivingAttachmentText(attachment) ? "hourglass_top" : "find_in_page"
                    }}</mat-icon>
                    {{
                      isDerivingAttachmentText(attachment)
                        ? "Refreshing…"
                        : attachment.has_derived_text
                          ? "Refresh derived text"
                          : "Derive text"
                    }}
                  </button>
                  <a
                    class="entry-attachment-open-link"
                    [href]="attachment.url"
                    target="_blank"
                    rel="noopener"
                  >
                    <mat-icon>open_in_new</mat-icon>
                    Open
                  </a>
                  <button
                    mat-stroked-button
                    color="warn"
                    type="button"
                    (click)="markAttachmentForRemoval(attachment)"
                    [disabled]="isSaving"
                  >
                    <mat-icon>delete</mat-icon>
                    Remove
                  </button>
                </div>
              </article>

              <article
                class="entry-attachment-row pending"
                *ngFor="let attachment of pendingAttachments; let index = index"
              >
                <div
                  class="entry-attachment-preview"
                  [class.image]="attachment.kind === 'image'"
                  [class.audio]="attachment.kind === 'audio'"
                  [class.pdf]="attachment.kind === 'pdf'"
                >
                  <img
                    *ngIf="attachment.kind === 'image' && attachment.previewUrl"
                    [src]="attachment.previewUrl"
                    [alt]="attachment.file.name"
                  />
                  <div class="entry-attachment-pdf-tile" *ngIf="attachment.kind === 'pdf'">
                    <mat-icon>picture_as_pdf</mat-icon>
                    <span>PDF</span>
                  </div>
                  <div class="entry-attachment-audio-tile" *ngIf="attachment.kind === 'audio'">
                    <mat-icon>graphic_eq</mat-icon>
                    <span>Audio</span>
                  </div>
                </div>
                <div class="entry-attachment-copy">
                  <h4>{{ attachment.file.name }}</h4>
                  <p>
                    {{ getPendingAttachmentTypeLabel(attachment) }} · Pending upload ·
                    {{ formatAttachmentFileSize(attachment.file.size) }}
                  </p>
                  <audio
                    *ngIf="attachment.kind === 'audio' && attachment.previewUrl"
                    class="entry-attachment-inline-audio"
                    controls
                    preload="metadata"
                    [src]="attachment.previewUrl"
                    [attr.aria-label]="'Audio preview for ' + attachment.file.name"
                  ></audio>
                  <p
                    class="entry-attachment-audio-note"
                    *ngIf="attachment.kind === 'audio'"
                  >
                    AI can only use this audio after you save the entry and
                    transcribe it from the entry view.
                  </p>
                </div>
                <button
                  mat-stroked-button
                  color="warn"
                  type="button"
                  (click)="removePendingAttachment(index)"
                  [disabled]="isSaving"
                >
                  <mat-icon>close</mat-icon>
                  Remove
                </button>
              </article>

              <article
                class="entry-attachment-row removal"
                *ngFor="let attachment of attachmentsMarkedForRemoval"
              >
                <div class="entry-attachment-preview removal-state">
                  <mat-icon>delete_outline</mat-icon>
                </div>
                <div class="entry-attachment-copy">
                  <h4>{{ attachment.original_filename }}</h4>
                  <p>
                    Marked for deletion on save
                    <span *ngIf="attachment.file_size_bytes">
                      · {{ formatAttachmentFileSize(attachment.file_size_bytes) }}
                    </span>
                  </p>
                </div>
                <button
                  mat-stroked-button
                  type="button"
                  (click)="restoreMarkedAttachment(attachment)"
                  [disabled]="isSaving"
                >
                  <mat-icon>undo</mat-icon>
                  Undo
                </button>
              </article>
            </div>

            <ng-template #noPendingAttachments>
              <div class="entry-attachments-empty">
                <mat-icon>attachment</mat-icon>
                <p>No attachments selected yet.</p>
              </div>
            </ng-template>
          </section>
          </fieldset>

          <div class="save-progress" *ngIf="isSaving" aria-live="polite">
            <mat-progress-spinner
              mode="indeterminate"
              diameter="22"
              strokeWidth="3"
            ></mat-progress-spinner>
            <div class="save-progress-copy">
              <strong>{{ getSaveProgressTitle() }}</strong>
              <span>{{ getSaveProgressDescription() }}</span>
            </div>
          </div>

          <div class="actions">
            <button
              mat-stroked-button
              color="warn"
              (click)="cancelCreate()"
              [disabled]="isSaving"
            >
              Cancel
            </button>

            <ng-container *ngIf="!leaveItToAI; else aiActions">
              <button
                mat-raised-button
                color="primary"
                (click)="saveAsDraft()"
                [disabled]="isSaving"
              >
                {{ isSaving ? "Saving…" : "Save Entry" }}
              </button>
            </ng-container>

            <ng-template #aiActions>
              <button
                mat-raised-button
                color="primary"
                (click)="saveAndAnalyse()"
                [disabled]="isSaving"
              >
                {{ isSaving ? "Saving & analysing…" : "Save & Analyse" }}
              </button>
            </ng-template>
          </div>

          <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
        </mat-card-content>
      </mat-card>

      <app-back-to-top />
    </div>
  `,
  styles: [
    `
      .create-container {
        max-width: 800px;
        margin: 0 auto;
      }

      .full-width {
        width: 100%;
        margin-bottom: var(--spacing-sm);
      }

      .half-width {
        width: calc(50% - 8px);
        margin-bottom: var(--spacing-sm);
      }

      .dream-fields {
        margin: var(--spacing-md) 0;
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background-color: var(--colour-surface-muted);
      }

      .dream-fields h3 {
        margin: 0 0 var(--spacing-md) 0;
        color: var(--colour-text-primary);
        font-weight: 600;
      }

      .entry-form-shell {
        margin: 0;
        padding: 0;
        border: 0;
        min-width: 0;
      }

      .entry-form-shell[disabled] {
        opacity: 0.78;
      }

      .dream-row {
        display: flex;
        gap: var(--spacing-md);
        align-items: flex-start;
      }

      .dream-row mat-form-field {
        flex: 1;
      }

      .entry-type-toggle {
        margin-bottom: var(--spacing-sm);
      }

      .hint {
        margin-bottom: var(--spacing-sm);
        color: var(--colour-text-secondary);
      }

      .subtle-hint {
        margin-top: calc(var(--spacing-sm) * -0.5);
        font-size: 0.92rem;
      }

      .actions {
        display: flex;
        gap: var(--spacing-sm);
        justify-content: flex-end;
        margin-top: var(--spacing-sm);
      }

      .save-progress {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-top: var(--spacing-sm);
        padding: 0.8rem 0.9rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .save-progress-copy {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
      }

      .save-progress-copy strong {
        font-size: 0.95rem;
      }

      .save-progress-copy span {
        color: var(--colour-text-secondary);
        font-size: 0.88rem;
        line-height: 1.4;
      }

      .ai-style-option {
        display: flex;
        flex-direction: column;
        gap: 0.18rem;
        padding: 0.15rem 0;
        white-space: normal;
      }

      .ai-style-option-label {
        font-weight: 700;
        line-height: 1.3;
      }

      .ai-style-option-description {
        color: var(--colour-text-secondary);
        font-size: 0.86rem;
        line-height: 1.35;
      }

      .ai-style-hint {
        line-height: 1.35;
      }

      .entry-attachments {
        margin: var(--spacing-md) 0;
        padding: 0.85rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .entry-attachments-header {
        display: flex;
        justify-content: space-between;
        gap: var(--spacing-md);
        align-items: flex-start;
      }

      .entry-attachments-header h3,
      .entry-attachment-copy h4 {
        margin: 0;
      }

      .entry-attachments-header p,
      .attachment-limit-copy,
      .entry-attachment-copy p {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .entry-attachments-actions {
        display: flex;
        justify-content: flex-end;
      }

      .attachment-limit-copy {
        margin-top: var(--spacing-sm);
        font-size: 0.92rem;
      }

      .entry-attachments-list {
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
        margin-top: var(--spacing-sm);
      }

      .entry-attachment-row {
        display: flex;
        align-items: center;
        gap: 0.7rem;
        padding: 0.55rem 0.65rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }

      .entry-attachment-preview {
        width: 3rem;
        min-width: 3rem;
        height: 3rem;
        border-radius: var(--radius-sm);
        border: 1px solid var(--colour-border);
        background:
          linear-gradient(180deg, rgba(15, 23, 42, 0.08), rgba(15, 23, 42, 0.18)),
          var(--colour-surface-muted);
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        color: inherit;
      }

      .entry-attachment-preview:focus-visible {
        outline: 2px solid var(--colour-primary);
        outline-offset: 2px;
      }

      .entry-attachment-preview img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .entry-attachment-pdf-tile,
      .entry-attachment-audio-tile {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
        align-items: center;
        color: var(--colour-text-primary);
        font-size: 0.72rem;
      }

      .entry-attachment-pdf-tile mat-icon,
      .entry-attachment-audio-tile mat-icon {
        width: 1rem;
        height: 1rem;
        font-size: 1rem;
      }

      .entry-attachment-copy {
        flex: 1;
        min-width: 0;
      }

      .entry-attachment-inline-audio {
        display: block;
        width: min(100%, 18rem);
        margin-top: 0.45rem;
      }

      .entry-attachment-audio-note {
        margin-top: 0.45rem;
        font-size: 0.8rem;
        line-height: 1.4;
        color: var(--colour-text-secondary);
      }

      .entry-attachments-empty {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        margin-top: var(--spacing-sm);
        padding: var(--spacing-sm);
        border-radius: var(--radius-md);
        background: var(--colour-surface);
        border: 1px dashed var(--colour-border);
        color: var(--colour-text-secondary);
        font-size: 0.92rem;
      }

      .entry-attachment-row-actions {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
      }

      .entry-attachment-preview.removal-state {
        color: var(--colour-text-secondary);
      }

      .entry-attachment-open-link {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        color: var(--colour-primary);
        text-decoration: underline;
        text-underline-offset: 0.12rem;
        font-weight: 600;
        white-space: nowrap;
      }

      .entry-attachment-open-link:focus-visible {
        outline: 2px solid var(--colour-primary);
        outline-offset: 2px;
        border-radius: var(--radius-sm);
      }

      .hidden {
        display: none;
      }

      mat-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--spacing-md);
        gap: var(--spacing-sm);
      }

      mat-card-title {
        margin: 0;
      }

      .header-back {
        border-color: var(--colour-border);
        color: var(--colour-text-secondary);
      }

      .header-back mat-icon {
        margin-right: var(--spacing-xs);
      }

      mat-card {
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }

      .error {
        color: #b91c1c;
        margin-top: var(--spacing-sm);
      }

      @media (max-width: 768px) {
        mat-card-header {
          flex-direction: column;
          align-items: stretch;
        }

        .header-back {
          align-self: flex-start;
        }

        .entry-attachments-header {
          flex-direction: column;
        }

        .entry-attachments-actions {
          width: 100%;
          justify-content: flex-start;
        }

        .entry-attachment-row {
          align-items: flex-start;
        }

        .entry-attachment-row-actions {
          width: 100%;
        }

        .actions {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class CreateComponent implements OnInit, OnDestroy {
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private appDialog = inject(AppDialogService);
  private authService = inject(AuthService);
  private entriesService = inject(EntriesService);
  private analysisService = inject(AnalysisService);
  @ViewChild("pendingAttachmentInput")
  pendingAttachmentInput?: ElementRef<HTMLInputElement>;

  backQueryParams: Record<string, string | number> = {};
  readonly maxAttachmentsPerEntry = MAX_ATTACHMENTS_PER_ENTRY;

  entryDate: Date | string | null = new Date();
  entryTime = this.getCurrentLocalTime();
  entryTitle = "";
  content = "";
  tags: string[] = [];
  peopleNames: string[] = [];
  places: string[] = [];
  leaveItToAI = false;
  allowAiAttachmentContext = false;
  selectedType: "daily" | "dream" = "daily";
  private previousSelectedType: "daily" | "dream" = "daily";
  isSaving = false;
  errorMessage = "";
  maxDate = new Date();
  isEditing = false;
  editingId: number | null = null;
  existingAttachments: EntryAsset[] = [];
  attachmentsMarkedForRemoval: EntryAsset[] = [];
  pendingAttachments: PendingAttachment[] = [];
  derivingAttachmentTextIds = new Set<number>();

  // Enhanced fields for both entry types
  selectedMood = "";
  selectedAIStyle = "friendly";

  // Dream-specific fields matching database schema
  dreamCast = "";
  dreamLocation = "";
  dreamPeriod = "";
  dreamEmotion = "";
  dreamPlot = "";
  dreamSymbolsAndImagery = "";
  dreamInsight = "";
  dreamAction = "";
  dreamOther = "";

  readonly separatorKeysCodes = [ENTER, COMMA] as const;
  private initialDate = this.describeEntryDate(this.entryDate);
  private initialTime = this.entryTime;

  // Mood options for both entry types
  moodOptions: MoodOption[] = [
    { emoji: "😊", label: "Happy", value: "happy" },
    { emoji: "😔", label: "Sad", value: "sad" },
    { emoji: "😴", label: "Tired", value: "tired" },
    { emoji: "😰", label: "Anxious", value: "anxious" },
    { emoji: "😡", label: "Angry", value: "angry" },
    { emoji: "🤔", label: "Thoughtful", value: "thoughtful" },
    { emoji: "😌", label: "Peaceful", value: "peaceful" },
    { emoji: "🤗", label: "Grateful", value: "grateful" },
    { emoji: "😕", label: "Confused", value: "confused" },
    { emoji: "💪", label: "Energetic", value: "energetic" },
  ];

  // AI style options for both entry types
  aiStyleOptions: AIStyleOption[] = [
    {
      label: "Friendly & Supportive",
      value: "friendly",
      description: "Warm, encouraging responses",
    },
    {
      label: "Professional & Clinical",
      value: "clinical",
      description: "Structured, therapeutic approach",
    },
    {
      label: "Reflective & Deep",
      value: "reflective",
      description: "Thoughtful, introspective analysis",
    },
    {
      label: "Brief & Practical",
      value: "brief",
      description: "Concise, actionable insights",
    },
    {
      label: "Creative & Symbolic",
      value: "creative",
      description: "Metaphorical, artistic interpretation",
    },
  ];

  getSelectedAIStyleLabel(): string {
    return (
      this.aiStyleOptions.find((style) => style.value === this.selectedAIStyle)
        ?.label || "Friendly & Supportive"
    );
  }

  // Dream field options with common values
  dreamFieldOptions: DreamFieldOptions = {
    emotions: [
      "Joy",
      "Fear",
      "Anger",
      "Sadness",
      "Surprise",
      "Disgust",
      "Love",
      "Anxiety",
      "Excitement",
      "Confusion",
      "Peace",
      "Frustration",
    ],
    periods: [
      "Childhood",
      "Teenage years",
      "Present day",
      "Future",
      "Past life",
      "Medieval times",
      "Victorian era",
      "Ancient times",
      "Dystopian future",
      "Timeless",
    ],
  };

  ngOnInit(): void {
    this.applyAttachmentContextDefault();
    this.captureBackQueryParams();

    // Check for pre-populated date and type from query params
    this.route.queryParamMap.subscribe((params) => {
      const dateParam = params.get("date");
      if (dateParam) {
        // Parse UK format date DD/MM/YYYY
        const [day, month, year] = dateParam.split("/");
        if (day && month && year) {
          const parsedDate = new Date(
            parseInt(year),
            parseInt(month) - 1,
            parseInt(day),
          );
          if (!isNaN(parsedDate.getTime())) {
            this.entryDate = parsedDate;
            this.initialDate = this.entryDate.toDateString();
          }
        }
      }

      // Check for entry type parameter
      const typeParam = params.get("type");
      if (typeParam === "dream" || typeParam === "daily") {
      this.selectedType = typeParam;
      this.previousSelectedType = typeParam;
      }

    });

    // Check for id parameter for editing
    const id = this.route.snapshot.paramMap.get("id");
    if (id) {
      this.isEditing = true;
      this.editingId = Number(id);
      this.loadEntryForEditing(this.editingId);
    }
  }

  ngOnDestroy(): void {
    this.clearPendingAttachments();
  }

  loadEntryForEditing(id: number): void {
    // Try loading as daily first
    this.entriesService.getDailyEntry(id).subscribe({
      next: (entry) => {
        this.populateForm(entry, "daily");
      },
      error: () => {
        this.entriesService.getDreamEntry(id).subscribe((entry) => {
          this.populateForm(entry, "dream");
        });
      },
    });
  }

  populateForm(entry: any, type: "daily" | "dream"): void {
    this.selectedType = type;
    this.previousSelectedType = type;
    this.clearPendingAttachments();
    this.attachmentsMarkedForRemoval = [];
    this.existingAttachments = Array.isArray(entry.attachments)
      ? [...entry.attachments]
      : [];
    this.applyAttachmentContextDefault();
    this.entryDate = this.parseApiDateAsLocal(entry.entry_date) ?? new Date();
    this.entryTime = this.coerceEntryTime(entry.entry_time) ?? this.getCurrentLocalTime();
    this.initialDate = this.describeEntryDate(this.entryDate);
    this.initialTime = this.entryTime;
    this.entryTitle = entry.title || "";
    this.tags = entry.tags
      ? entry.tags
          .split(",")
          .map((t: string) => t.trim())
          .filter((t: string) => t)
      : [];
    this.selectedMood = entry.mood || "";
    this.selectedAIStyle = entry.ai_style || "friendly";

    if (type === "daily") {
      this.content = entry.user_message || "";
      this.peopleNames = entry.daily_people_names
        ? entry.daily_people_names
            .split(",")
            .map((p: string) => p.trim())
            .filter((p: string) => p)
        : [];
      this.places = entry.daily_places
        ? entry.daily_places
            .split(",")
            .map((p: string) => p.trim())
            .filter((p: string) => p)
        : [];
    } else {
      this.dreamCast = entry.cast || "";
      this.dreamLocation = entry.location || "";
      this.dreamPeriod = entry.period || "";
      this.dreamEmotion = entry.emotion || "";
      this.dreamPlot = entry.plot || "";
      this.dreamSymbolsAndImagery = entry.symbols_and_imagery || "";
      this.dreamInsight = entry.insight || "";
      this.dreamAction = entry.action || "";
      this.dreamOther = entry.other || "";
      this.peopleNames = entry.dream_people_names
        ? entry.dream_people_names
            .split(",")
            .map((p: string) => p.trim())
            .filter((p: string) => p)
        : [];
      this.places = entry.dream_places
        ? entry.dream_places
            .split(",")
            .map((p: string) => p.trim())
            .filter((p: string) => p)
        : [];
    }
  }

  saveAsDraft(): void {
    this.persistEntry(this.isEditing && this.leaveItToAI);
  }

  saveAndAnalyse(): void {
    this.persistEntry(true);
  }

  private persistEntry(shouldAnalyse: boolean): void {
    this.errorMessage = "";

    const normalisedEntryDate = this.coerceEntryDate(this.entryDate);

    if (!normalisedEntryDate) {
      this.errorMessage = "Please select a date for this entry.";
      return;
    }

    if (this.isFutureDate(normalisedEntryDate)) {
      this.errorMessage = "Entries cannot be created or moved to a future date.";
      return;
    }

    this.entryDate = normalisedEntryDate;

    // Content validation - required for daily entries, optional for dreams
    if (this.selectedType === "daily" && !this.content.trim()) {
      this.errorMessage = "Please add some notes so the AI has context.";
      return;
    }

    this.isSaving = true;
    const entryDate = this.serialiseDateAsLocalIso(normalisedEntryDate);
    const entryTime = this.coerceEntryTime(this.entryTime);
    const tags = this.tags.join(",");
    const trimmedTitle = this.entryTitle.trim();
    const body = this.content.trim();

    if (!entryTime) {
      this.errorMessage = "Please select a valid time for this entry.";
      this.isSaving = false;
      return;
    }

    if (this.selectedType === "daily") {
      const createPayload = {
        entry_date: entryDate,
        entry_time: entryTime,
        title: trimmedTitle,
        user_message: body,
        tags,
        mood: this.selectedMood,
        ai_style: this.selectedAIStyle,
        daily_people_names: this.peopleNames.join(","),
        daily_places: this.places.join(","),
      };

      const updatePayload = {
        entry_date: entryDate,
        entry_time: entryTime,
        title: trimmedTitle,
        user_message: body,
        tags,
        mood: this.selectedMood,
        ai_style: this.selectedAIStyle,
        daily_people_names: this.peopleNames.join(","),
        daily_places: this.places.join(","),
      };

      if (this.isEditing && this.editingId !== null) {
        this.entriesService
          .updateDailyEntry(this.editingId, updatePayload)
          .subscribe({
            next: () =>
              void this.handleEntrySaved(
                this.editingId!,
                "daily",
                shouldAnalyse,
              ),
            error: (error) =>
              this.handleSaveError(
                error,
                "Failed to update your daily entry.",
              ),
          });
      } else {
        this.entriesService.createDailyEntry(createPayload).subscribe({
          next: (created) =>
            void this.handleEntrySaved(created.id!, "daily", shouldAnalyse),
          error: (error) =>
            this.handleSaveError(error, "Failed to save your daily entry."),
        });
      }
    } else {
      const dreamPlotContent = this.dreamPlot.trim() || "Dream entry";

      const createPayload = {
        entry_date: entryDate,
        entry_time: entryTime,
        title: trimmedTitle,
        plot: dreamPlotContent,
        tags,
        mood: this.selectedMood,
        ai_style: this.selectedAIStyle,
        cast: this.dreamCast.trim(),
        location: this.dreamLocation.trim(),
        period: this.dreamPeriod.trim(),
        emotion: this.dreamEmotion.trim(),
        symbols_and_imagery: this.dreamSymbolsAndImagery.trim(),
        insight: this.dreamInsight.trim(),
        action: this.dreamAction.trim(),
        other: this.dreamOther.trim(),
        dream_people_names: this.peopleNames.join(","),
        dream_places: this.places.join(","),
      };

      const updatePayload = {
        entry_date: entryDate,
        entry_time: entryTime,
        title: trimmedTitle,
        plot: dreamPlotContent,
        tags,
        mood: this.selectedMood,
        ai_style: this.selectedAIStyle,
        cast: this.dreamCast.trim(),
        location: this.dreamLocation.trim(),
        period: this.dreamPeriod.trim(),
        emotion: this.dreamEmotion.trim(),
        symbols_and_imagery: this.dreamSymbolsAndImagery.trim(),
        insight: this.dreamInsight.trim(),
        action: this.dreamAction.trim(),
        other: this.dreamOther.trim(),
        dream_people_names: this.peopleNames.join(","),
        dream_places: this.places.join(","),
      };

      if (this.isEditing && this.editingId !== null) {
        this.entriesService
          .updateDreamEntry(this.editingId, updatePayload)
          .subscribe({
            next: () =>
              void this.handleEntrySaved(
                this.editingId!,
                "dream",
                shouldAnalyse,
              ),
            error: (error) =>
              this.handleSaveError(
                error,
                "Failed to update your dream entry.",
              ),
          });
      } else {
        this.entriesService.createDreamEntry(createPayload).subscribe({
          next: (created) =>
            void this.handleEntrySaved(created.id!, "dream", shouldAnalyse),
          error: (error) =>
            this.handleSaveError(error, "Failed to save your dream entry."),
        });
      }
    }
  }

  private async handleEntrySaved(
    entryId: number,
    entryType: "daily" | "dream",
    shouldAnalyse: boolean,
  ): Promise<void> {
    const shouldRevealAttachments = this.pendingAttachments.length > 0;
    const failedDeletedAttachmentNames =
      await this.deleteMarkedAttachments(entryId, entryType);
    const failedAttachmentNames = await this.uploadPendingAttachments(
      entryId,
      entryType,
    );
    const analysisWarning = shouldAnalyse
      ? await (entryType === "daily"
          ? this.runDailyAnalysis(entryId)
          : this.runDreamAnalysis(entryId))
      : undefined;

    const attachmentMessages: string[] = [];
    if (failedAttachmentNames.length) {
      attachmentMessages.push(
        `these attachments failed to upload: ${failedAttachmentNames.join(", ")}`,
      );
    }
    if (failedDeletedAttachmentNames.length) {
      attachmentMessages.push(
        `these attachments could not be deleted: ${failedDeletedAttachmentNames.join(", ")}`,
      );
    }
    const attachmentWarning = attachmentMessages.length
      ? `Your entry was saved, but ${attachmentMessages.join("; ")}.`
      : undefined;

    this.finishNavigation(entryId, {
      analysisWarning,
      attachmentWarning,
      showAttachments: shouldRevealAttachments,
    });
  }

  private async runDailyAnalysis(entryId: number): Promise<string | undefined> {
    const analysisDate = this.coerceEntryDate(this.entryDate);
    const referenceDate = analysisDate
      ? this.serialiseDateAsLocalIso(analysisDate)
      : undefined;

    try {
      const analysis = await firstValueFrom(
        this.analysisService.analyseText({
          mode: "daily",
          text: this.content,
          reference_date: referenceDate,
          entry_id: entryId,
          include_attachment_context: this.allowAiAttachmentContext,
          ai_style: this.selectedAIStyle,
        }),
      );

      const dailyAnalysis = analysis as DailyAnalysisResponse;
      const analysisAttachmentRefs = this.serialiseAnalysisAttachmentRefs(
        dailyAnalysis.attachment_context_refs,
      );
      try {
        await firstValueFrom(
          this.entriesService.updateDailyEntry(entryId, {
            ai_response: dailyAnalysis.ai_response,
            analysis_attachment_refs: analysisAttachmentRefs,
            tags: this.tags.length ? this.tags.join(",") : dailyAnalysis.tags,
            daily_people_names: this.peopleNames.length
              ? this.peopleNames.join(",")
              : dailyAnalysis.daily_people_names,
            daily_places: this.places.length
              ? this.places.join(",")
              : dailyAnalysis.daily_places,
          }),
        );
        return undefined;
      } catch {
        return "ai-save-failed";
      }
    } catch (error) {
      if (this.isRateLimitAnalysisError(error)) {
        return "ai-rate-limit";
      }

      return undefined;
    }
  }

  private async runDreamAnalysis(entryId: number): Promise<string | undefined> {
    // For dream analysis, use the plot field or combine dream fields
    const analysisText =
      this.dreamPlot.trim() ||
      `Cast: ${this.dreamCast} Location: ${this.dreamLocation} Plot: ${this.dreamPlot} Emotion: ${this.dreamEmotion}`;
    const analysisDate = this.coerceEntryDate(this.entryDate);
    const referenceDate = analysisDate
      ? this.serialiseDateAsLocalIso(analysisDate)
      : undefined;

    try {
      const analysis = await firstValueFrom(
        this.analysisService.analyseText({
          mode: "dream",
          text: analysisText,
          reference_date: referenceDate,
          entry_id: entryId,
          include_attachment_context: this.allowAiAttachmentContext,
          ai_style: this.selectedAIStyle,
        }),
      );

      const dreamAnalysis = analysis as DreamAnalysisResponse;
      const analysisAttachmentRefs = this.serialiseAnalysisAttachmentRefs(
        dreamAnalysis.attachment_context_refs,
      );
      try {
        await firstValueFrom(
          this.entriesService.updateDreamEntry(entryId, {
            summary: dreamAnalysis.summary,
            interpretation: dreamAnalysis.interpretation,
            image_prompt: dreamAnalysis.image_prompt,
            analysis_attachment_refs: analysisAttachmentRefs,
            tags: this.tags.length ? this.tags.join(",") : dreamAnalysis.tags,
            dream_people_names: this.peopleNames.length
              ? this.peopleNames.join(",")
              : dreamAnalysis.dream_people_names,
            dream_places: this.places.length
              ? this.places.join(",")
              : dreamAnalysis.dream_places,
          }),
        );
        return undefined;
      } catch {
        return "ai-save-failed";
      }
    } catch (error) {
      if (this.isRateLimitAnalysisError(error)) {
        return "ai-rate-limit";
      }

      return undefined;
    }
  }

  private finishNavigation(
    entryId: number,
    warnings?: {
      analysisWarning?: string;
      attachmentWarning?: string;
      showAttachments?: boolean;
    },
  ): void {
    this.isSaving = false;
    this.resetForm();

    const queryParams =
      warnings?.analysisWarning ||
      warnings?.attachmentWarning ||
      warnings?.showAttachments
        ? {
            ...(warnings.analysisWarning
              ? { analysisWarning: warnings.analysisWarning }
              : {}),
            ...(warnings.attachmentWarning
              ? { attachmentWarning: warnings.attachmentWarning }
              : {}),
            ...(warnings.showAttachments ? { showAttachments: "1" } : {}),
          }
        : undefined;

    this.router.navigate(["/entries", entryId], { queryParams });
  }

  private isRateLimitAnalysisError(error: unknown): boolean {
    if (!(error instanceof HttpErrorResponse)) {
      return false;
    }

    if (error.status === 429) {
      return true;
    }

    const serialised = JSON.stringify(error.error ?? "").toLowerCase();
    return (
      serialised.includes("quota") ||
      serialised.includes("rate limit") ||
      serialised.includes("too many requests") ||
      serialised.includes("insufficient_quota")
    );
  }

  private handleError(message: string): void {
    this.isSaving = false;
    this.errorMessage = message;
  }

  private composeDailyMessage(title: string, body: string): string {
    if (title && body) {
      return `${title}\n\n${body}`;
    }
    if (title) {
      return title;
    }
    return body;
  }

  triggerPendingAttachmentSelection(): void {
    if (!this.canAddPendingAttachment()) {
      return;
    }

    this.pendingAttachmentInput?.nativeElement.click();
  }

  onPendingAttachmentSelected(event: Event): void {
    const input = event.target as HTMLInputElement | null;
    const files = Array.from(input?.files ?? []);
    if (input) {
      input.value = "";
    }

    if (!files.length) {
      return;
    }

    for (const file of files) {
      if (this.getTotalAttachmentCount() >= this.maxAttachmentsPerEntry) {
        this.errorMessage = `Each entry can have up to ${this.maxAttachmentsPerEntry} attachments.`;
        break;
      }

      const validationMessage = this.validateAttachmentFile(file);
      if (validationMessage) {
        this.errorMessage = validationMessage;
        continue;
      }

      this.pendingAttachments = [
        ...this.pendingAttachments,
        {
          file,
          previewUrl: this.createPendingAttachmentPreviewUrl(file),
          kind: this.getPendingAttachmentKind(file),
        },
      ];
      this.errorMessage = "";
    }
  }

  removePendingAttachment(index: number): void {
    const pending = this.pendingAttachments[index];
    if (!pending) {
      return;
    }

    this.releasePendingAttachment(pending);
    this.pendingAttachments = this.pendingAttachments.filter(
      (_, itemIndex) => itemIndex !== index,
    );
  }

  getTotalAttachmentCount(): number {
    return this.existingAttachments.length + this.pendingAttachments.length;
  }

  canAddPendingAttachment(): boolean {
    return this.getTotalAttachmentCount() < this.maxAttachmentsPerEntry;
  }

  formatAttachmentFileSize(sizeBytes: number): string {
    if (!sizeBytes || sizeBytes < 1024) {
      return `${sizeBytes || 0} B`;
    }
    if (sizeBytes < 1024 * 1024) {
      return `${(sizeBytes / 1024).toFixed(1)} KB`;
    }
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  getPendingAttachmentTypeLabel(attachment: PendingAttachment): string {
    if (attachment.kind === "pdf") {
      return "PDF";
    }
    if (attachment.kind === "audio") {
      return "Audio";
    }
    if (attachment.kind === "image") {
      return "Image";
    }
    return "Attachment";
  }

  getAttachmentDerivedTextLabel(attachment: EntryAsset): string {
    return attachment.derived_text_source === "audio-transcription"
      ? "Transcript"
      : "Derived text";
  }

  getAttachmentDerivedTextPreview(attachment: EntryAsset): string {
    const text = String(attachment.derived_text || "").trim();
    if (text.length <= 220) {
      return text;
    }
    return `${text.slice(0, 220).trimEnd()}…`;
  }

  isDerivingAttachmentText(attachment: EntryAsset): boolean {
    return this.derivingAttachmentTextIds.has(Number(attachment.id));
  }

  async openAttachmentDerivedText(attachment: EntryAsset): Promise<void> {
    const text = String(attachment.derived_text || "").trim();
    if (!text) {
      return;
    }

    await this.appDialog.alert({
      title: `${this.getAttachmentDerivedTextLabel(attachment)}: ${attachment.original_filename}`,
      message: text,
      confirmText: "Close",
      variant: "info",
    });
  }

  deriveAttachmentText(attachment: EntryAsset): void {
    if (!this.editingId || !attachment?.id || !attachment.is_pdf) {
      return;
    }

    this.derivingAttachmentTextIds.add(Number(attachment.id));
    const request =
      this.selectedType === "dream"
        ? this.entriesService.deriveDreamAttachmentText(this.editingId, attachment.id)
        : this.entriesService.deriveDailyAttachmentText(this.editingId, attachment.id);

    request.subscribe({
      next: (result) => {
        this.existingAttachments = this.existingAttachments.map((item) =>
          Number(item.id) === Number(attachment.id) ? result.attachment : item,
        );
        this.derivingAttachmentTextIds.delete(Number(attachment.id));
      },
      error: async (error) => {
        console.error("Failed to derive attachment text:", error);
        this.derivingAttachmentTextIds.delete(Number(attachment.id));
        await this.appDialog.alert({
          title: "Text extraction failed",
          message:
            error?.error?.error || "Failed to derive text from the PDF attachment.",
          confirmText: "Close",
          variant: "warning",
        });
      },
    });
  }

  markAttachmentForRemoval(attachment: EntryAsset): void {
    this.attachmentsMarkedForRemoval = [
      ...this.attachmentsMarkedForRemoval,
      attachment,
    ];
    this.existingAttachments = this.existingAttachments.filter(
      (item) => Number(item.id) !== Number(attachment.id),
    );
  }

  restoreMarkedAttachment(attachment: EntryAsset): void {
    this.attachmentsMarkedForRemoval = this.attachmentsMarkedForRemoval.filter(
      (item) => Number(item.id) !== Number(attachment.id),
    );
    this.existingAttachments = [...this.existingAttachments, attachment].sort(
      (left, right) => Number(left.id || 0) - Number(right.id || 0),
    );
  }

  cancelCreate(): void {
    this.goBack();
  }

  async goBack(): Promise<void> {
    if (!(await this.canLeaveCreateScreen())) {
      return;
    }

    if (this.isEditing && this.editingId !== null) {
      this.resetForm();
      this.router.navigate(["/entries", this.editingId]);
      return;
    }

    this.resetForm();
    this.router.navigate(["/entries"]);
  }

  addTag(event: MatChipInputEvent): void {
    this.addChipValue(this.tags, event);
  }

  removeTag(tag: string): void {
    this.tags = this.tags.filter((t) => t !== tag);
  }

  addPeopleName(event: MatChipInputEvent): void {
    this.addChipValue(this.peopleNames, event);
  }

  removePeopleName(person: string): void {
    this.peopleNames = this.peopleNames.filter((p) => p !== person);
  }

  addPlace(event: MatChipInputEvent): void {
    this.addChipValue(this.places, event);
  }

  handleChipInputTab(event: Event, target: string[]): void {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.shiftKey || this.isSaving) {
      return;
    }

    const input = keyboardEvent.target as HTMLInputElement | null;
    const value = input?.value?.trim() || "";
    if (!value) {
      return;
    }

    keyboardEvent.preventDefault();
    this.addChipString(target, value);
    if (input) {
      input.value = "";
    }
  }

  removePlace(place: string): void {
    this.places = this.places.filter((p) => p !== place);
  }

  async onTypeChange(event: MatButtonToggleChange): Promise<void> {
    const nextType = event.value as "daily" | "dream";
    const previousType = this.previousSelectedType;

    if (nextType === previousType) {
      return;
    }

    if (this.hasTypeSpecificContent(previousType)) {
      const confirmed = await this.appDialog.confirm({
        title: "Switch entry type?",
        message:
          "Switching entry type will clear the current type-specific content.",
        confirmText: "Switch type",
        cancelText: "Keep current type",
        variant: "warning",
      });

      if (!confirmed) {
        this.selectedType = previousType;
        return;
      }
    }

    if (previousType === "daily") {
      this.content = "";
    } else {
      this.resetDreamFields();
    }

    this.previousSelectedType = nextType;
  }

  private resetDreamFields() {
    this.dreamCast = "";
    this.dreamLocation = "";
    this.dreamPeriod = "";
    this.dreamEmotion = "";
    this.dreamPlot = "";
    this.dreamSymbolsAndImagery = "";
    this.dreamInsight = "";
    this.dreamAction = "";
    this.dreamOther = "";
  }

  canDeactivate(): boolean | Promise<boolean> {
    return this.canLeaveCreateScreen();
  }

  @HostListener("window:beforeunload", ["$event"])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.hasUnsavedChanges()) {
      event.preventDefault();
      event.returnValue = "";
    }
  }

  private addChipValue(target: string[], event: MatChipInputEvent): void {
    const value = (event.value || "").trim();
    this.addChipString(target, value);
    event.chipInput?.clear();
  }

  private addChipString(target: string[], value: string): void {
    if (value && !target.includes(value)) {
      target.push(value);
    }
  }

  private canLeaveCreateScreen(): boolean | Promise<boolean> {
    if (!this.hasUnsavedChanges()) {
      return true;
    }

    return this.appDialog.confirm({
      title: "Discard this entry?",
      message:
        "You have unsaved changes. Leaving now will discard this entry draft.",
      confirmText: "Discard changes",
      cancelText: "Stay here",
      variant: "danger",
    });
  }

  private async uploadPendingAttachments(
    entryId: number,
    entryType: "daily" | "dream",
  ): Promise<string[]> {
    if (!this.pendingAttachments.length) {
      return [];
    }

    const failedFiles: string[] = [];
    const pending = [...this.pendingAttachments];

    for (const attachment of pending) {
      try {
        const request =
          entryType === "dream"
            ? this.entriesService.uploadDreamAttachment(entryId, attachment.file)
            : this.entriesService.uploadDailyAttachment(entryId, attachment.file);
        await firstValueFrom(request);
      } catch {
        failedFiles.push(attachment.file.name);
      }
    }

    this.clearPendingAttachments();
    this.existingAttachments = [];
    return failedFiles;
  }

  private async deleteMarkedAttachments(
    entryId: number,
    entryType: "daily" | "dream",
  ): Promise<string[]> {
    if (!this.attachmentsMarkedForRemoval.length) {
      return [];
    }

    const failedFiles: string[] = [];
    const markedAttachments = [...this.attachmentsMarkedForRemoval];

    for (const attachment of markedAttachments) {
      try {
        const request =
          entryType === "dream"
            ? this.entriesService.deleteDreamAttachment(entryId, attachment.id)
            : this.entriesService.deleteDailyAttachment(entryId, attachment.id);
        await firstValueFrom(request);
      } catch {
        failedFiles.push(attachment.original_filename);
      }
    }

    this.attachmentsMarkedForRemoval = failedFiles.length
      ? markedAttachments.filter((attachment) =>
          failedFiles.includes(attachment.original_filename),
        )
      : [];
    return failedFiles;
  }

  private validateAttachmentFile(file: File): string | null {
    const extension = this.getAttachmentExtension(file.name);
    if (!ALLOWED_ATTACHMENT_EXTENSIONS.has(extension)) {
      return "Unsupported attachment type. Use PDF, JPG, PNG, WEBP, MP3, WAV, M4A, OGG, WEBM, or AIFF.";
    }

    const kind = this.getPendingAttachmentKind(file);
    const sizeLimit =
      kind === "audio"
        ? MAX_AUDIO_ATTACHMENT_BYTES
        : MAX_IMAGE_OR_PDF_ATTACHMENT_BYTES;
    if (file.size > sizeLimit) {
      return kind === "audio"
        ? "Audio attachments must be 25 MB or smaller."
        : "Image and PDF attachments must be 10 MB or smaller.";
    }

    return null;
  }

  private getPendingAttachmentKind(
    file: File,
  ): PendingAttachment["kind"] {
    const mimeType = file.type.toLowerCase();
    const extension = this.getAttachmentExtension(file.name);

    if (
      mimeType.startsWith("image/") ||
      ["jpg", "jpeg", "png", "webp"].includes(extension)
    ) {
      return "image";
    }
    if (mimeType.startsWith("audio/") || ["mp3", "wav", "m4a", "ogg", "webm", "aiff"].includes(extension)) {
      return "audio";
    }
    if (mimeType === "application/pdf" || extension === "pdf") {
      return "pdf";
    }
    return "other";
  }

  private getAttachmentExtension(filename: string): string {
    const segments = filename.toLowerCase().split(".");
    return segments.length > 1 ? segments.at(-1) ?? "" : "";
  }

  private createPendingAttachmentPreviewUrl(file: File): string | null {
    const kind = this.getPendingAttachmentKind(file);
    return kind === "image" || kind === "audio"
      ? URL.createObjectURL(file)
      : null;
  }

  private releasePendingAttachment(attachment: PendingAttachment): void {
    if (attachment.previewUrl) {
      URL.revokeObjectURL(attachment.previewUrl);
    }
  }

  private clearPendingAttachments(): void {
    this.pendingAttachments.forEach((attachment) =>
      this.releasePendingAttachment(attachment),
    );
    this.pendingAttachments = [];
  }

  private captureBackQueryParams(): void {
    const sourceParams = this.route.snapshot.queryParams;

    ["type", "month", "year", "search"].forEach((key) => {
      if (sourceParams[key] !== undefined && sourceParams[key] !== null) {
        this.backQueryParams[key] = sourceParams[key];
      }
    });
  }

  private parseApiDateAsLocal(value: unknown): Date | null {
    return parseLocalIsoDate(value);
  }

  private coerceEntryTime(value: unknown): string | null {
    if (typeof value !== "string") {
      return null;
    }

    const text = value.trim();
    if (!/^\d{2}:\d{2}$/.test(text)) {
      return null;
    }

    const [hoursText, minutesText] = text.split(":");
    const hours = Number(hoursText);
    const minutes = Number(minutesText);
    if (
      Number.isNaN(hours) ||
      Number.isNaN(minutes) ||
      hours < 0 ||
      hours > 23 ||
      minutes < 0 ||
      minutes > 59
    ) {
      return null;
    }

    return `${hoursText}:${minutesText}`;
  }

  private getCurrentLocalTime(): string {
    const now = new Date();
    const hours = `${now.getHours()}`.padStart(2, "0");
    const minutes = `${now.getMinutes()}`.padStart(2, "0");
    return `${hours}:${minutes}`;
  }

  readonly allowPastOrTodayOnly = (value: Date | null): boolean => {
    if (!value) {
      return false;
    }

    return !this.isFutureDate(value);
  };

  private serialiseDateAsLocalIso(value: Date): string {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  private isFutureDate(value: Date): boolean {
    const candidate = new Date(
      value.getFullYear(),
      value.getMonth(),
      value.getDate(),
    );
    const today = new Date();
    const todayLocal = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate(),
    );
    return candidate.getTime() > todayLocal.getTime();
  }

  private coerceEntryDate(value: Date | string | null): Date | null {
    if (value instanceof Date) {
      return Number.isNaN(value.getTime()) ? null : value;
    }

    if (typeof value === "string") {
      return this.parseApiDateAsLocal(value);
    }

    return null;
  }

  private describeEntryDate(value: Date | string | null): string {
    const parsed = this.coerceEntryDate(value);
    return parsed ? parsed.toDateString() : "";
  }

  getReadableEntryDateLabel(): string {
    return formatReadableLongDate(this.entryDate);
  }

  private handleSaveError(error: unknown, fallbackMessage: string): void {
    if (error instanceof HttpErrorResponse) {
      const apiMessage =
        typeof error.error?.error === "string" ? error.error.error : "";
      if (apiMessage) {
        this.handleError(apiMessage);
        return;
      }
    }

    this.handleError(fallbackMessage);
  }

  private hasUnsavedChanges(): boolean {
      const hasBasicChanges = Boolean(
        (this.entryTitle && this.entryTitle.trim()) ||
        (this.content && this.content.trim()) ||
        this.tags.length ||
        this.peopleNames.length ||
        this.places.length ||
        this.selectedMood ||
        this.selectedAIStyle !== "friendly" ||
        this.leaveItToAI ||
        (this.leaveItToAI &&
          this.allowAiAttachmentContext !==
            this.getAttachmentContextDefaultValue()) ||
        this.describeEntryDate(this.entryDate) !== this.initialDate ||
        this.entryTime !== this.initialTime
    );

    const hasDreamChanges =
      this.selectedType === "dream" &&
      Boolean(
        this.dreamCast.trim() ||
        this.dreamLocation.trim() ||
        this.dreamPeriod.trim() ||
        this.dreamEmotion.trim() ||
        this.dreamPlot.trim() ||
        this.dreamSymbolsAndImagery.trim() ||
        this.dreamInsight.trim() ||
        this.dreamAction.trim() ||
        this.dreamOther.trim(),
      );

    return (
      hasBasicChanges ||
      hasDreamChanges ||
      this.pendingAttachments.length > 0 ||
      this.attachmentsMarkedForRemoval.length > 0
    );
  }

  private hasTypeSpecificContent(type: "daily" | "dream"): boolean {
    if (type === "daily") {
      return Boolean(this.content.trim());
    }

    return Boolean(
      this.dreamCast.trim() ||
        this.dreamLocation.trim() ||
        this.dreamPeriod.trim() ||
        this.dreamEmotion.trim() ||
        this.dreamPlot.trim() ||
        this.dreamSymbolsAndImagery.trim() ||
        this.dreamInsight.trim() ||
        this.dreamAction.trim() ||
        this.dreamOther.trim(),
    );
  }

  private resetForm(): void {
    this.isSaving = false;
    this.errorMessage = "";
    this.clearPendingAttachments();
    this.existingAttachments = [];
    this.attachmentsMarkedForRemoval = [];
    this.entryDate = new Date();
    this.entryTime = this.getCurrentLocalTime();
    this.initialDate = this.entryDate.toDateString();
    this.initialTime = this.entryTime;
    this.entryTitle = "";
    this.content = "";
    this.tags = [];
    this.peopleNames = [];
    this.places = [];
    this.leaveItToAI = false;
    this.applyAttachmentContextDefault();
    this.selectedType = "daily";
    this.previousSelectedType = "daily";
    this.selectedMood = "";
    this.selectedAIStyle = "friendly";
    this.resetDreamFields();
  }

  hasAttachmentContextCandidates(): boolean {
    return this.getTotalAttachmentCount() > 0;
  }

  getAttachmentContextEligibleCount(): number {
    return this.getAttachmentContextEligibleAttachments().length;
  }

  getAttachmentContextBlockedCount(): number {
    return this.getAttachmentContextBlockedAttachmentCount();
  }

  getAttachmentContextCheckboxLabel(): string {
    const eligibleCount = this.getAttachmentContextEligibleCount();
    if (eligibleCount > 0) {
      return `Use ${eligibleCount} attachment${
        eligibleCount === 1 ? "" : "s"
      } in this AI analysis`;
    }
    return "Use attachment context in this AI analysis";
  }

  getAttachmentContextSummary(): string {
    const eligibleCount = this.getAttachmentContextEligibleCount();
    if (eligibleCount <= 0) {
      return "No current attachments can add useful AI context.";
    }

    return `${eligibleCount} attachment${
      eligibleCount === 1 ? "" : "s"
    } can contribute filenames, extracted PDF text, image references, or saved transcripts to this analysis.`;
  }

  getSaveProgressTitle(): string {
    return this.leaveItToAI ? "Saving entry and running AI analysis" : "Saving entry";
  }

  getSaveProgressDescription(): string {
    return this.leaveItToAI
      ? "This can take a moment while the app saves your entry, gathers context, and generates the response."
      : "This can take a moment while the app saves your entry and attachments.";
  }

  private applyAttachmentContextDefault(): void {
    this.allowAiAttachmentContext = this.getAttachmentContextDefaultValue();
  }

  private getAttachmentContextDefaultValue(): boolean {
    const currentUser = this.authService.getCurrentUser();
    return currentUser?.allow_ai_attachment_context === undefined
      ? false
      : Boolean(currentUser.allow_ai_attachment_context);
  }

  private serialiseAnalysisAttachmentRefs(refs: string[] | undefined): string {
    if (!Array.isArray(refs)) {
      return "";
    }

    return refs
      .map((ref) => String(ref || "").trim())
      .filter((ref) => ref.length > 0)
      .join("\n");
  }

  private getAttachmentContextEligibleAttachments(): Array<EntryAsset | PendingAttachment> {
    return [
      ...this.existingAttachments.filter((attachment) =>
        this.isExistingAttachmentEligibleForAiContext(attachment),
      ),
      ...this.pendingAttachments.filter((attachment) =>
        this.isPendingAttachmentEligibleForAiContext(attachment),
      ),
    ];
  }

  private getAttachmentContextBlockedAttachmentCount(): number {
    const existingBlocked = this.existingAttachments.filter(
      (attachment) => this.isExistingAttachmentBlockedForAiContext(attachment),
    ).length;
    const pendingBlocked = this.pendingAttachments.filter(
      (attachment) => this.isPendingAttachmentBlockedForAiContext(attachment),
    ).length;
    return existingBlocked + pendingBlocked;
  }

  private isExistingAttachmentEligibleForAiContext(attachment: EntryAsset): boolean {
    if (attachment.is_audio) {
      return Boolean(attachment.has_derived_text);
    }
    return true;
  }

  private isExistingAttachmentBlockedForAiContext(attachment: EntryAsset): boolean {
    return Boolean(attachment.is_audio && !attachment.has_derived_text);
  }

  private isPendingAttachmentEligibleForAiContext(attachment: PendingAttachment): boolean {
    return attachment.kind !== "audio";
  }

  private isPendingAttachmentBlockedForAiContext(attachment: PendingAttachment): boolean {
    return attachment.kind === "audio";
  }
}
