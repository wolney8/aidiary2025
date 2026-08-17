import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatNativeDateModule } from "@angular/material/core";
import { AuthService } from "../../core/services/auth.service";
import {
  BillingPlan,
  BillingService,
  CheckoutTier,
} from "../../core/services/billing.service";
import { ProfileService } from "../../core/services/profile.service";
import { AuthResponse, User } from "../../core/models/user.model";
import { PublicHolidaysService } from "../../core/services/public-holidays.service";
import { PublicHolidayCountry } from "../../core/models/public-holiday.model";

const DEFAULT_ONBOARDING_PLANS: BillingPlan[] = [
  {
    tier: "free",
    public_name: "Free",
    strapline: "Start journalling privately.",
    description: "Basic journalling tools with a small AI allowance.",
    monthly_price_gbp_pence: 0,
    annual_price_gbp_pence: 0,
    annual_discount_percent: 0,
    quotas: {
      storage_mb: 250,
      ai_analysis_monthly: 10,
      ai_chat_monthly: 10,
      ai_images_monthly: 0,
      ocr_pages_monthly: 5,
      transcription_minutes_monthly: 0,
    },
    features: [
      "Private diary, dream, and calendar entries",
      "Dashboard, search, and export tools",
      "10 AI responses per month",
      "250 MB media storage",
    ],
    gated_features: ["ai_images", "audio_transcription", "large_media_storage"],
    is_paid: false,
    is_public: true,
    sort_order: 10,
    catalogue_version: 1,
  },
  {
    tier: "personal",
    public_name: "Plus",
    strapline: "Regular AI-supported reflection.",
    description: "Higher AI and media limits for consistent personal use.",
    monthly_price_gbp_pence: 499,
    annual_price_gbp_pence: 4790,
    annual_discount_percent: 20,
    quotas: {
      storage_mb: 2048,
      ai_analysis_monthly: 250,
      ai_chat_monthly: 150,
      ai_images_monthly: 10,
      ocr_pages_monthly: 100,
      transcription_minutes_monthly: 30,
    },
    features: [
      "Everything in Free",
      "250 AI responses per month",
      "AI image generation for entries",
      "OCR and audio transcription allowance",
      "2 GB media storage",
    ],
    gated_features: [],
    is_paid: true,
    is_public: true,
    sort_order: 20,
    catalogue_version: 1,
  },
  {
    tier: "plus",
    public_name: "Premier",
    strapline: "Maximum headroom for power users.",
    description: "More AI, media, and response capacity for deeper use.",
    monthly_price_gbp_pence: 1199,
    annual_price_gbp_pence: 11510,
    annual_discount_percent: 20,
    quotas: {
      storage_mb: 10240,
      ai_analysis_monthly: 1000,
      ai_chat_monthly: 600,
      ai_images_monthly: 40,
      ocr_pages_monthly: 500,
      transcription_minutes_monthly: 180,
    },
    features: [
      "Everything in Plus",
      "1,000 AI responses per month",
      "Higher chat, image, OCR, and transcription limits",
      "Priority headroom for heavier imports",
      "10 GB media storage",
    ],
    gated_features: [],
    is_paid: true,
    is_public: true,
    sort_order: 30,
    catalogue_version: 1,
  },
];

const ONBOARDING_PLAN_COPY = {
  heading: "Choose your plan",
  subheading: "Start recording your entries now or upgrade if you want higher AI and storage limits.",
  monthlyLabel: "Monthly",
  annualLabel: "Annual",
  suggestedPill: "Most Popular",
  freeNote: "Free",
  continueFreeButton: "Continue with Free",
  checkoutOpening: "Opening...",
  choosePlanPrefix: "Choose",
  selectedPlanLabel: "Selected",
};

type BillingPeriod = "monthly" | "annual";

