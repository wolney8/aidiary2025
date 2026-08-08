import { CommonModule } from "@angular/common";
import { Component, OnInit, computed, inject } from "@angular/core";
import { ActivatedRoute, RouterModule } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { AuthService } from "../core/services/auth.service";
import { ThemeService } from "../core/services/theme.service";

@Component({
  selector: "app-verify-email",
  standalone: true,
  imports: [CommonModule, RouterModule, MatButtonModule, MatCardModule, MatIconModule],
  template: `
    <main class="auth-container" data-testid="verify-email-page">
      <mat-card class="auth-card">
        <mat-card-header class="auth-card-header">
          <div class="brand-lockup">
            <span class="brand-logo-frame">
              <img class="brand-logo" [src]="brandLogoSrc()" alt="OpenMynd" />
            </span>
            <p class="brand-eyebrow">Email verification</p>
          </div>
          <h1 class="sr-only">Verify OpenMynd email</h1>
        </mat-card-header>

        <mat-card-content>
          <div class="status" [class.status--success]="verified" [class.status--error]="errorMessage" role="status">
            <mat-icon aria-hidden="true">{{ loading ? "hourglass_top" : verified ? "mark_email_read" : "error" }}</mat-icon>
            <span>{{ statusText }}</span>
          </div>

          <a mat-raised-button color="primary" routerLink="/login" class="full-width" data-testid="verify-email-login">
            <mat-icon aria-hidden="true">login</mat-icon>
            <span>Sign in</span>
          </a>
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

    .status {
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
      padding: 12px;
      margin-bottom: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-md);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      font-weight: 750;
    }

    .status mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    .status--success {
      border-color: var(--colour-success-text);
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
    }

    .status--error {
      border-color: var(--colour-danger-text);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    .full-width {
      display: inline-flex;
      width: 100%;
      min-height: 48px;
      border-radius: var(--radius-pill);
      font-weight: 800;
      letter-spacing: 0.04em;
    }

    .full-width mat-icon {
      margin-right: var(--spacing-xs);
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
export class VerifyEmailComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly themeService = inject(ThemeService);
  readonly brandLogoSrc = computed(() =>
    this.themeService.isDark()
      ? "assets/brand/openmynd-logo-dark.jpg"
      : "assets/brand/openmynd-logo-light.jpg",
  );

  loading = true;
  verified = false;
  errorMessage = "";
  statusText = "Checking your verification link...";

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get("token") || "";
    if (!token) {
      this.loading = false;
      this.errorMessage = "Verification link is missing or invalid.";
      this.statusText = this.errorMessage;
      return;
    }

    this.authService.confirmEmailVerification(token).subscribe({
      next: (response) => {
        this.loading = false;
        this.verified = true;
        this.statusText = response.message;
      },
      error: (error) => {
        this.loading = false;
        this.errorMessage =
          error?.error?.error || "Email verification failed. Request a new link from Account.";
        this.statusText = this.errorMessage;
      },
    });
  }
}
