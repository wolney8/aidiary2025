import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { Router, RouterLink } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { AuthService } from "../../core/services/auth.service";
import { AuthResponse, User } from "../../core/models/user.model";

@Component({
  selector: "app-oauth-callback",
  standalone: true,
  imports: [CommonModule, RouterLink, MatCardModule, MatIconModule],
  template: `
    <main class="oauth-callback-shell" data-testid="oauth-callback-page">
      <mat-card class="oauth-callback-card">
        <mat-icon aria-hidden="true">
          {{ errorMessage ? "error" : "verified_user" }}
        </mat-icon>
        <h1>{{ errorMessage ? "Sign-in could not be completed" : "Completing sign-in" }}</h1>
        <p>{{ errorMessage || "Please wait while OpenMynd finishes signing you in." }}</p>
        <a *ngIf="errorMessage" routerLink="/login">Return to sign in</a>
      </mat-card>
    </main>
  `,
  styles: [`
    .oauth-callback-shell {
      box-sizing: border-box;
      display: grid;
      place-items: center;
      min-height: 100vh;
      padding: var(--spacing-md);
      background: var(--gradient-auth-ambient);
      background-size: 360% 360%;
    }

    .oauth-callback-card {
      width: min(100%, 440px);
      padding: var(--spacing-lg);
      border: 1px solid var(--colour-border);
      border-radius: 28px;
      background: color-mix(in srgb, var(--colour-surface-elevated) 92%, transparent);
      color: var(--colour-text-primary);
      text-align: center;
      box-shadow: 0 24px 70px var(--colour-shadow-medium);
      backdrop-filter: blur(22px);
    }

    .oauth-callback-card mat-icon {
      width: 44px;
      height: 44px;
      color: var(--colour-primary);
      font-size: 44px;
    }

    .oauth-callback-card h1 {
      margin: var(--spacing-sm) 0;
      font-size: clamp(1.8rem, 5vw, 2.4rem);
      letter-spacing: -0.05em;
    }

    .oauth-callback-card p {
      margin: 0;
      color: var(--colour-text-secondary);
      font-weight: 750;
    }

    .oauth-callback-card a {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 44px;
      margin-top: var(--spacing-md);
      padding: 0 1rem;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      font-weight: 850;
      text-decoration: none;
    }
  `],
})
export class OAuthCallbackComponent implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  errorMessage = "";

  ngOnInit(): void {
    const queryParams = new URLSearchParams(window.location.search);
    const error = queryParams.get("error");
    if (error) {
      this.errorMessage = error;
      return;
    }

    const fragment = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = fragment.get("token");
    const encodedUser = fragment.get("user");
    const returnUrl = this.getSafeReturnUrl(fragment.get("returnUrl"));
    if (!token || !encodedUser) {
      this.errorMessage = "The external provider did not return a valid OpenMynd session.";
      return;
    }

    try {
      const user = this.decodeUser(encodedUser);
      this.authService.completeOAuthLogin({ token, user } satisfies AuthResponse);
      window.history.replaceState({}, document.title, "/oauth/callback");
      void this.router.navigateByUrl(returnUrl, { replaceUrl: true });
    } catch {
      this.errorMessage = "The external sign-in response could not be read.";
    }
  }

  private decodeUser(encodedUser: string): User {
    const padded = encodedUser.padEnd(Math.ceil(encodedUser.length / 4) * 4, "=");
    const json = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as User;
  }

  private getSafeReturnUrl(raw: string | null): string {
    const value = raw || "/dashboard";
    if (!value.startsWith("/") || value.startsWith("//") || value.includes("://")) {
      return "/dashboard";
    }
    if (value === "/login" || value === "/register" || value === "/oauth/callback") {
      return "/dashboard";
    }
    return value;
  }
}
