// Registration component
import { Component, OnInit, computed, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';
import { OAuthProvider } from '../../core/models/user.model';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule
  ],
  template: `
    <div class="auth-container" data-testid="register-page">
      <mat-card class="auth-card" data-testid="register-card">
        <mat-card-header class="auth-card-header">
          <div class="brand-lockup">
            <span class="brand-logo-frame">
              <img
                class="brand-logo"
                [src]="brandLogoSrc()"
                alt="OpenMynd"
                data-testid="register-brand-logo"
              />
            </span>
            <p class="brand-eyebrow">Create your private workspace</p>
          </div>
          <h1 class="sr-only">Create OpenMynd account</h1>
        </mat-card-header>
        
        <mat-card-content>
          <form class="auth-form" (ngSubmit)="onSubmit()" [attr.aria-busy]="submitting">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Username</mat-label>
              <input
                matInput
                [(ngModel)]="formData.username"
                name="username"
                maxlength="32"
                autocomplete="username"
                required
              >
              <mat-hint>Use 3-32 letters, numbers, dots, underscores, or hyphens.</mat-hint>
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="formData.password"
                name="password"
                maxlength="128"
                autocomplete="new-password"
                required
              >
              <mat-hint>Use 8-128 characters with letters and numbers.</mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Confirm Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="confirmPassword"
                name="confirmPassword"
                autocomplete="new-password"
                required
              >
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>First Name</mat-label>
              <input
                matInput
                [(ngModel)]="formData.first_name"
                name="first_name"
                maxlength="12"
                autocomplete="given-name"
              >
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Last Name</mat-label>
              <input
                matInput
                [(ngModel)]="formData.last_name"
                name="last_name"
                maxlength="12"
                autocomplete="family-name"
              >
            </mat-form-field>
            
            <button
              mat-raised-button
              color="primary"
              type="submit"
              class="full-width"
              [disabled]="submitting"
              data-testid="register-submit"
            >
              <mat-icon aria-hidden="true">{{ submitting ? "hourglass_top" : "person_add" }}</mat-icon>
              <span>{{ submitting ? "Creating account..." : "Create account" }}</span>
            </button>
          </form>

          <div class="oauth-divider" aria-hidden="true">
            <span></span>
            <small>or</small>
            <span></span>
          </div>

          <div class="oauth-actions" aria-label="External account creation options">
            <button
              *ngFor="let provider of oauthProviders"
              mat-stroked-button
              type="button"
              class="oauth-button"
              [disabled]="!provider.enabled || submitting"
              [attr.data-testid]="'register-' + provider.id + '-oauth'"
              (click)="startOAuth(provider)"
            >
              <svg class="oauth-mark oauth-mark--google" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285f4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.58c2.09-1.93 3.27-4.78 3.27-8.09z" />
                <path fill="#34a853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.58-2.77c-.98.66-2.24 1.06-3.7 1.06-2.84 0-5.25-1.92-6.12-4.5H2.18v2.84C3.99 20.53 7.68 23 12 23z" />
                <path fill="#fbbc05" d="M5.88 14.13c-.22-.66-.35-1.36-.35-2.13s.13-1.47.35-2.13V7.03H2.18C1.43 8.53 1 10.22 1 12s.43 3.47 1.18 4.97l3.7-2.84z" />
                <path fill="#ea4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.68 1 3.99 3.47 2.18 7.03l3.7 2.84c.87-2.58 3.28-4.49 6.12-4.49z" />
              </svg>
              <span>Continue with {{ provider.label }}</span>
            </button>
          </div>

          <p class="status error" *ngIf="errorMessage" role="alert" data-testid="register-error">{{ errorMessage }}</p>
          
          <p class="login-link">
            Already have an account? <a routerLink="/login">Sign in</a>
          </p>
        </mat-card-content>
      </mat-card>
    </div>
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
      position: relative;
      max-width: 460px;
      width: 100%;
      padding: clamp(8px, 1vw, 14px);
      border: 1px solid var(--colour-border);
      border-radius: 32px;
      background: color-mix(in srgb, var(--colour-surface-elevated) 88%, transparent);
      color: var(--colour-text-primary);
      box-shadow:
        0 24px 70px var(--colour-shadow-medium),
        inset 0 1px 0 color-mix(in srgb, #ffffff 34%, transparent);
      backdrop-filter: blur(24px);
    }

    .auth-card-header {
      display: flex;
      justify-content: center;
      padding: var(--spacing-md) var(--spacing-sm) var(--spacing-sm);
      text-align: center;
    }

    .brand-lockup {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
    }

    .brand-logo-frame {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 104px;
      height: 104px;
      overflow: hidden;
      border: 1px solid color-mix(in srgb, var(--colour-border) 70%, transparent);
      border-radius: 32px;
      background: var(--colour-surface);
      box-shadow:
        0 18px 42px var(--colour-shadow-soft),
        inset 0 1px 0 color-mix(in srgb, #ffffff 34%, transparent);
    }

    .brand-logo {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .brand-eyebrow {
      margin: 0;
      color: var(--colour-text-secondary);
      font-size: 0.9rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
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
      margin-right: 8px;
    }

    .oauth-divider {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      align-items: center;
      gap: 12px;
      margin: var(--spacing-md) 0 var(--spacing-sm);
      color: var(--colour-text-secondary);
    }

    .oauth-divider span {
      height: 1px;
      background: var(--colour-border);
    }

    .oauth-divider small {
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .oauth-actions {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
    }

    .oauth-button {
      width: 100%;
      min-height: 44px;
      border-radius: var(--radius-pill);
      border-color: var(--colour-border);
      color: var(--colour-text-primary);
    }

    .oauth-mark {
      width: 24px;
      height: 24px;
      display: block;
      flex: 0 0 24px;
    }
    
    .login-link {
      text-align: center;
      margin-top: var(--spacing-md);
    }

    .login-link a {
      color: var(--colour-primary);
      font-weight: 800;
    }

    .status {
      margin-top: var(--spacing-sm);
    }

    .error {
      padding: 12px;
      border: 1px solid var(--colour-danger-text);
      border-radius: var(--radius-md);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    @keyframes authGradientDrift {
      from {
        background-position: 0% 50%;
      }
      to {
        background-position: 100% 50%;
      }
    }

    @media (max-width: 560px) {
      .auth-container {
        align-items: stretch;
        padding: var(--spacing-sm);
      }

      .auth-card {
        margin: auto 0;
        border-radius: 26px;
      }

      .oauth-actions {
        grid-template-columns: 1fr;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      .auth-container {
        animation: none;
      }
    }
  `]
})
export class RegisterComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);
  private readonly themeService = inject(ThemeService);
  readonly brandLogoSrc = computed(() =>
    this.themeService.isDark()
      ? 'assets/brand/openmynd-logo-dark.jpg'
      : 'assets/brand/openmynd-logo-light.jpg',
  );
  
  formData = {
    username: '',
    password: '',
    first_name: '',
    last_name: ''
  };
  confirmPassword = '';
  submitting = false;
  errorMessage = '';
  oauthProviders: OAuthProvider[] = this.defaultOAuthProviders();

  ngOnInit(): void {
    this.authService.getOAuthProviders().subscribe({
      next: ({ providers }) => {
        this.oauthProviders = this.supportedOAuthProviders(providers);
      },
      error: () => {
        this.oauthProviders = this.defaultOAuthProviders();
      },
    });
  }
  
  onSubmit(): void {
    this.errorMessage = '';

    if (this.formData.password !== this.confirmPassword) {
      this.errorMessage = 'Password confirmation does not match.';
      return;
    }

    if (this.formData.password.length < 8 || this.formData.password.length > 128) {
      this.errorMessage = 'Password must be between 8 and 128 characters.';
      return;
    }

    if (!/[A-Za-z]/.test(this.formData.password) || !/[0-9]/.test(this.formData.password)) {
      this.errorMessage = 'Password must include letters and numbers.';
      return;
    }

    this.submitting = true;
    this.authService.register(this.formData).subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: err => {
        this.errorMessage =
          err?.error?.error || 'Registration failed. Please try again.';
        this.submitting = false;
      },
      complete: () => {
        this.submitting = false;
      }
    });
  }

  startOAuth(provider: OAuthProvider): void {
    const startUrl = this.authService.getOAuthStartUrl(provider, '/dashboard');
    if (!provider.enabled || !startUrl) {
      return;
    }

    this.authService.clearLocalSession();
    window.location.assign(startUrl);
  }

  private defaultOAuthProviders(): OAuthProvider[] {
    return [
      {
        id: 'google',
        label: 'Google',
        enabled: false,
        configured: false,
        status: 'not_configured',
        start_url: null,
      },
    ];
  }

  private supportedOAuthProviders(providers: OAuthProvider[]): OAuthProvider[] {
    const supported = providers.filter((provider) => provider.id === 'google');
    return supported.length ? supported : this.defaultOAuthProviders();
  }
}
