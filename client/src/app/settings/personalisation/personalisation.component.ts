import { CommonModule } from "@angular/common";
import { Component, HostListener, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { AppDialogService } from "../../core/services/app-dialog.service";
import {
  AI_MODEL_OPTIONS,
  DEFAULT_AI_MODEL,
} from "../../core/constants/ai-options";
import { ProfileService } from "../../core/services/profile.service";
import { PublicHolidaysService } from "../../core/services/public-holidays.service";
import { PublicHolidayCountry } from "../../core/models/public-holiday.model";
import { User } from "../../core/models/user.model";

@Component({
  selector: "app-personalisation",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  template: `
    <section class="settings-section" *ngIf="settings">
      <header class="section-header">
        <h2>Customisation</h2>
        <p>Choose how the app responds, analyses, and handles calendar data.</p>
      </header>

      <form (ngSubmit)="saveSettings()" class="settings-form">
        <mat-card class="group-card">
          <mat-card-header>
            <mat-card-title>Calendar And Holidays</mat-card-title>
            <mat-card-subtitle>
              Control whether public holidays appear in calendar view.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="field-grid">
            <div class="ai-behaviour-group checkbox-row-wide">
              <div class="checkbox-stack">
                <div class="checkbox-row">
                  <mat-checkbox
                    [(ngModel)]="settings.show_public_holidays"
                    name="show_public_holidays"
                  >
                    Show public holidays in calendar
                  </mat-checkbox>
                  <p class="checkbox-hint">
                    Uses your selected country and keeps holidays separate from diary entries.
                  </p>
                </div>
              </div>
            </div>

            <mat-form-field appearance="outline" class="holiday-country-field">
              <mat-label>Holiday country</mat-label>
              <mat-select
                [(ngModel)]="settings.holiday_country_code"
                name="holiday_country_code"
              >
                <mat-option value="">No country selected</mat-option>
                <mat-option
                  *ngFor="let country of holidayCountries"
                  [value]="country.countryCode"
                >
                  {{ country.name }}
                </mat-option>
              </mat-select>
              <mat-hint>Pick a country to show its public holidays.</mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Timezone</mat-label>
              <input
                matInput
                [(ngModel)]="settings.timezone"
                name="timezone"
                placeholder="Europe/London"
                maxlength="64"
              />
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card class="group-card">
          <mat-card-header>
            <mat-card-title>AI Behaviour</mat-card-title>
            <mat-card-subtitle>
              Control tone, depth, and how much context the AI may use.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="field-grid ai-behaviour-grid">
            <div class="ai-behaviour-note checkbox-row-wide">
              <strong>Cost and depth</strong>
              <p>
                Detailed responses and stronger models can produce more
                comprehensive analysis, but they usually increase token usage
                and cost.
              </p>
            </div>

            <mat-form-field appearance="outline">
              <mat-label>AI Tone</mat-label>
              <mat-select [(ngModel)]="settings.ai_tone" name="ai_tone">
                <mat-option value="friendly">Friendly</mat-option>
                <mat-option value="empathetic">Empathetic</mat-option>
                <mat-option value="analytical">Analytical</mat-option>
                <mat-option value="formal">Formal</mat-option>
              </mat-select>
              <mat-hint>Sets the overall voice of the response.</mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>AI Verbosity</mat-label>
              <mat-select
                [(ngModel)]="settings.ai_verbosity"
                name="ai_verbosity"
              >
                <mat-option value="concise">Concise</mat-option>
                <mat-option value="balanced">Balanced</mat-option>
                <mat-option value="detailed">Detailed</mat-option>
              </mat-select>
              <mat-hint>
                Controls response depth. Brief response styles remain shorter.
              </mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>AI Focus</mat-label>
              <mat-select [(ngModel)]="settings.ai_focus" name="ai_focus">
                <mat-option value="reflective">Reflective</mat-option>
                <mat-option value="emotional-support"
                  >Emotional support</mat-option
                >
                <mat-option value="practical-advice"
                  >Practical advice</mat-option
                >
                <mat-option value="creative-prompts">Creative prompts</mat-option>
              </mat-select>
              <mat-hint>Biases what the AI pays most attention to.</mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>AI Analysis Model</mat-label>
              <mat-select [(ngModel)]="settings.ai_model" name="ai_model">
                <mat-option
                  *ngFor="let model of aiModelOptions"
                  [value]="model.value"
                >
                  {{ model.label }}
                </mat-option>
              </mat-select>
              <mat-hint>
                Higher-tier models usually cost more per analysis.
              </mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline" class="guidance-field">
              <mat-label>Goals and custom AI guidance</mat-label>
              <textarea
                matInput
                rows="3"
                maxlength="100"
                [(ngModel)]="settings.custom_guidance"
                name="custom_guidance"
                placeholder="Short background such as what support helps most."
              ></textarea>
              <mat-hint align="start">Optional short guidance.</mat-hint>
              <mat-hint align="end">{{ getCustomGuidanceLength() }}/100</mat-hint>
            </mat-form-field>

            <div class="ai-behaviour-group checkbox-row-wide">
              <h3 class="ai-behaviour-group-title">Context permissions</h3>
              <div class="checkbox-stack">
                <div class="checkbox-row">
                  <mat-checkbox
                    [(ngModel)]="settings.allow_ai_history"
                    name="allow_ai_history"
                  >
                    Allow AI to reference past entries
                  </mat-checkbox>
                  <p class="checkbox-hint">
                    Lets analysis call back relevant earlier entries when that
                    helps.
                  </p>
                </div>

                <div class="checkbox-row">
                  <mat-checkbox
                    [(ngModel)]="settings.allow_ai_attachment_context"
                    name="allow_ai_attachment_context"
                  >
                    Allow AI to use attachment context by default
                  </mat-checkbox>
                  <p class="checkbox-hint">
                    This affects the default toggle on create and edit entry
                    forms.
                  </p>
                </div>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card class="group-card">
          <mat-card-header>
            <mat-card-title>Coach And API Access</mat-card-title>
            <mat-card-subtitle>
              Optional advanced settings for coach naming and per-mode keys.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="field-grid">
            <mat-form-field appearance="outline">
              <mat-label>Daily Diary Coach Name</mat-label>
              <input
                matInput
                [(ngModel)]="settings.chatgpt_daily_diary_coachname"
                name="chatgpt_daily_diary_coachname"
                maxlength="80"
              />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Dream Diary Coach Name</mat-label>
              <input
                matInput
                [(ngModel)]="settings.chatgpt_dream_diary_coachname"
                name="chatgpt_dream_diary_coachname"
                maxlength="80"
              />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Daily Diary API Key</mat-label>
              <input
                matInput
                [(ngModel)]="settings.dailydiary_api_key"
                name="dailydiary_api_key"
                type="password"
                autocomplete="off"
              />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Dream Diary API Key</mat-label>
              <input
                matInput
                [(ngModel)]="settings.dreamdiary_api_key"
                name="dreamdiary_api_key"
                type="password"
                autocomplete="off"
              />
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <div class="actions">
          <button
            mat-raised-button
            color="primary"
            type="submit"
            [disabled]="saving || !hasPendingChanges()"
          >
            {{ saving ? "Saving..." : "Save Customisation" }}
          </button>
        </div>

        <p class="status success" *ngIf="successMessage">{{ successMessage }}</p>
        <p class="status error" *ngIf="errorMessage">{{ errorMessage }}</p>
      </form>
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

      .settings-form {
        display: grid;
        gap: var(--spacing-md);
      }

      .group-card {
        border: 1px solid var(--colour-border);
      }

      .field-grid {
        display: grid;
        gap: var(--spacing-md);
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }

      .guidance-field {
        grid-column: 1 / -1;
      }

      .holiday-country-field {
        align-self: start;
      }

      .holiday-country-field .mat-mdc-form-field-subscript-wrapper {
        min-height: 1rem;
      }

      .holiday-country-field .mat-mdc-form-field-hint-wrapper,
      .holiday-country-field .mat-mdc-form-field-hint {
        line-height: 1.2;
      }

      .ai-behaviour-grid {
        align-items: start;
      }

      .ai-behaviour-note,
      .ai-behaviour-group {
        grid-column: 1 / -1;
        padding: 0.9rem 1rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .ai-behaviour-note strong,
      .ai-behaviour-group-title {
        display: block;
        margin: 0 0 0.35rem;
        font-size: 0.98rem;
      }

      .ai-behaviour-note p,
      .ai-behaviour-group p {
        margin: 0;
      }

      .ai-behaviour-group-title {
        font-weight: 700;
      }

      .checkbox-stack {
        display: grid;
        gap: 0.8rem;
      }

      .checkbox-row {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: center;
        gap: 0.35rem;
        min-height: 56px;
      }

      .checkbox-row-wide {
        grid-column: 1 / -1;
      }

      .checkbox-hint {
        margin: 0;
        color: var(--colour-text-secondary);
        font-size: 0.9rem;
      }

      .checkbox-row mat-checkbox {
        align-items: center;
      }

      @media (max-width: 720px) {
        .ai-behaviour-note,
        .ai-behaviour-group {
          padding: 0.8rem 0.85rem;
        }
      }

      .actions {
        display: flex;
        justify-content: flex-end;
      }

      .status {
        margin: 0;
      }

      .success {
        color: #2e7d32;
        font-weight: 600;
      }

      .error {
        color: #c62828;
      }
    `,
  ],
})
export class PersonalisationComponent implements OnInit {
  private readonly appDialog = inject(AppDialogService);
  private readonly profileService = inject(ProfileService);
  private readonly publicHolidaysService = inject(PublicHolidaysService);