@Component({
  selector: "app-onboarding",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    RouterLink,
  ],
  template: `
    <main class="onboarding-shell" data-testid="oauth-onboarding-page">
      <mat-card class="onboarding-card">
        <mat-card-header *ngIf="!showPlanSelection">
          <div class="onboarding-icon" aria-hidden="true">
            <mat-icon>verified_user</mat-icon>
          </div>
          <div>
            <h1>Finish setting up your account</h1>
          </div>
        </mat-card-header>

        <mat-card-content>
          <form
            class="onboarding-form"
            (ngSubmit)="completeOnboarding()"
            *ngIf="profile && !showPlanSelection"
          >
            <section class="connected-account" aria-label="Signed in account">
              <img
                *ngIf="profile.profile_picture_url"
                class="connected-avatar"
                [src]="profile.profile_picture_url"
                alt=""
              />
              <span *ngIf="!profile.profile_picture_url" class="connected-avatar fallback" aria-hidden="true">
                <mat-icon>account_circle</mat-icon>
              </span>
              <div>
                <p class="connected-label">Signed in as</p>
                <p class="connected-name">{{ getConnectedName() }}</p>
                <p class="connected-email" *ngIf="profile.email">{{ profile.email }}</p>
              </div>
            </section>

            <div class="step-tabs" aria-label="Onboarding steps">
              <button
                type="button"
                class="step-pill"
                [class.is-active]="activeStep === 'basics'"
                (click)="activeStep = 'basics'"
              >
                <mat-icon aria-hidden="true">account_circle</mat-icon>
                <span>Account</span>
              </button>
              <button
                type="button"
                class="step-pill"
                [class.is-active]="activeStep === 'ai'"
                (click)="activeStep = 'ai'"
              >
                <mat-icon aria-hidden="true">auto_awesome</mat-icon>
                <span>AI</span>
              </button>
            </div>

            <section *ngIf="activeStep === 'basics'" class="setup-panel">
              <div class="field-grid">
                <mat-form-field appearance="outline">
                  <mat-label>Display name</mat-label>
                  <input
                    matInput
                    [(ngModel)]="profile.display_name"
                    name="display_name"
                    maxlength="24"
                    autocomplete="nickname"
                  />
                  <mat-hint align="start">Letters, numbers, hyphens, or underscores.</mat-hint>
                  <mat-hint align="end">{{ getDisplayNameLength() }}/24</mat-hint>
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Date of birth</mat-label>
                  <input
                    matInput
                    [matDatepicker]="dateOfBirthPicker"
                    [(ngModel)]="dateOfBirthValue"
                    name="date_of_birth"
                    [max]="today"
                    (dateChange)="onDateOfBirthChange()"
                  />
                  <mat-datepicker-toggle
                    matIconSuffix
                    [for]="dateOfBirthPicker"
                  ></mat-datepicker-toggle>
                  <mat-datepicker #dateOfBirthPicker></mat-datepicker>
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Country</mat-label>
                  <mat-select
                    [(ngModel)]="profile.holiday_country_code"
                    name="holiday_country_code"
                  >
                    <mat-option value="">Choose later</mat-option>
                    <mat-option
                      *ngFor="let country of holidayCountries"
                      [value]="country.countryCode"
                    >
                      {{ country.name }}
                    </mat-option>
                  </mat-select>
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Timezone</mat-label>
                  <input
                    matInput
                    [(ngModel)]="profile.timezone"
                    name="timezone"
                    maxlength="64"
                    placeholder="Europe/London"
                  />
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Pronouns</mat-label>
                  <mat-select [(ngModel)]="profile.pronouns" name="pronouns">
                    <mat-option value="">Prefer not to say</mat-option>
                    <mat-option value="he/him">he/him</mat-option>
                    <mat-option value="she/her">she/her</mat-option>
                    <mat-option value="they/them">they/them</mat-option>
                    <mat-option value="he/they">he/they</mat-option>
                    <mat-option value="she/they">she/they</mat-option>
                    <mat-option value="prefer not to say">prefer not to say</mat-option>
                  </mat-select>
                </mat-form-field>

                <mat-form-field appearance="outline">
                  <mat-label>Gender</mat-label>
                  <mat-select [(ngModel)]="profile.gender" name="gender">
                    <mat-option value="">Prefer not to say</mat-option>
                    <mat-option value="man">man</mat-option>
                    <mat-option value="woman">woman</mat-option>
                    <mat-option value="non-binary">non-binary</mat-option>
                    <mat-option value="agender">agender</mat-option>
                    <mat-option value="other / prefer not to say">other / prefer not to say</mat-option>
                  </mat-select>
                </mat-form-field>

                <mat-form-field appearance="outline" class="guidance-field">
                  <mat-label>Goals or guidance</mat-label>
                  <textarea
                    matInput
                    rows="3"
                    [(ngModel)]="profile.custom_guidance"
                    name="custom_guidance"
                    maxlength="100"
                  ></textarea>
                  <mat-hint align="start">Plain text only.</mat-hint>
                  <mat-hint align="end">{{ getGuidanceLength() }}/100</mat-hint>
                </mat-form-field>
              </div>

              <div class="preference-grid">
                <label class="preference-card">
                  <mat-checkbox [(ngModel)]="profile.allow_ai_history" name="allow_ai_history">
                    Allow past entries in analysis
                  </mat-checkbox>
                  <span>
                    Lets OpenMynd compare new entries with relevant earlier entries, such as repeated people, tags, or dates.
                  </span>
                </label>
                <label class="preference-card">
                  <mat-checkbox
                    [(ngModel)]="profile.allow_ai_attachment_context"
                    name="allow_ai_attachment_context"
                  >
                    Allow attachment context by default
                  </mat-checkbox>
                  <span>
                    Enables PDFs, transcripts, and saved derived text to be offered to analysis when an entry has attachments.
                  </span>
                </label>
              </div>
            </section>

            <section *ngIf="activeStep === 'ai'" class="setup-panel">
              <p class="confidentiality-notice">
                OpenMynd AI uses the entry, settings, history, or attachments you allow. Plan limits apply.
              </p>

              <div class="ai-settings-grid">
                <article class="ai-settings-card">
                  <header class="ai-settings-card-header">
                    <span class="ai-settings-icon" aria-hidden="true">
                      <mat-icon>book</mat-icon>
                    </span>
                    <div>
                      <h2>Daily Diary</h2>
                      <p>Reflection, prompts, emotional check-ins, and diary patterns.</p>
                    </div>
                  </header>

                  <mat-form-field appearance="outline">
                    <mat-label>Daily AI name</mat-label>
                    <input
                      matInput
                      [(ngModel)]="profile.chatgpt_daily_diary_coachname"
                      name="chatgpt_daily_diary_coachname"
                      maxlength="80"
                    />
                  </mat-form-field>
                </article>

                <article class="ai-settings-card">
                  <header class="ai-settings-card-header">
                    <span class="ai-settings-icon dream" aria-hidden="true">
                      <mat-icon>nights_stay</mat-icon>
                    </span>
                    <div>
                      <h2>Dream Diary</h2>
                      <p>Summaries, interpretation, symbols, people, places, and image prompts.</p>
                    </div>
                  </header>

                  <mat-form-field appearance="outline">
                    <mat-label>Dream AI name</mat-label>
                    <input
                      matInput
                      [(ngModel)]="profile.chatgpt_dream_diary_coachname"
                      name="chatgpt_dream_diary_coachname"
                      maxlength="80"
                    />
                  </mat-form-field>
                </article>
              </div>
            </section>

            <p class="status error" *ngIf="errorMessage" role="alert">
              {{ errorMessage }}
            </p>

            <div class="actions">
              <mat-checkbox
                class="signup-consent"
                [(ngModel)]="acceptedTerms"
                name="accepted_terms"
                required
              >
                I agree to the
                <a routerLink="/terms" target="_blank" rel="noopener">Terms</a>
                and
                <a routerLink="/privacy" target="_blank" rel="noopener">Privacy Policy</a>
              </mat-checkbox>
              <button
                mat-raised-button
                color="primary"
                type="submit"
                [disabled]="saving || !acceptedTerms"
                data-testid="oauth-onboarding-complete"
              >
                <mat-icon aria-hidden="true">check</mat-icon>
                {{ saving ? "Saving..." : "Sign up" }}
              </button>
            </div>
          </form>

          <section
            *ngIf="profile && showPlanSelection"
            class="setup-panel plan-selection-final"
            data-testid="onboarding-plan-step"
            aria-labelledby="onboarding-plan-heading"
          >
            <div class="plan-final-header">
              <div>
                <h1 id="onboarding-plan-heading">{{ planCopy.heading }}</h1>
                <p>{{ planCopy.subheading }}</p>
              </div>
            </div>

            <div
              class="billing-period-toggle"
              role="group"
              aria-label="Choose billing period"
              data-testid="onboarding-billing-period-toggle"
            >
              <button
                type="button"
                class="billing-period-option"
                [class.is-active]="selectedBillingPeriod === 'monthly'"
                [attr.aria-pressed]="selectedBillingPeriod === 'monthly'"
                (click)="setBillingPeriod('monthly')"
              >
                {{ planCopy.monthlyLabel }}
              </button>
              <button
                type="button"
                class="billing-period-option"
                [class.is-active]="selectedBillingPeriod === 'annual'"
                [attr.aria-pressed]="selectedBillingPeriod === 'annual'"
                (click)="setBillingPeriod('annual')"
              >
                {{ planCopy.annualLabel }}
                <span class="billing-period-saving" *ngIf="bestAnnualDiscountPercent > 0">
                  Save {{ bestAnnualDiscountPercent }}%
                </span>
              </button>
            </div>

            <p class="plans-inline-status" *ngIf="plansLoading" role="status">
              Loading plans...
            </p>
            <p class="plans-inline-status is-error" *ngIf="plansErrorMessage" role="alert">
              {{ plansErrorMessage }}
            </p>

            <div
              class="onboarding-plan-grid"
              *ngIf="plans.length"
              [class.is-period-monthly]="selectedBillingPeriod === 'monthly'"
              [class.is-period-annual]="selectedBillingPeriod === 'annual'"
            >
              <button
                type="button"
                class="onboarding-plan-card"
                *ngFor="let plan of plans"
                [class.is-free]="plan.tier === 'free'"
                [class.is-plus]="plan.tier === 'personal'"
                [class.is-premier]="plan.tier === 'plus'"
                [class.is-recommended]="isRecommendedPlan(plan)"
                [class.is-selected]="selectedPlanTier === plan.tier"
                [attr.aria-pressed]="selectedPlanTier === plan.tier"
                [attr.aria-label]="'Select ' + plan.public_name + ' plan'"
                (click)="selectPlan(plan)"
              >
                <div class="onboarding-plan-header">
                  <div>
                    <h2>{{ plan.public_name }}</h2>
                    <p>{{ plan.strapline }}</p>
                  </div>
                  <span class="plan-default-pill" *ngIf="isRecommendedPlan(plan)">
                    {{ planCopy.suggestedPill }}
                  </span>
                </div>

                <div class="onboarding-plan-price">
                  <strong>{{ getPlanPriceLabel(plan) }}</strong>
                  <span *ngIf="plan.monthly_price_gbp_pence > 0">
                    /{{ getPlanBillingUnit(plan) }}
                  </span>
                  <small *ngIf="getPlanSavingLabel(plan)">
                    {{ getPlanSavingLabel(plan) }}
                  </small>
                </div>

                <ul>
                  <li *ngFor="let feature of plan.features">
                    <mat-icon aria-hidden="true">check_circle</mat-icon>
                    <span>{{ feature }}</span>
                  </li>
                </ul>

                <span class="plan-free-action" *ngIf="plan.tier === 'free'">
                  <mat-icon aria-hidden="true" *ngIf="selectedPlanTier !== plan.tier">
                    open_in_new
                  </mat-icon>
                  <span>{{ getPlanActionLabel(plan) }}</span>
                </span>

                <span
                  *ngIf="isCheckoutTier(plan.tier)"
                  class="plan-upgrade-action"
                  [class.is-disabled]="!canContinueSelectedPlan(plan)"
                  role="button"
                  [attr.aria-disabled]="!canContinueSelectedPlan(plan)"
                  (click)="onPlanActionClick($event, plan)"
                >
                  <mat-icon aria-hidden="true" *ngIf="selectedPlanTier !== plan.tier || checkoutBusyTier === plan.tier">
                    {{ checkoutBusyTier === plan.tier ? "hourglass_top" : "open_in_new" }}
                  </mat-icon>
                  <span>
                    {{
                      checkoutBusyTier === plan.tier
                        ? planCopy.checkoutOpening
                        : getPlanActionLabel(plan)
                    }}
                  </span>
                </span>
              </button>
            </div>

            <p class="status error" *ngIf="errorMessage" role="alert">
              {{ errorMessage }}
            </p>

            <div class="actions">
              <button
                mat-raised-button
                color="primary"
                type="button"
                [disabled]="!canContinueSelectedPlanFromFooter()"
                (click)="continueSelectedPlanFromFooter()"
                data-testid="onboarding-continue-selected-plan"
              >
                <mat-icon aria-hidden="true" *ngIf="getSelectedPlanFooterIcon()">
                  {{ getSelectedPlanFooterIcon() }}
                </mat-icon>
                {{ getSelectedPlanFooterLabel() }}
              </button>
            </div>
          </section>
        </mat-card-content>
      </mat-card>
    </main>
  `,
  styles: [`
    .onboarding-shell {
      box-sizing: border-box;
      display: grid;
      min-height: calc(100vh - 96px);
      place-items: center;
      padding: var(--spacing-xl) var(--spacing-md);
    }

    .onboarding-card {
      width: min(100%, 1040px);
      border: 1px solid var(--colour-border);
      border-radius: 30px;
      background:
        radial-gradient(circle at 12% 10%, color-mix(in srgb, var(--colour-primary) 18%, transparent), transparent 34%),
        var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      box-shadow: 0 24px 70px var(--colour-shadow-medium);
    }

    mat-card-header {
      display: flex;
      gap: var(--spacing-md);
      padding: var(--spacing-lg) var(--spacing-lg) 0;
    }

    .onboarding-icon {
      display: grid;
      width: 56px;
      height: 56px;
      flex: 0 0 56px;
      place-items: center;
      border-radius: var(--radius-pill);
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
    }

    .onboarding-icon mat-icon {
      width: 30px;
      height: 30px;
      font-size: 30px;
    }

    .eyebrow {
      margin: 0 0 var(--spacing-xs);
      color: var(--colour-primary);
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      font-size: clamp(2rem, 5vw, 3.1rem);
      letter-spacing: -0.06em;
    }

    mat-card-content {
      padding: var(--spacing-lg);
    }

    .onboarding-form,
    .field-grid {
      display: grid;
      gap: var(--spacing-md);
    }

    .connected-account {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .connected-avatar {
      width: 64px;
      height: 64px;
      flex: 0 0 64px;
      border: 2px solid var(--colour-border);
      border-radius: var(--radius-pill);
      object-fit: cover;
      background: var(--colour-surface-elevated);
    }

    .connected-avatar.fallback {
      display: grid;
      place-items: center;
      color: var(--colour-text-secondary);
    }

    .connected-avatar mat-icon {
      width: 42px;
      height: 42px;
      font-size: 42px;
    }

    .connected-label,
    .connected-name,
    .connected-email {
      margin: 0;
    }

    .connected-label {
      color: var(--colour-text-secondary);
      font-size: 0.82rem;
      font-weight: 850;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .connected-name {
      color: var(--colour-text-primary);
      font-size: 1.12rem;
      font-weight: 900;
    }

    .connected-email {
      color: var(--colour-text-secondary);
      font-weight: 750;
      word-break: break-word;
    }

    .field-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .guidance-field {
      grid-column: 1 / -1;
    }

    .step-tabs {
      display: inline-flex;
      width: fit-content;
      padding: 4px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
    }

    .step-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-xs);
      min-height: 44px;
      padding: 0 var(--spacing-md);
      border: 0;
      border-radius: var(--radius-pill);
      background: transparent;
      color: var(--colour-text-secondary);
      cursor: pointer;
      font: inherit;
      font-weight: 900;
    }

    .step-pill mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    .step-pill.is-active {
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      box-shadow: 0 12px 26px var(--colour-shadow-soft);
    }

    .step-pill:focus-visible {
      outline: 3px solid var(--colour-focus-ring);
      outline-offset: 3px;
    }

    .setup-panel {
      display: grid;
      gap: var(--spacing-md);
    }

    .plan-selection-final {
      gap: var(--spacing-lg);
    }

    .plan-final-header {
      display: grid;
      gap: var(--spacing-xs);
    }

    .plan-final-header h1,
    .plan-final-header p {
      margin: 0;
    }

    .plan-final-header h1 {
      line-height: 1;
    }

    .plan-final-header p {
      color: var(--colour-text-secondary);
      font-weight: 750;
      line-height: 1.45;
    }

    .billing-period-toggle {
      display: inline-flex;
      justify-self: center;
      width: fit-content;
      padding: 4px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      box-shadow: 0 12px 26px var(--colour-shadow-soft);
    }

    .billing-period-option {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-xs);
      min-height: 44px;
      padding: 0 var(--spacing-md);
      border: 0;
      border-radius: var(--radius-pill);
      background: transparent;
      color: var(--colour-text-secondary);
      cursor: pointer;
      font: inherit;
      font-weight: 900;
      transition:
        background 180ms ease,
        color 180ms ease,
        box-shadow 180ms ease;
    }

    .billing-period-option.is-active {
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      box-shadow: 0 10px 22px var(--colour-shadow-soft);
    }

    .billing-period-option:focus-visible {
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    .billing-period-saving {
      padding: 0.12rem 0.42rem;
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, #fbbf24 24%, var(--colour-surface-elevated));
      color: #2f1a00;
      font-size: 0.76rem;
      font-weight: 950;
      box-shadow: inset 0 0 0 1px color-mix(in srgb, #f59e0b 34%, transparent);
    }

    :host-context(html[data-theme="dark"]) .billing-period-saving {
      background: color-mix(in srgb, #fbbf24 36%, #2a1a05);
      color: #fff7d6;
    }

    .confidentiality-notice {
      margin: 0;
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: color-mix(in srgb, var(--colour-primary) 10%, var(--colour-surface-muted));
      color: var(--colour-text-primary);
      font-weight: 750;
      line-height: 1.45;
    }

    .ai-settings-grid {
      display: grid;
      gap: var(--spacing-md);
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .ai-settings-card {
      display: grid;
      gap: var(--spacing-md);
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .ai-settings-card-header {
      display: flex;
      align-items: flex-start;
      gap: var(--spacing-sm);
    }

    .ai-settings-icon {
      display: grid;
      width: 48px;
      height: 48px;
      flex: 0 0 48px;
      place-items: center;
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, #2563eb 22%, var(--colour-surface-elevated));
      color: #8fb3ff;
    }

    .ai-settings-icon.dream {
      background: color-mix(in srgb, #7c3aed 24%, var(--colour-surface-elevated));
      color: #c4b5fd;
    }

    .ai-settings-card h2,
    .ai-settings-card p {
      margin: 0;
    }

    .ai-settings-card h2 {
      font-size: 1.1rem;
      letter-spacing: -0.02em;
    }

    .ai-settings-card p {
      color: var(--colour-text-secondary);
      font-size: 0.94rem;
      line-height: 1.45;
    }

    .preference-grid {
      display: grid;
      gap: var(--spacing-sm);
    }

    .preference-card {
      display: grid;
      gap: var(--spacing-xs);
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .preference-card span {
      color: var(--colour-text-secondary);
      font-size: 0.94rem;
      line-height: 1.45;
    }

    .onboarding-plan-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--spacing-md);
    }

    .onboarding-plan-card {
      position: relative;
      display: grid;
      grid-template-areas:
        "heading"
        "strapline"
        "price"
        "features"
        "action";
      grid-template-rows: 2.25rem 3rem 3.75rem 1fr 3rem;
      gap: var(--spacing-sm);
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background:
        radial-gradient(circle at 12% 0%, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 10%, transparent), transparent 38%),
        linear-gradient(145deg, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 5%, transparent), transparent 58%),
        var(--colour-surface-muted);
      color: var(--colour-text-primary);
      cursor: pointer;
      font: inherit;
      text-align: left;
      transition:
        border-color 180ms ease,
        box-shadow 180ms ease,
        transform 180ms ease,
        background 180ms ease;
    }

    .onboarding-plan-card.is-free {
      --plan-accent: var(--colour-success-text);
    }

    .onboarding-plan-card.is-plus {
      --plan-accent: #f59e0b;
    }

    .onboarding-plan-card.is-premier {
      --plan-accent: #a78bfa;
    }

    .onboarding-plan-card:hover {
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 48%, var(--colour-border));
    }

    .onboarding-plan-card:focus-visible {
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    .onboarding-plan-card.is-selected {
      border-color: var(--plan-accent, var(--colour-primary));
      background:
        radial-gradient(circle at 12% 0%, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 34%, transparent), transparent 38%),
        linear-gradient(145deg, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 18%, transparent), transparent 58%),
        var(--colour-surface-muted);
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 46%, transparent),
        0 0 48px color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 34%, transparent),
        0 22px 52px var(--colour-primary-shadow);
    }

    .onboarding-plan-card.is-free.is-selected {
      background:
        radial-gradient(circle at 12% 0%, color-mix(in srgb, var(--colour-success-text) 32%, transparent), transparent 38%),
        linear-gradient(145deg, color-mix(in srgb, var(--colour-success-text) 16%, transparent), transparent 58%),
        var(--colour-surface-muted);
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--colour-success-text) 42%, transparent),
        0 0 38px color-mix(in srgb, var(--colour-success-text) 28%, transparent),
        0 22px 52px var(--colour-shadow-medium);
    }

    .onboarding-plan-header {
      display: contents;
    }

    .onboarding-plan-card h2,
    .onboarding-plan-card p,
    .onboarding-plan-card ul,
    .onboarding-plan-price,
    .plans-inline-status {
      margin: 0;
    }

    .onboarding-plan-card h2 {
      grid-area: heading;
      align-self: end;
    }

    .onboarding-plan-card p {
      grid-area: strapline;
    }

    .onboarding-plan-card p,
    .plans-inline-status {
      color: var(--colour-text-secondary);
      font-weight: 750;
      line-height: 1.4;
    }

    .plans-inline-status {
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .plans-inline-status.is-error {
      border-color: color-mix(in srgb, var(--colour-warning-text) 35%, transparent);
      color: var(--colour-warning-text);
      background: var(--colour-warning-bg);
    }

    .plan-default-pill {
      position: absolute;
      top: calc(var(--spacing-md) * -0.6);
      right: var(--spacing-md);
      overflow: hidden;
      padding: 0.2rem 0.62rem;
      border-radius: var(--radius-pill);
      background: linear-gradient(135deg, #fbbf24, #f59e0b);
      color: #1f1300;
      font-size: 0.78rem;
      font-weight: 900;
      box-shadow:
        0 10px 24px color-mix(in srgb, #f59e0b 26%, transparent),
        inset 0 0 0 1px color-mix(in srgb, #fef3c7 46%, transparent);
    }

    .plan-default-pill::after {
      position: absolute;
      inset: 0;
      content: "";
      background: linear-gradient(
        110deg,
        transparent 0%,
        transparent 32%,
        color-mix(in srgb, #fff7d6 58%, transparent) 50%,
        transparent 68%,
        transparent 100%
      );
      transform: translateX(-130%);
      animation: suggested-chip-shimmer 7.6s cubic-bezier(0.2, 0, 0, 1) infinite;
    }

    @keyframes suggested-chip-shimmer {
      0% {
        transform: translateX(-130%);
      }
      34% {
        transform: translateX(130%);
      }
      100% {
        transform: translateX(130%);
      }
    }

    .onboarding-plan-grid.is-period-monthly .onboarding-plan-card {
      animation: plan-card-period-flip-monthly 520ms cubic-bezier(0.2, 0, 0, 1);
    }

    .onboarding-plan-grid.is-period-annual .onboarding-plan-card {
      animation: plan-card-period-flip-annual 520ms cubic-bezier(0.2, 0, 0, 1);
    }

    @keyframes plan-card-period-flip-monthly {
      0% {
        opacity: 0.72;
        transform: perspective(900px) rotateY(-8deg) translateY(8px) scale(0.985);
      }
      100% {
        opacity: 1;
        transform: perspective(900px) rotateY(0deg) translateY(0) scale(1);
      }
    }

    @keyframes plan-card-period-flip-annual {
      0% {
        opacity: 0.72;
        transform: perspective(900px) rotateY(8deg) translateY(8px) scale(0.985);
      }
      100% {
        opacity: 1;
        transform: perspective(900px) rotateY(0deg) translateY(0) scale(1);
      }
    }

    .onboarding-plan-price {
      grid-area: price;
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      gap: var(--spacing-xs);
      align-self: center;
      min-height: 0;
    }

    .onboarding-plan-price strong {
      font-size: 1.55rem;
      letter-spacing: -0.04em;
    }

    .onboarding-plan-price span {
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    .onboarding-plan-price small {
      flex-basis: 100%;
      color: var(--colour-success-text);
      font-weight: 850;
    }

    .onboarding-plan-card ul {
      grid-area: features;
      display: grid;
      align-content: start;
      gap: 0.38rem;
      padding: 0;
      list-style: none;
    }

    .onboarding-plan-card li,
    .plan-upgrade-action,
    .plan-free-action {
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
    }

    .onboarding-plan-card li {
      color: var(--colour-text-primary);
      font-weight: 750;
    }

    .onboarding-plan-card li mat-icon,
    .plan-upgrade-action mat-icon,
    .plan-free-action mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    .onboarding-plan-card li mat-icon {
      flex: 0 0 20px;
      color: var(--colour-success-text);
    }

    .plan-upgrade-action {
      justify-content: center;
      min-height: 44px;
      border-radius: var(--radius-pill);
      font-weight: 900;
    }

    .plan-free-action {
      grid-area: action;
      align-self: end;
      min-height: 44px;
      justify-content: center;
      padding: 0 var(--spacing-sm);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      color: var(--colour-text-secondary);
      font-weight: 900;
      text-align: center;
    }

    .onboarding-plan-card.is-selected .plan-free-action {
      border-color: color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 48%, var(--colour-border));
      background: color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 16%, transparent);
      color: var(--colour-text-primary);
    }

    .plan-selection-final .actions button.mat-mdc-raised-button {
      --mdc-protected-button-container-color: var(--colour-control-selected);
      --mdc-protected-button-label-text-color: var(--colour-control-selected-text);
      --mat-protected-button-state-layer-color: var(--colour-control-selected-text);
      border-radius: var(--radius-pill);
      box-shadow: 0 14px 30px var(--colour-primary-shadow);
    }

    .plan-selection-final .actions button.mat-mdc-raised-button:disabled {
      --mdc-protected-button-disabled-container-color: color-mix(in srgb, var(--colour-text-secondary) 16%, var(--colour-surface-muted));
      --mdc-protected-button-disabled-label-text-color: var(--colour-text-secondary);
      box-shadow: none;
      opacity: 0.72;
    }

    .plan-upgrade-action {
      grid-area: action;
    }

    .plan-upgrade-action.is-disabled {
      opacity: 0.54;
      cursor: not-allowed;
    }

    .onboarding-plan-card.is-selected .plan-upgrade-action.is-disabled {
      opacity: 1;
      background: color-mix(in srgb, var(--colour-primary) 14%, transparent);
      color: var(--colour-text-primary);
    }

    @media (prefers-reduced-motion: reduce) {
      .onboarding-plan-card {
        transition: none;
      }

      .onboarding-plan-card:hover {
        transform: none;
      }

      .plan-default-pill::after {
        animation: none;
      }

      .onboarding-plan-grid.is-period-monthly .onboarding-plan-card,
      .onboarding-plan-grid.is-period-annual .onboarding-plan-card {
        animation: none;
      }

      .billing-period-option {
        transition: none;
      }
    }

    .actions {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .signup-consent {
      color: var(--colour-text-secondary);
      font-weight: 750;
    }

    .signup-consent a {
      color: var(--colour-primary);
      font-weight: 900;
      text-decoration: underline;
      text-underline-offset: 0.18em;
    }

    .actions button {
      min-height: 48px;
      border-radius: var(--radius-pill);
      font-weight: 900;
    }

    .actions mat-icon {
      margin-right: var(--spacing-xs);
    }

    .status {
      margin: 0;
      font-weight: 800;
    }

    .error {
      color: var(--colour-danger-text);
    }

    @media (max-width: 720px) {
      .field-grid,
      .ai-settings-grid,
      .onboarding-plan-grid {
        grid-template-columns: 1fr;
      }
    }
  `],
})
export class OnboardingComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly billingService = inject(BillingService);
  private readonly profileService = inject(ProfileService);
  private readonly publicHolidaysService = inject(PublicHolidaysService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  profile: User | null = null;
  saving = false;
  errorMessage = "";
  activeStep: "basics" | "ai" = "basics";
  showPlanSelection = false;
  acceptedTerms = false;
  plans: BillingPlan[] = [];
  plansLoading = false;
  plansErrorMessage = "";
  stripeConfigured = false;
  checkoutPeriods: Partial<Record<CheckoutTier, BillingPeriod[]>> = {};
  checkoutBusyTier: CheckoutTier | null = null;
  selectedPlanTier: BillingPlan["tier"] = "free";
  selectedBillingPeriod: BillingPeriod = "monthly";
  readonly today = new Date();
  dateOfBirthValue: Date | null = null;
  holidayCountries: PublicHolidayCountry[] = [];
  readonly planCopy = ONBOARDING_PLAN_COPY;

  get bestAnnualDiscountPercent(): number {
    return this.plans.reduce(
      (best, plan) => Math.max(best, plan.annual_discount_percent || 0),
      0,
    );
  }

  ngOnInit(): void {
    this.consumeOAuthFragment();
    if (this.errorMessage) {
      return;
    }
    if (!this.authService.isAuthenticated()) {
      void this.router.navigate(["/login"], {
        queryParams: { returnUrl: "/dashboard" },
        replaceUrl: true,
      });
      return;
    }
    this.loadHolidayCountries();
    this.loadProfile();
    this.loadPlans();
  }

  private loadHolidayCountries(): void {
    this.publicHolidaysService.getAvailableCountries().subscribe({
      next: (countries) => {
        this.holidayCountries = countries;
      },
      error: () => {
        this.holidayCountries = [];
      },
    });
  }

  private loadProfile(): void {
    this.profileService.getProfile().subscribe({
      next: (profile) => {
        if (profile.onboarding_completed === true) {
          void this.navigateToReturnUrl();
          return;
        }
        this.profile = {
          ...profile,
          display_name: profile.display_name || profile.first_name || "",
          date_of_birth: profile.date_of_birth || "",
          pronouns: profile.pronouns || "",
          gender: profile.gender || "",
          custom_guidance: profile.custom_guidance || "",
          holiday_country_code: profile.holiday_country_code || "",
          timezone: profile.timezone || this.getBrowserTimezone(),
          chatgpt_daily_diary_coachname:
            profile.chatgpt_daily_diary_coachname || "",
          chatgpt_dream_diary_coachname:
            profile.chatgpt_dream_diary_coachname || "",
          allow_ai_history:
            profile.allow_ai_history === undefined ? true : Boolean(profile.allow_ai_history),
          allow_ai_attachment_context:
            profile.allow_ai_attachment_context === undefined
              ? false
              : Boolean(profile.allow_ai_attachment_context),
        };
        this.dateOfBirthValue = this.parseDateForPicker(this.profile.date_of_birth);
      },
      error: () => {
        this.errorMessage = "Unable to load account setup.";
      },
    });
  }

  completeOnboarding(): void {
    if (!this.profile || this.saving) return;
    if (!this.acceptedTerms) {
      this.errorMessage = "You must agree to the Terms and Privacy Policy to sign up.";
      return;
    }

    const validationError = this.validateProfile(this.profile);
    if (validationError) {
      this.errorMessage = validationError;
      return;
    }

    this.saving = true;
    this.errorMessage = "";
    this.profileService.updateProfile({
      display_name: String(this.profile.display_name || "").trim(),
      date_of_birth: this.formatDateForApi(this.dateOfBirthValue),
      pronouns: String(this.profile.pronouns || "").trim(),
      gender: String(this.profile.gender || "").trim(),
      custom_guidance: String(this.profile.custom_guidance || "").trim(),
      holiday_country_code: String(this.profile.holiday_country_code || "").trim(),
      timezone: String(this.profile.timezone || "").trim() || this.getBrowserTimezone(),
      chatgpt_daily_diary_coachname: String(
        this.profile.chatgpt_daily_diary_coachname || "",
      ).trim(),
      chatgpt_dream_diary_coachname: String(
        this.profile.chatgpt_dream_diary_coachname || "",
      ).trim(),
      allow_ai_history: Boolean(this.profile.allow_ai_history),
      allow_ai_attachment_context: Boolean(this.profile.allow_ai_attachment_context),
      onboarding_completed: false,
    }).subscribe({
      next: (response) => {
        this.saving = false;
        this.authService.syncCurrentUser(response.user);
        this.showPlanSelection = true;
        this.errorMessage = "";
        this.loadPlans();
        this.resetPagePosition();
        window.requestAnimationFrame(() => this.resetPagePosition());
      },
      error: (error) => {
        this.saving = false;
        this.errorMessage =
          error?.error?.error || "Account setup could not be saved. Please try again.";
      },
    });
  }

  finishWithFree(): void {
    this.completePlanSelection(() => {
      void this.navigateToReturnUrl();
    });
  }

  getSelectedPlan(): BillingPlan | undefined {
    return this.plans.find((plan) => plan.tier === this.selectedPlanTier);
  }

  getSelectedPlanFooterLabel(): string {
    const plan = this.getSelectedPlan();
    if (this.saving) return "Saving...";
    if (this.checkoutBusyTier) return this.planCopy.checkoutOpening;
    if (!plan || plan.tier === "free") return this.planCopy.continueFreeButton;
    return `Continue with ${plan.public_name}`;
  }

  getSelectedPlanFooterIcon(): string {
    if (this.saving) return "";
    if (this.checkoutBusyTier) return "hourglass_top";
    return "open_in_new";
  }

  canContinueSelectedPlanFromFooter(): boolean {
    if (this.saving || this.checkoutBusyTier !== null) return false;
    const plan = this.getSelectedPlan();
    if (!plan) return false;
    if (plan.tier === "free") return true;
    return this.isCheckoutTier(plan.tier) && this.canContinueSelectedPlan(plan);
  }

  continueSelectedPlanFromFooter(): void {
    const plan = this.getSelectedPlan();
    if (!plan || !this.canContinueSelectedPlanFromFooter()) return;
    if (plan.tier === "free") {
      this.finishWithFree();
      return;
    }
    if (this.isCheckoutTier(plan.tier)) {
      this.startCheckout(plan.tier);
    }
  }

  getDisplayNameLength(): number {
    return String(this.profile?.display_name || "").trim().length;
  }

  getGuidanceLength(): number {
    return String(this.profile?.custom_guidance || "").trim().length;
  }

  onDateOfBirthChange(): void {
    if (this.profile) {
      this.profile.date_of_birth = this.formatDateForApi(this.dateOfBirthValue);
    }
  }

  getConnectedName(): string {
    const parts = [
      String(this.profile?.first_name || "").trim(),
      String(this.profile?.last_name || "").trim(),
    ].filter(Boolean);
    return parts.join(" ") || this.profile?.display_name || this.profile?.username || "Google account";
  }

  getPlanPriceLabel(plan: BillingPlan): string {
    const price =
      this.selectedBillingPeriod === "annual" && plan.annual_price_gbp_pence
        ? plan.annual_price_gbp_pence
        : plan.monthly_price_gbp_pence;
    if (!price) return "Free";
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
      maximumFractionDigits: price % 100 === 0 ? 0 : 2,
    }).format(price / 100);
  }

  getPlanSavingLabel(plan: BillingPlan): string {
    if (
      this.selectedBillingPeriod !== "annual" ||
      !plan.annual_discount_percent ||
      !plan.annual_price_gbp_pence
    ) {
      return "";
    }
    return `Save ${plan.annual_discount_percent}% annually`;
  }

  getPlanBillingUnit(plan: BillingPlan): "month" | "year" {
    return this.selectedBillingPeriod === "annual" && plan.annual_price_gbp_pence
      ? "year"
      : "month";
  }

  getPlanActionLabel(plan: BillingPlan): string {
    return this.selectedPlanTier === plan.tier
      ? this.planCopy.selectedPlanLabel
      : `${this.planCopy.choosePlanPrefix} ${plan.public_name}`;
  }

  isCheckoutTier(tier: string): tier is CheckoutTier {
    return tier === "personal" || tier === "plus";
  }

  isRecommendedPlan(plan: BillingPlan): boolean {
    return this.selectedBillingPeriod === "annual"
      ? plan.tier === "plus"
      : plan.tier === "personal";
  }

  selectPlan(plan: BillingPlan): void {
    this.selectedPlanTier = plan.tier;
  }

  setBillingPeriod(period: BillingPeriod): void {
    this.selectedBillingPeriod = period;
  }

  canContinueSelectedPlan(plan: BillingPlan): boolean {
    return (
      this.selectedPlanTier === plan.tier &&
      this.isCheckoutTier(plan.tier) &&
      this.stripeConfigured &&
      this.isCheckoutPeriodConfigured(plan.tier) &&
      !this.saving &&
      this.checkoutBusyTier === null
    );
  }

  onPlanActionClick(event: MouseEvent, plan: BillingPlan): void {
    event.stopPropagation();
    this.selectPlan(plan);
    if (this.isCheckoutTier(plan.tier) && this.canContinueSelectedPlan(plan)) {
      this.startCheckout(plan.tier);
    }
  }

  startCheckout(tier: CheckoutTier): void {
    if (!this.stripeConfigured || this.checkoutBusyTier || this.saving) return;
    this.completePlanSelection(() => {
      this.checkoutBusyTier = tier;
      this.errorMessage = "";
      this.billingService.startCheckout(tier, this.selectedBillingPeriod).subscribe({
        next: (response) => {
          window.location.href = response.url;
        },
        error: (error) => {
          this.checkoutBusyTier = null;
          this.errorMessage = error?.error?.error || "Checkout could not be started.";
        },
      });
    });
  }

  private loadPlans(): void {
    this.plansLoading = true;
    this.plansErrorMessage = "";
    this.billingService.getPlans().subscribe({
      next: (response) => {
        this.plans = response.plans?.length ? response.plans : DEFAULT_ONBOARDING_PLANS;
        this.stripeConfigured = Boolean(response.stripe_configured);
        this.checkoutPeriods = response.checkout_periods || {};
        this.plansLoading = false;
      },
      error: () => {
        this.plans = DEFAULT_ONBOARDING_PLANS;
        this.checkoutPeriods = {};
        this.plansLoading = false;
        this.plansErrorMessage = "";
      },
    });
  }

  private isCheckoutPeriodConfigured(tier: CheckoutTier): boolean {
    const configuredPeriods = this.checkoutPeriods[tier] || [];
    return configuredPeriods.includes(this.selectedBillingPeriod);
  }

  private completePlanSelection(afterComplete: () => void): void {
    if (this.saving) return;
    this.saving = true;
    this.errorMessage = "";
    this.profileService.updateProfile({ onboarding_completed: true }).subscribe({
      next: (response) => {
        this.saving = false;
        this.authService.syncCurrentUser(response.user);
        afterComplete();
      },
      error: (error) => {
        this.saving = false;
        this.checkoutBusyTier = null;
        this.errorMessage =
          error?.error?.error || "Account setup could not be completed. Please try again.";
      },
    });
  }

  private validateProfile(profile: User): string | null {
    const displayName = String(profile.display_name || "").trim();
    if (displayName && !/^[A-Za-z0-9][A-Za-z0-9_-]{0,23}$/.test(displayName)) {
      return "Display name may only use letters, numbers, hyphens, and underscores.";
    }
    const customGuidance = String(profile.custom_guidance || "").trim();
    if (
      customGuidance &&
      (/[<>{}\[\]`;]/.test(customGuidance) ||
        /javascript:|script|onerror|onclick/i.test(customGuidance) ||
        !/^[A-Za-z0-9][A-Za-z0-9 ,.?!'"()&/\-:]{0,99}$/.test(customGuidance))
    ) {
      return "Goals or guidance must be plain text only; code or scripts are not allowed.";
    }
    const dateOfBirth = this.formatDateForApi(this.dateOfBirthValue);
    if (dateOfBirth && this.dateOfBirthValue && this.dateOfBirthValue > this.today) {
      return "Date of birth cannot be in the future.";
    }
    profile.date_of_birth = dateOfBirth;
    return null;
  }

  private getBrowserTimezone(): string {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
    } catch {
      return "UTC";
    }
  }

  private parseDateForPicker(value?: string | null): Date | null {
    if (!value) {
      return null;
    }
    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) {
      return null;
    }
    return new Date(year, month - 1, day);
  }

  private formatDateForApi(value: Date | null): string {
    if (!value) {
      return "";
    }
    const year = value.getFullYear();
    const month = `${value.getMonth() + 1}`.padStart(2, "0");
    const day = `${value.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  private consumeOAuthFragment(): void {
    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = fragment.get("token");
    const encodedUser = fragment.get("user");
    if (!token || !encodedUser) {
      return;
    }

    try {
      const user = this.decodeUser(encodedUser);
      this.authService.completeOAuthLogin({ token, user } satisfies AuthResponse);
      const returnUrl = this.getSafeReturnUrl(fragment.get("returnUrl"));
      window.history.replaceState(
        {},
        document.title,
        `/onboarding?returnUrl=${encodeURIComponent(returnUrl)}`,
      );
    } catch {
      this.errorMessage = "The external sign-in response could not be read.";
    }
  }

  private decodeUser(encodedUser: string): User {
    const padded = encodedUser.padEnd(Math.ceil(encodedUser.length / 4) * 4, "=");
    const json = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as User;
  }

  private getSafeReturnUrl(rawValue?: string | null): string {
    const value = rawValue || this.route.snapshot.queryParamMap.get("returnUrl") || "/dashboard";
    if (!value.startsWith("/") || value.startsWith("//") || value.includes("://")) {
      return "/dashboard";
    }
    return value === "/login" ||
      value === "/register" ||
      value === "/oauth/callback" ||
      value === "/onboarding"
      ? "/dashboard"
      : value;
  }

  private async navigateToReturnUrl(): Promise<void> {
    await this.router.navigateByUrl(this.getSafeReturnUrl(), { replaceUrl: true });
    this.resetPagePosition();
    window.requestAnimationFrame(() => this.resetPagePosition());
    window.setTimeout(() => this.resetPagePosition(), 75);
  }

  private resetPagePosition(): void {
    const scrollTargets = new Set<HTMLElement>();
    const scrollingElement = document.scrollingElement;

    if (scrollingElement instanceof HTMLElement) {
      scrollTargets.add(scrollingElement);
    }

    document
      .querySelectorAll<HTMLElement>(
        ".mat-drawer-content, .mat-sidenav-content, #main-content",
      )
      .forEach((element) => scrollTargets.add(element));

    scrollTargets.forEach((target) => {
      target.scrollTo({ top: 0, left: 0, behavior: "auto" });
      target.scrollTop = 0;
      target.scrollLeft = 0;
    });

    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    document.getElementById("main-content")?.focus({ preventScroll: true });
  }
}
