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
import { AuthService } from "../../core/services/auth.service";
import { ProfileService } from "../../core/services/profile.service";
import { AuthResponse, User } from "../../core/models/user.model";

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
    RouterLink,
  ],
  template: `
    <main class="onboarding-shell" data-testid="oauth-onboarding-page">
      <mat-card class="onboarding-card">
        <mat-card-header>
          <div class="onboarding-icon" aria-hidden="true">
            <mat-icon>verified_user</mat-icon>
          </div>
          <div>
            <h1>Finish setting up your account</h1>
          </div>
        </mat-card-header>

        <mat-card-content>
          <form class="onboarding-form" (ngSubmit)="completeOnboarding()" *ngIf="profile">
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
                AI uses only the entry, settings, history, or attachments you allow.
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
                    <mat-label>Daily diary API key</mat-label>
                    <input
                      matInput
                      [(ngModel)]="profile.dailydiary_api_key"
                      name="dailydiary_api_key"
                      autocomplete="off"
                    />
                  </mat-form-field>

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
                    <mat-label>Dream diary API key</mat-label>
                    <input
                      matInput
                      [(ngModel)]="profile.dreamdiary_api_key"
                      name="dreamdiary_api_key"
                      autocomplete="off"
                    />
                  </mat-form-field>

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
      width: min(100%, 760px);
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
      .ai-settings-grid {
        grid-template-columns: 1fr;
      }
    }
  `],
})
export class OnboardingComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly profileService = inject(ProfileService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  profile: User | null = null;
  saving = false;
  errorMessage = "";
  activeStep: "basics" | "ai" = "basics";
  acceptedTerms = false;

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
    this.loadProfile();
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
          pronouns: profile.pronouns || "",
          gender: profile.gender || "",
          custom_guidance: profile.custom_guidance || "",
          dailydiary_api_key: profile.dailydiary_api_key || "",
          dreamdiary_api_key: profile.dreamdiary_api_key || "",
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
      pronouns: String(this.profile.pronouns || "").trim(),
      gender: String(this.profile.gender || "").trim(),
      custom_guidance: String(this.profile.custom_guidance || "").trim(),
      dailydiary_api_key: String(this.profile.dailydiary_api_key || "").trim(),
      dreamdiary_api_key: String(this.profile.dreamdiary_api_key || "").trim(),
      chatgpt_daily_diary_coachname: String(
        this.profile.chatgpt_daily_diary_coachname || "",
      ).trim(),
      chatgpt_dream_diary_coachname: String(
        this.profile.chatgpt_dream_diary_coachname || "",
      ).trim(),
      allow_ai_history: Boolean(this.profile.allow_ai_history),
      allow_ai_attachment_context: Boolean(this.profile.allow_ai_attachment_context),
      onboarding_completed: true,
    }).subscribe({
      next: (response) => {
        this.saving = false;
        this.authService.syncCurrentUser(response.user);
        void this.navigateToReturnUrl();
      },
      error: (error) => {
        this.saving = false;
        this.errorMessage =
          error?.error?.error || "Account setup could not be saved. Please try again.";
      },
    });
  }

  getDisplayNameLength(): number {
    return String(this.profile?.display_name || "").trim().length;
  }

  getGuidanceLength(): number {
    return String(this.profile?.custom_guidance || "").trim().length;
  }

  getConnectedName(): string {
    const parts = [
      String(this.profile?.first_name || "").trim(),
      String(this.profile?.last_name || "").trim(),
    ].filter(Boolean);
    return parts.join(" ") || this.profile?.display_name || this.profile?.username || "Google account";
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
    return null;
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
