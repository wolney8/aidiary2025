import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { AuthService } from "../core/services/auth.service";
import { ImportService } from "../core/services/import.service";
import { ProfileService } from "../core/services/profile.service";
import { AppDialogService } from "../core/services/app-dialog.service";

@Component({
  selector: "app-account-restricted",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatInputModule,
  ],
  template: `
    <section class="restricted-page" data-testid="account-restricted-page">
      <mat-card class="restricted-card">
        <mat-card-header>
          <mat-icon mat-card-avatar aria-hidden="true">lock</mat-icon>
          <mat-card-title>Account restricted</mat-card-title>
          <mat-card-subtitle>Contact the OpenMynd administrator for access.</mat-card-subtitle>
        </mat-card-header>

        <mat-card-content>
          <p>
            You cannot use OpenMynd while this account is restricted. Your data
            can still be exported or deleted from this page.
          </p>

          <p class="feedback success" *ngIf="successMessage">{{ successMessage }}</p>
          <p class="feedback error" *ngIf="errorMessage">{{ errorMessage }}</p>

          <div class="restricted-actions">
            <button
              mat-raised-button
              color="primary"
              type="button"
              class="pill-action"
              [disabled]="isExporting"
              (click)="downloadExport()"
              data-testid="restricted-export-button"
            >
              <mat-icon aria-hidden="true">download</mat-icon>
              <span>{{ isExporting ? "Preparing export" : "Export my data" }}</span>
            </button>

            <button
              mat-stroked-button
              type="button"
              class="pill-action"
              (click)="logout()"
              data-testid="restricted-logout-button"
            >
              <mat-icon aria-hidden="true">logout</mat-icon>
              <span>Logout</span>
            </button>
          </div>

          <div class="delete-panel">
            <h2>Delete account</h2>
            <p>This permanently removes this account and app-owned data.</p>

            <mat-form-field appearance="outline" *ngIf="requiresPassword()">
              <mat-label>Password</mat-label>
              <input
                matInput
                type="password"
                autocomplete="current-password"
                [(ngModel)]="accountDeletePassword"
                name="restricted_account_delete_password"
              />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Type DELETE MY ACCOUNT</mat-label>
              <input
                matInput
                [(ngModel)]="accountDeleteConfirmation"
                name="restricted_account_delete_confirmation"
              />
            </mat-form-field>

            <button
              mat-raised-button
              color="warn"
              type="button"
              class="pill-action pill-action--danger"
              [disabled]="!canDeleteAccount()"
              (click)="deleteAccount()"
              data-testid="restricted-delete-account-button"
            >
              <mat-icon aria-hidden="true">delete_forever</mat-icon>
              <span>{{ isDeleting ? "Deleting" : "Delete account" }}</span>
            </button>
          </div>
        </mat-card-content>
      </mat-card>
    </section>
  `,
  styles: [`
    .restricted-page {
      min-height: calc(100vh - 10rem);
      display: grid;
      place-items: start center;
      padding: var(--spacing-lg) var(--spacing-md);
    }

    .restricted-card {
      width: min(46rem, 100%);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      box-shadow: 0 24px 54px var(--colour-shadow-soft);
    }

    .restricted-card mat-card-header {
      gap: var(--spacing-sm);
      padding: var(--spacing-md) var(--spacing-md) 0;
    }

    .restricted-card [mat-card-avatar] {
      display: grid;
      place-items: center;
      border-radius: var(--radius-pill);
      background: var(--colour-warning-bg);
      color: var(--colour-warning-text);
    }

    .restricted-card mat-card-content {
      display: grid;
      gap: var(--spacing-md);
      padding: var(--spacing-md);
    }

    .restricted-card p,
    .delete-panel p {
      margin: 0;
      color: var(--colour-text-secondary);
      font-weight: 700;
    }

    .restricted-actions {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--spacing-sm);
    }

    .pill-action {
      min-height: 44px;
      border-radius: var(--radius-pill);
      font-weight: 900;
    }

    .pill-action mat-icon {
      margin-right: 0.45rem;
    }

    .pill-action--danger {
      width: fit-content;
    }

    .delete-panel {
      display: grid;
      gap: var(--spacing-sm);
      padding: var(--spacing-md);
      border: 1px solid color-mix(in srgb, var(--colour-danger-text) 42%, var(--colour-border));
      border-radius: var(--radius-lg);
      background: var(--colour-danger-bg);
    }

    .delete-panel h2 {
      margin: 0;
      color: var(--colour-danger-text);
      font-size: 1.15rem;
    }

    .delete-panel mat-form-field {
      width: 100%;
    }

    .feedback {
      margin: 0;
      padding: var(--spacing-sm);
      border-radius: var(--radius-lg);
      font-weight: 800;
    }

    .feedback.success {
      border: 1px solid color-mix(in srgb, var(--colour-success-text) 55%, var(--colour-border));
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
    }

    .feedback.error {
      border: 1px solid color-mix(in srgb, var(--colour-danger-text) 55%, var(--colour-border));
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }
  `],
})
export class AccountRestrictedComponent {
  private readonly authService = inject(AuthService);
  private readonly importService = inject(ImportService);
  private readonly profileService = inject(ProfileService);
  private readonly appDialog = inject(AppDialogService);

  readonly user = this.authService.getCurrentUser();
  isExporting = false;
  isDeleting = false;
  successMessage = "";
  errorMessage = "";
  accountDeletePassword = "";
  accountDeleteConfirmation = "";

  requiresPassword(): boolean {
    return Boolean(this.user?.password_auth_enabled);
  }

  canDeleteAccount(): boolean {
    if (this.isDeleting) return false;
    if (this.accountDeleteConfirmation.trim() !== "DELETE MY ACCOUNT") return false;
    return !this.requiresPassword() || this.accountDeletePassword.length > 0;
  }

  downloadExport(): void {
    if (this.isExporting) return;
    this.isExporting = true;
    this.errorMessage = "";
    this.successMessage = "";
    this.importService.downloadExport({ exportAll: true }).subscribe({
      next: ({ blob, filename }) => {
        this.isExporting = false;
        this.downloadBlob(blob, filename);
        this.successMessage = "Full data export downloaded.";
      },
      error: (error) => {
        this.isExporting = false;
        this.errorMessage =
          error?.error?.error || "Your data export could not be prepared.";
      },
    });
  }

  deleteAccount(): void {
    if (!this.canDeleteAccount()) return;
    void this.appDialog.confirm({
      title: "Permanently delete account?",
      message:
        "This deletes your account and all OpenMynd data for this user. This cannot be undone.",
      confirmText: "Delete account",
      cancelText: "Cancel",
      variant: "danger",
    }).then((confirmed) => {
      if (!confirmed) return;
      this.isDeleting = true;
      this.errorMessage = "";
      this.profileService.deleteAccount({
        password: this.requiresPassword() ? this.accountDeletePassword : "",
        confirmation: this.accountDeleteConfirmation.trim(),
      }).subscribe({
        next: () => {
          this.isDeleting = false;
          this.authService.logout({ reason: "account-deleted", replaceUrl: true });
        },
        error: (error) => {
          this.isDeleting = false;
          this.errorMessage =
            error?.error?.error || "Account deletion failed. Please try again.";
        },
      });
    });
  }

  logout(): void {
    this.authService.logout();
  }

  private downloadBlob(blob: Blob, filename?: string): void {
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 10);
    anchor.href = url;
    anchor.download = filename || `openmynd_export_${stamp}.zip`;
    anchor.click();
    window.URL.revokeObjectURL(url);
  }
}
