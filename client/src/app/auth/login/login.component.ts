// Login component
import { Component, OnInit, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterModule } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { AuthService } from "../../core/services/auth.service";

@Component({
  selector: "app-login",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
  ],
  template: `
    <div class="auth-container">
      <mat-card>
        <mat-card-header>
          <mat-card-title>Login to AI Diary</mat-card-title>
        </mat-card-header>

        <mat-card-content>
          <div *ngIf="sessionInfoMessage" class="info-message">
            <mat-icon>info</mat-icon>
            <span>{{ sessionInfoMessage }}</span>
          </div>

          <!-- Error Message Display -->
          <div *ngIf="errorMessage" class="error-message">
            <mat-icon>error</mat-icon>
            <span>{{ errorMessage }}</span>
          </div>

          <form (ngSubmit)="onSubmit()">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Username</mat-label>
              <input
                matInput
                [(ngModel)]="credentials.username"
                name="username"
                required
              />
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="credentials.password"
                name="password"
                required
              />
            </mat-form-field>

            <button
              mat-raised-button
              color="primary"
              type="submit"
              class="full-width"
              [disabled]="isLoading"
            >
              {{ isLoading ? "Logging in..." : "Login" }}
            </button>
          </form>

          <p class="register-link">
            Don't have an account? <a routerLink="/register">Register here</a>
          </p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [
    `
      .auth-container {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 100vh;
        background: #f5f5f5;
      }

      mat-card {
        max-width: 400px;
        width: 100%;
      }

      .full-width {
        width: 100%;
        margin-bottom: var(--spacing-sm);
      }

      .register-link {
        text-align: center;
        margin-top: var(--spacing-md);
      }

      .error-message {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        margin-bottom: 16px;
        background-color: #ffebee;
        border: 1px solid #e57373;
        border-radius: 4px;
        color: #c62828;
        font-size: 14px;
      }

      .info-message {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        margin-bottom: 16px;
        background-color: #e3f2fd;
        border: 1px solid #64b5f6;
        border-radius: 4px;
        color: #0d47a1;
        font-size: 14px;
      }

      .error-message mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }

      .info-message mat-icon {
        font-size: 20px;
        width: 20px;
        height: 20px;
      }
    `,
  ],
})
export class LoginComponent implements OnInit {
  private authService = inject(AuthService);
  private router = inject(Router);
  private route = inject(ActivatedRoute);

  credentials = {
    username: "",
    password: "",
  };

  errorMessage = "";
  sessionInfoMessage = "";
  isLoading = false;

  ngOnInit(): void {
    const reason = this.route.snapshot.queryParamMap.get("reason");
    if (reason === "session-expired") {
      this.sessionInfoMessage =
        "Your session has expired. Please log in again to continue.";
    }
  }

  onSubmit(): void {
    if (!this.credentials.username || !this.credentials.password) {
      this.errorMessage = "Please enter both username and password.";
      return;
    }

    this.isLoading = true;
    this.errorMessage = "";

    this.authService.login(this.credentials).subscribe({
      next: () => {
        this.isLoading = false;
        this.router.navigateByUrl(this.getSafeReturnUrl(), {
          replaceUrl: true,
        });
      },
      error: (err) => {
        this.isLoading = false;
        console.error("Login failed:", err);

        // Handle different error scenarios
        if (err.status === 401 || err.status === 400) {
          this.errorMessage =
            "Incorrect username or password. Please try again.";
        } else if (err.status === 0) {
          this.errorMessage =
            "Unable to connect to server. Please check your connection.";
        } else {
          this.errorMessage = "Login failed. Please try again.";
        }
      },
    });
  }

  private getSafeReturnUrl(): string {
    const returnUrl = this.route.snapshot.queryParamMap.get("returnUrl");

    if (
      !returnUrl ||
      !returnUrl.startsWith("/") ||
      returnUrl.startsWith("//")
    ) {
      return "/entries";
    }

    if (returnUrl.includes("://") || returnUrl === "/login") {
      return "/entries";
    }

    return returnUrl;
  }
}
