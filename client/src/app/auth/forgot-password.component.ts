import { CommonModule } from "@angular/common";
import { Component, computed, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterModule } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { AuthService } from "../core/services/auth.service";
import { ThemeService } from "../core/services/theme.service";

@Component({
  selector: "app-forgot-password",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
  ],
  template: `
    <main class="auth-container" data-testid="forgot-password-page">
      <mat-card class="auth-card">
        <mat-card-header class="auth-card-header">
          <div class="brand-lockup">
            <span class="brand-logo-frame">
              <img class="brand-logo" [src]="brandLogoSrc()" alt="OpenMynd" />
            </span>
            <p class="brand-eyebrow">Password recovery</p>
          </div>
          <h1 class="sr-only">Reset your OpenMynd password</h1>
        </mat-card-header>

        <mat-card-content>
          <div *ngIf="successMessage" class="status status--success" role="status" data-testid="forgot-password-success">
            <mat-icon aria-hidden="true">check_circle</mat-icon>
            <span>{{ successMessage }}</span>
          </div>
          <div *ngIf="errorMessage" class="status status--error" role="alert" data-testid="forgot-password-error">
            <mat-icon aria-hidden="true">error</mat-icon>
            <span>{{ errorMessage }}</span>
          </div>

          <form class="auth-form" (ngSubmit)="requestReset()" [attr.aria-busy]="submitting">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Email</mat-label>
              <input
                matInput
                type="email"
                [(ngModel)]="email"
                name="email"
                autocomplete="email"
                required
                data-testid="forgot-password-email"
              />
            </mat-form-field>

            <button
              mat-raised-button
              color="primary"
              type="submit"
              class="full-width"
              [disabled]="submitting"
              data-testid="forgot-password-submit"
            >
              <mat-icon aria-hidden="true">{{ submitting ? "hourglass_top" : "mail" }}</mat-icon>
              <span>{{ submitting ? "Sending..." : "Send reset link" }}</span>
            </button>
          </form>

          <p class="auth-link">
            Remembered it? <a routerLink="/login">Sign in</a>
          </p>
        </mat-card-content>
      </mat-card>
    </main>
  `,
  styles: [`
    .auth-container {
      box-sizing: border-box;
      position: relative;
      isolation: isolate;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: var(--spacing-md);
      overflow: hidden;
      background: var(--gradient-auth-ambient);
      background-size: 360% 360%;
      animation: authGradientDrift var(--motion-ambient-gradient);
    }

    .auth-container::before {
      content: "";
      position: absolute;
      inset: 0;
      z-index: -3;
      background:
        radial-gradient(circle at 50% 46%, rgba(255, 255, 255, 0.18), transparent 34%),
        linear-gradient(180deg, rgba(15, 23, 42, 0.1), rgba(15, 23, 42, 0.32));
      opacity: 0.86;
      pointer-events: none;
    }

    .auth-card {
      max-width: 440px;
      width: 100%;
      padding: clamp(8px, 1vw, 14px);
      border: 1px solid var(--colour-border);
      border-radius: 32px;
      background: color-mix(in srgb, var(--colour-surface-elevated) 88%, transparent);
      color: var(--colour-text-primary);
      box-shadow: 0 24px 70px var(--colour-shadow-medium);
      backdrop-filter: blur(24px);
    }

    .auth-card-header,
    .brand-lockup,
    .brand-logo-frame {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .auth-card-header {
      padding: var(--spacing-md) var(--spacing-sm) var(--spacing-sm);
      text-align: center;
    }

    .brand-lockup {
      flex-direction: column;
      gap: 12px;
    }

    .brand-logo-frame {
      width: 104px;
      height: 104px;
      overflow: hidden;
      border: 1px solid color-mix(in srgb, var(--colour-border) 70%, transparent);
      border-radius: 32px;
      background: var(--colour-surface);
    }

    .brand-logo {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .brand-eyebrow {
      margin: 0;
      color: var(--colour-text-secondary);
      font-size: 0.9rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .auth-form {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .full-width {
      width: 100%;
      margin-bottom: var(--spacing-sm);
    }

    button.full-width {
      min-height: 48px;
      border-radius: var(--radius-pill);
      font-weight: 800;
      letter-spacing: 0.04em;
    }

    button.full-width mat-icon {
      margin-right: var(--spacing-xs);
    }

    .status {
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
      padding: 12px;
      margin-bottom: var(--spacing-sm);
      border-radius: var(--radius-md);
      font-size: 14px;
      font-weight: 750;
    }

    .status mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    .status--success {
      border: 1px solid var(--colour-success-text);
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
    }

    .status--error {
      border: 1px solid var(--colour-danger-text);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    .auth-link {
      margin-top: var(--spacing-md);
      text-align: center;
    }

    .auth-link a {
      color: var(--colour-primary);
      font-weight: 800;
    }

    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    @keyframes authGradientDrift {
      from { background-position: 0% 50%; }
      to { background-position: 100% 50%; }
    }

    @media (prefers-reduced-motion: reduce) {
      .auth-container { animation: none; }
    }
  `],
})
export class ForgotPasswordComponent {
  private readonly authService = inject(AuthService);
  private readonly themeService = inject(ThemeService);
  readonly brandLogoSrc = computed(() =>
    this.themeService.isDark()
      ? "assets/brand/openmynd-logo-dark.jpg"
      : "assets/brand/openmynd-logo-light.jpg",
  );

  email = "";
  submitting = false;
  successMessage = "";
  errorMessage = "";

  requestReset(): void {
    this.errorMessage = "";
    this.successMessage = "";
    const email = this.email.trim();
    if (!email) {
      this.errorMessage = "Enter your account email.";
      return;
    }

    this.submitting = true;
    this.authService.requestPasswordReset(email).subscribe({
      next: (response) => {
        this.successMessage = response.message;
        this.submitting = false;
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Password reset request failed. Please try again.";
        this.submitting = false;
      },
    });
  }
}