  readonly aiModelOptions = AI_MODEL_OPTIONS;
  settings: User | null = null;
  holidayCountries: PublicHolidayCountry[] = [];
  saving = false;
  successMessage = "";
  errorMessage = "";
  private initialSettingsSnapshot = "";

  ngOnInit(): void {
    this.publicHolidaysService.getAvailableCountries().subscribe({
      next: (countries) => {
        this.holidayCountries = countries;
      },
      error: () => {
        this.holidayCountries = [];
      },
    });

    this.profileService.getProfile().subscribe({
      next: (profile) => {
        this.settings = {
          ...profile,
          custom_guidance: profile.custom_guidance || profile.goals || "",
          timezone: profile.timezone || "UTC",
          holiday_country_code: profile.holiday_country_code || "",
          show_public_holidays:
            profile.show_public_holidays === undefined
              ? false
              : Boolean(profile.show_public_holidays),
          ai_tone: profile.ai_tone || "friendly",
          ai_verbosity: profile.ai_verbosity || "balanced",
          ai_focus: profile.ai_focus || "reflective",
          ai_model: profile.ai_model || DEFAULT_AI_MODEL,
          allow_ai_history:
            profile.allow_ai_history === undefined
              ? true
              : Boolean(profile.allow_ai_history),
          allow_ai_attachment_context:
            profile.allow_ai_attachment_context === undefined
              ? false
              : Boolean(profile.allow_ai_attachment_context),
        };
        this.initialSettingsSnapshot = this.serialiseSettings(this.settings);
      },
      error: () => {
        this.errorMessage = "Unable to load settings.";
      },
    });
  }

