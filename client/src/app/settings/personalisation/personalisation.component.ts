import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterModule } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { ProfileService } from "../../core/services/profile.service";
import { User } from "../../core/models/user.model";

@Component({
  selector: "app-personalisation",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
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
        <h2>Personalisation</h2>
        <p>Choose how the app and AI companion address and support you.</p>
        <p class="supporting-copy">
          Changes here update the current compatibility profile endpoint. This
          is the active home for app-level preferences and AI behaviour.
        </p>
      </header>

      <form (ngSubmit)="saveSettings()" class="settings-form">
        <mat-card class="group-card">
          <mat-card-header>
            <mat-card-title>Identity</mat-card-title>
            <mat-card-subtitle>
              How the app and AI should refer to you.
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="field-grid">
            <mat-form-field appearance="outline">
              <mat-label>Display Name</mat-label>
              <input
                matInput
                [(ngModel)]="settings.display_name"
                name="display_name"
                maxlength="80"
              />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Pronouns</mat-label>
              <input
                matInput
                [(ngModel)]="settings.pronouns"
                name="pronouns"
                maxlength="40"
              />
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
          <mat-card-content class="field-grid">
            <mat-form-field appearance="outline">
              <mat-label>AI Tone</mat-label>
              <mat-select [(ngModel)]="settings.ai_tone" name="ai_tone">
                <mat-option value="friendly">Friendly</mat-option>
                <mat-option value="empathetic">Empathetic</mat-option>
                <mat-option value="analytical">Analytical</mat-option>
                <mat-option value="formal">Formal</mat-option>
              </mat-select>
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
            </mat-form-field>

            <div class="checkbox-row">
              <mat-checkbox
                [(ngModel)]="settings.allow_ai_history"
                name="allow_ai_history"
              >
                Allow AI to reference past entries
              </mat-checkbox>
            </div>

            <div class="checkbox-row checkbox-row-wide">
              <mat-checkbox
                [(ngModel)]="settings.allow_ai_attachment_context"
                name="allow_ai_attachment_context"
              >
                Allow AI to use attachment context by default
              </mat-checkbox>
              <p class="checkbox-hint">
                This affects the default toggle on create and edit entry forms.
              </p>
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
            [disabled]="saving"
          >
            Save Personalisation
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

      .supporting-copy {
        margin-top: var(--spacing-xs);
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

      .actions {
        display: flex;
        justify-content: flex-end;
      }

      .status {
        margin: 0;
      }

      .success {
        color: #2e7d32;
      }

      .error {
        color: #c62828;
      }
    `,
  ],
})
export class PersonalisationComponent implements OnInit {
  private readonly profileService = inject(ProfileService);

  settings: User | null = null;
  saving = false;
  successMessage = "";
  errorMessage = "";

  ngOnInit(): void {
    this.profileService.getProfile().subscribe({
      next: (profile) => {
        this.settings = {
          ...profile,
          timezone: profile.timezone || "UTC",
          ai_tone: profile.ai_tone || "friendly",
          ai_verbosity: profile.ai_verbosity || "balanced",
          ai_focus: profile.ai_focus || "reflective",
          allow_ai_history:
            profile.allow_ai_history === undefined
              ? true
              : Boolean(profile.allow_ai_history),
          allow_ai_attachment_context:
            profile.allow_ai_attachment_context === undefined
              ? true
              : Boolean(profile.allow_ai_attachment_context),
        };
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
      ...settingsPayload
    } = this.settings;

    this.profileService.updateProfile(settingsPayload).subscribe({
      next: (response) => {
        this.successMessage = response.message;
        this.saving = false;
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Settings update failed. Please try again.";
        this.saving = false;
      },
    });
  }
}
