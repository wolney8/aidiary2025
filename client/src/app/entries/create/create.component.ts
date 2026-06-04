// Create entry with support for daily and dream flows
import { Component, HostListener, inject, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { HttpErrorResponse } from "@angular/common/http";
import { Router, ActivatedRoute } from "@angular/router";
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
import { COMMA, ENTER } from "@angular/cdk/keycodes";
import { MatButtonToggleChange } from "@angular/material/button-toggle";
import { EntriesService } from "../../core/services/entries.service";
import { AnalysisService } from "../../core/services/analysis.service";
import {
  DailyAnalysisResponse,
  DreamAnalysisResponse,
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

@Component({
  selector: "app-create",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
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

          <mat-slide-toggle [(ngModel)]="leaveItToAI">
            Respond with AI
          </mat-slide-toggle>
        </mat-card-header>

        <mat-card-content>
          <mat-button-toggle-group
            class="entry-type-toggle"
            [(ngModel)]="selectedType"
            name="entryType"
            [disabled]="isEditing"
            aria-label="Entry type toggle"
            (change)="onTypeChange($event)"
          >
            <mat-button-toggle value="daily">Daily Entry</mat-button-toggle>
            <mat-button-toggle value="dream">Dream Entry</mat-button-toggle>
          </mat-button-toggle-group>
          <p class="hint" *ngIf="leaveItToAI">
            We'll run an AI analysis straight after saving this entry.
          </p>

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
          </mat-form-field>

          <!-- AI Style Selection - only show when AI toggle is on -->
          <mat-form-field
            appearance="outline"
            class="full-width"
            *ngIf="leaveItToAI"
          >
            <mat-label>AI Response Style</mat-label>
            <mat-select [(ngModel)]="selectedAIStyle" name="aiStyle">
              <mat-option
                *ngFor="let style of aiStyleOptions"
                [value]="style.value"
              >
                <div>
                  <strong>{{ style.label }}</strong>
                  <br />
                  <small>{{ style.description }}</small>
                </div>
              </mat-option>
            </mat-select>
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
              />
            </mat-chip-grid>
          </mat-form-field>

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
                Save Entry
              </button>
            </ng-container>

            <ng-template #aiActions>
              <button
                mat-raised-button
                color="primary"
                (click)="saveAndAnalyse()"
                [disabled]="isSaving"
              >
                Save & Analyse
              </button>
            </ng-template>
          </div>

          <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
        </mat-card-content>
      </mat-card>
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

      .actions {
        display: flex;
        gap: var(--spacing-sm);
        justify-content: flex-end;
        margin-top: var(--spacing-sm);
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
      }
    `,
  ],
})
export class CreateComponent implements OnInit {
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private entriesService = inject(EntriesService);
  private analysisService = inject(AnalysisService);

  backQueryParams: Record<string, string | number> = {};

  entryDate: Date | string | null = new Date();
  entryTitle = "";
  content = "";
  tags: string[] = [];
  peopleNames: string[] = [];
  places: string[] = [];
  leaveItToAI = false;
  selectedType: "daily" | "dream" = "daily";
  private previousSelectedType: "daily" | "dream" = "daily";
  isSaving = false;
  errorMessage = "";
  maxDate = new Date();
  isEditing = false;
  editingId: number | null = null;

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
    this.entryDate = this.parseApiDateAsLocal(entry.entry_date) ?? new Date();
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
    const tags = this.tags.join(",");
    const trimmedTitle = this.entryTitle.trim();
    const body = this.content.trim();

    if (this.selectedType === "daily") {
      const createPayload = {
        entry_date: entryDate,
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
            next: () => {
              if (shouldAnalyse) {
                this.runDailyAnalysis(this.editingId!);
              } else {
                this.finishNavigation(this.editingId!);
              }
            },
            error: (error) =>
              this.handleSaveError(
                error,
                "Failed to update your daily entry.",
              ),
          });
      } else {
        this.entriesService.createDailyEntry(createPayload).subscribe({
          next: (created) => {
            if (shouldAnalyse) {
              this.runDailyAnalysis(created.id!);
            } else {
              this.finishNavigation(created.id!);
            }
          },
          error: (error) =>
            this.handleSaveError(error, "Failed to save your daily entry."),
        });
      }
    } else {
      const dreamPlotContent = this.dreamPlot.trim() || "Dream entry";

      const createPayload = {
        entry_date: entryDate,
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
            next: () => {
              if (shouldAnalyse) {
                this.runDreamAnalysis(this.editingId!);
              } else {
                this.finishNavigation(this.editingId!);
              }
            },
            error: (error) =>
              this.handleSaveError(
                error,
                "Failed to update your dream entry.",
              ),
          });
      } else {
        this.entriesService.createDreamEntry(createPayload).subscribe({
          next: (created) => {
            if (shouldAnalyse) {
              this.runDreamAnalysis(created.id!);
            } else {
              this.finishNavigation(created.id!);
            }
          },
          error: (error) =>
            this.handleSaveError(error, "Failed to save your dream entry."),
        });
      }
    }
  }

  private runDailyAnalysis(entryId: number): void {
    const analysisDate = this.coerceEntryDate(this.entryDate);
    const referenceDate = analysisDate
      ? this.serialiseDateAsLocalIso(analysisDate)
      : undefined;

    this.analysisService
      .analyseText({
        mode: "daily",
        text: this.content,
        reference_date: referenceDate,
      })
      .subscribe({
        next: (analysis) => {
          const dailyAnalysis = analysis as DailyAnalysisResponse;
          this.entriesService
            .updateDailyEntry(entryId, {
              ai_response: dailyAnalysis.ai_response,
              tags: this.tags.length ? this.tags.join(",") : dailyAnalysis.tags,
              daily_people_names: this.peopleNames.length
                ? this.peopleNames.join(",")
                : dailyAnalysis.daily_people_names,
              daily_places: this.places.length
                ? this.places.join(",")
                : dailyAnalysis.daily_places,
            })
            .subscribe({
              next: () => this.finishNavigation(entryId),
              error: () => this.finishNavigation(entryId, "ai-save-failed"),
            });
        },
        error: (error) => {
          if (this.isRateLimitAnalysisError(error)) {
            this.finishNavigation(entryId, "ai-rate-limit");
            return;
          }

          this.finishNavigation(entryId);
        },
      });
  }

  private runDreamAnalysis(entryId: number): void {
    // For dream analysis, use the plot field or combine dream fields
    const analysisText =
      this.dreamPlot.trim() ||
      `Cast: ${this.dreamCast} Location: ${this.dreamLocation} Plot: ${this.dreamPlot} Emotion: ${this.dreamEmotion}`;
    const analysisDate = this.coerceEntryDate(this.entryDate);
    const referenceDate = analysisDate
      ? this.serialiseDateAsLocalIso(analysisDate)
      : undefined;

    this.analysisService
      .analyseText({
        mode: "dream",
        text: analysisText,
        reference_date: referenceDate,
      })
      .subscribe({
        next: (analysis) => {
          const dreamAnalysis = analysis as DreamAnalysisResponse;
          this.entriesService
            .updateDreamEntry(entryId, {
              summary: dreamAnalysis.summary,
              interpretation: dreamAnalysis.interpretation,
              image_prompt: dreamAnalysis.image_prompt,
              tags: this.tags.length ? this.tags.join(",") : dreamAnalysis.tags,
              dream_people_names: this.peopleNames.length
                ? this.peopleNames.join(",")
                : dreamAnalysis.dream_people_names,
              dream_places: this.places.length
                ? this.places.join(",")
                : dreamAnalysis.dream_places,
            })
            .subscribe({
              next: () => this.finishNavigation(entryId),
              error: () => this.finishNavigation(entryId, "ai-save-failed"),
            });
        },
        error: (error) => {
          if (this.isRateLimitAnalysisError(error)) {
            this.finishNavigation(entryId, "ai-rate-limit");
            return;
          }

          this.finishNavigation(entryId);
        },
      });
  }

  private finishNavigation(entryId: number, analysisWarning?: string): void {
    this.isSaving = false;
    this.resetForm();

    const queryParams = analysisWarning ? { analysisWarning } : undefined;

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

  cancelCreate(): void {
    this.goBack();
  }

  goBack(): void {
    if (!this.canLeaveCreateScreen()) {
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

  removePlace(place: string): void {
    this.places = this.places.filter((p) => p !== place);
  }

  onTypeChange(event: MatButtonToggleChange) {
    const nextType = event.value as "daily" | "dream";
    const previousType = this.previousSelectedType;

    if (nextType === previousType) {
      return;
    }

    if (this.hasTypeSpecificContent(previousType)) {
      const confirmed = confirm(
        "Switching entry type will clear the current type-specific content. Continue?",
      );

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

  canDeactivate(): boolean {
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
    if (value && !target.includes(value)) {
      target.push(value);
    }
    event.chipInput?.clear();
  }

  private canLeaveCreateScreen(): boolean {
    return !this.hasUnsavedChanges() || confirm("Discard this entry?");
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
    if (typeof value !== "string" || !value.trim()) {
      return null;
    }

    const trimmed = value.trim();
    const isoDateOnlyMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
    if (isoDateOnlyMatch) {
      const year = Number(isoDateOnlyMatch[1]);
      const monthIndex = Number(isoDateOnlyMatch[2]) - 1;
      const day = Number(isoDateOnlyMatch[3]);
      const localDate = new Date(year, monthIndex, day);

      if (
        localDate.getFullYear() === year &&
        localDate.getMonth() === monthIndex &&
        localDate.getDate() === day
      ) {
        return localDate;
      }

      return null;
    }

    const parsed = new Date(trimmed);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
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
      this.describeEntryDate(this.entryDate) !== this.initialDate,
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

    return hasBasicChanges || hasDreamChanges;
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
    this.entryDate = new Date();
    this.initialDate = this.entryDate.toDateString();
    this.entryTitle = "";
    this.content = "";
    this.tags = [];
    this.peopleNames = [];
    this.places = [];
    this.leaveItToAI = false;
    this.selectedType = "daily";
    this.previousSelectedType = "daily";
    this.selectedMood = "";
    this.selectedAIStyle = "friendly";
    this.resetDreamFields();
  }
}