  saveSettings(): void {
    if (!this.settings) {
      return;
    }

    const validationError = this.validateSettings(this.settings);
    if (validationError) {
      this.errorMessage = validationError;
      this.successMessage = "";
      return;
    }

    this.saving = true;
    this.successMessage = "";
    this.errorMessage = "";

    const {
      id,
      username,
      first_name,
      last_name,
      age,
      sex,
      goals,
      display_name,
      pronouns,
      gender,
      ...settingsPayload
    } = this.settings;

    this.profileService.updateProfile(settingsPayload).subscribe({
      next: (response) => {
        this.successMessage = response.message || "Customisation saved.";
        this.saving = false;
        if (this.settings) {
          this.initialSettingsSnapshot = this.serialiseSettings(this.settings);
        }
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Settings update failed. Please try again.";
        this.saving = false;
      },
    });
  }

  private validateSettings(settings: User): string | null {
    const displayName = String(settings.display_name || "").trim();
    if (displayName && displayName.length > 8) {
      return "Display name must be 8 characters or fewer.";
    }
    if (displayName && !/^[A-Za-z][A-Za-z '\-]{0,7}$/.test(displayName)) {
      return "Display name may only use letters, spaces, apostrophes, and hyphens.";
    }

    const customGuidance = String(settings.custom_guidance || "").trim();
    if (
      customGuidance &&
      !/^[A-Za-z0-9 ,.?!'"()&/\-:]{1,100}$/.test(customGuidance)
    ) {
      return "Goals and custom AI guidance must use plain text and basic punctuation only.";
    }

    return null;
  }

  hasPendingChanges(): boolean {
    if (!this.settings) {
      return false;
    }
    return this.serialiseSettings(this.settings) !== this.initialSettingsSnapshot;
  }

  canDeactivate(): boolean | Promise<boolean> {
    if (!this.hasPendingChanges() || this.saving) {
      return true;
    }

    return this.appDialog.confirm({
      title: "Discard Customisation changes?",
      message:
        "You have unsaved Customisation changes. Leaving now will discard them.",
      confirmText: "Discard changes",
      cancelText: "Stay here",
      variant: "danger",
    });
  }

  @HostListener("window:beforeunload", ["$event"])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (!this.hasPendingChanges() || this.saving) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  }

  private serialiseSettings(settings: User): string {
    return JSON.stringify({
      custom_guidance: String(settings.custom_guidance || "").trim(),
      timezone: String(settings.timezone || "").trim(),
      holiday_country_code: String(settings.holiday_country_code || "").trim(),
      show_public_holidays: Boolean(settings.show_public_holidays),
      ai_tone: String(settings.ai_tone || "").trim(),
      ai_verbosity: String(settings.ai_verbosity || "").trim(),
      ai_focus: String(settings.ai_focus || "").trim(),
      ai_model: String(settings.ai_model || "").trim(),
      allow_ai_history: Boolean(settings.allow_ai_history),
      allow_ai_attachment_context: Boolean(settings.allow_ai_attachment_context),
      chatgpt_daily_diary_coachname: String(
        settings.chatgpt_daily_diary_coachname || "",
      ).trim(),
      chatgpt_dream_diary_coachname: String(
        settings.chatgpt_dream_diary_coachname || "",
      ).trim(),
      dailydiary_api_key: String(settings.dailydiary_api_key || "").trim(),
      dreamdiary_api_key: String(settings.dreamdiary_api_key || "").trim(),
    });
  }

  getCustomGuidanceLength(): number {
    return String(this.settings?.custom_guidance || "").trim().length;
  }
}
