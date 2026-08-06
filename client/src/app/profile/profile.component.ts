// Account screen mapping to users table columns
import { Component, HostListener, OnInit, inject } from "@angular/core";
import { CommonModule, Location } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { Router } from "@angular/router";
import { AppDialogService } from "../core/services/app-dialog.service";
import { AuthService } from "../core/services/auth.service";
import { ProfileService } from "../core/services/profile.service";
import { User } from "../core/models/user.model";

@Component({
  selector: "app-profile",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
  ],
  template: `
    <div class="profile-container" data-testid="account-page" *ngIf="profile">
      <div class="header-actions">
        <button
          mat-stroked-button
          type="button"
          class="header-back"
          (click)="goBack()"
          aria-label="Go back"
        >
          <mat-icon>arrow_back</mat-icon>
          Back
        </button>
      </div>

      <mat-card>
        <mat-card-header>
          <h1 mat-card-title>Account</h1>
        </mat-card-header>

        <mat-card-content>
          <section class="account-summary-grid" aria-label="Account summary">
            <div class="account-summary-card">
              <span class="summary-label">Email</span>
              <strong>{{ profile.email || "Not connected" }}</strong>
            </div>
            <div class="account-summary-card">
              <span class="summary-label">Sign-in method</span>
              <strong>{{ getSignInMethodLabel() }}</strong>
            </div>
            <div class="account-summary-card">
              <span class="summary-label">Registered</span>
              <strong>{{ getRegisteredDateLabel() }}</strong>
            </div>
          </section>

          <section class="profile-picture-section" aria-labelledby="profile-picture-heading">
            <div class="profile-picture-preview">
              <img
                *ngIf="profile.profile_picture_url; else profilePictureFallback"
                [src]="profile.profile_picture_url"
                [alt]="getProfilePictureAlt()"
              />
              <ng-template #profilePictureFallback>
                <mat-icon aria-hidden="true">person</mat-icon>
              </ng-template>
            </div>
            <div class="profile-picture-copy">
              <h3 id="profile-picture-heading">Profile picture</h3>
              <p>JPEG, PNG, or WebP. Up to 5 MB.</p>
              <div class="profile-picture-actions">
                <input
                  #profilePictureInput
                  class="visually-hidden"
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  aria-label="Choose profile picture"
                  (change)="onProfilePictureSelected($event)"
                />
                <button
                  mat-stroked-button
                  type="button"
                  [disabled]="pictureSaving"
                  (click)="profilePictureInput.click()"
                >
                  <mat-icon>upload</mat-icon>
                  {{
                    pictureSaving
                      ? "Saving..."
                      : profile.profile_picture_url
                        ? "Replace"
                        : "Upload"
                  }}
                </button>
                <button
                  *ngIf="profile.profile_picture_url"
                  mat-raised-button
                  color="warn"
                  type="button"
                  [disabled]="pictureSaving"
                  (click)="removeProfilePicture()"
                >
                  <mat-icon>delete</mat-icon>
                  Remove
                </button>
              </div>
            </div>
          </section>

          <form (ngSubmit)="onSubmit()">
            <h3 class="account-heading">Account and identity</h3>

            <div class="field-grid">
              <mat-form-field appearance="outline">
                <mat-label>First Name</mat-label>
                <input
                  matInput
                  [(ngModel)]="profile.first_name"
                  name="first_name"
                />
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Last Name</mat-label>
                <input
                  matInput
                  [(ngModel)]="profile.last_name"
                  name="last_name"
                />
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Age</mat-label>
                <input
                  matInput
                  type="number"
                  [(ngModel)]="profile.age"
                  name="age"
                />
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Display Name</mat-label>
                <input
	                  matInput
	                  [(ngModel)]="profile.display_name"
	                  name="display_name"
	                  maxlength="24"
	                />
	                <mat-hint align="start">Letters, numbers, hyphens, or underscores.</mat-hint>
	                <mat-hint align="end">{{ getDisplayNameLength() }}/24</mat-hint>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Pronouns</mat-label>
                <mat-select [(ngModel)]="profile.pronouns" name="pronouns">
                  <mat-option value="">Not set</mat-option>
                  <mat-option value="he/him">he/him</mat-option>
                  <mat-option value="she/her">she/her</mat-option>
                  <mat-option value="they/them">they/them</mat-option>
                  <mat-option value="he/they">he/they</mat-option>
                  <mat-option value="she/they">she/they</mat-option>
                  <mat-option value="prefer not to say"
                    >prefer not to say</mat-option
                  >
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Gender</mat-label>
                <mat-select [(ngModel)]="profile.gender" name="gender">
                  <mat-option value="">Not set</mat-option>
                  <mat-option value="man">man</mat-option>
                  <mat-option value="woman">woman</mat-option>
                  <mat-option value="non-binary">non-binary</mat-option>
                  <mat-option value="agender">agender</mat-option>
                  <mat-option value="other / prefer not to say"
                    >other / prefer not to say</mat-option
                  >
                </mat-select>
              </mat-form-field>
            </div>

            <div class="actions">
              <button
                mat-raised-button
                color="primary"
                type="submit"
                [disabled]="saving || !hasPendingChanges()"
              >
                {{ saving ? "Saving..." : "Save Changes" }}
              </button>
            </div>
          </form>

          <p class="status success" *ngIf="successMessage">
            {{ successMessage }}
          </p>
          <p class="status error" *ngIf="errorMessage">{{ errorMessage }}</p>

          <section class="danger-section" aria-labelledby="delete-account-heading">
            <div class="danger-copy">
              <h3 id="delete-account-heading">Delete account</h3>
              <p>Permanently removes this account and app-owned data.</p>
            </div>

            <div class="delete-account-grid">
              <mat-form-field *ngIf="requiresPassword()" appearance="outline">
                <mat-label>Password</mat-label>
                <input
                  matInput
                  type="password"
                  autocomplete="current-password"
                  [(ngModel)]="accountDeletePassword"
                  name="account_delete_password"
                  [disabled]="deletingAccount"
                />
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Type DELETE MY ACCOUNT</mat-label>
                <input
                  matInput
                  [(ngModel)]="accountDeleteConfirmation"
                  name="account_delete_confirmation"
                  [disabled]="deletingAccount"
                />
              </mat-form-field>
            </div>

            <p class="delete-note" *ngIf="!requiresPassword()">
              Google sign-in accounts are confirmed with the deletion phrase.
            </p>

            <button
              mat-raised-button
              color="warn"
              type="button"
              [disabled]="!canDeleteAccount()"
              (click)="deleteAccount()"
              data-testid="account-delete-account-button"
            >
              <mat-icon>delete_forever</mat-icon>
              {{ deletingAccount ? "Deleting..." : "Delete account" }}
            </button>
          </section>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [
    `
      .profile-container {
        max-width: 900px;
        margin: 0 auto;
      }

      .header-actions {
        margin-bottom: var(--spacing-md);
      }

      .header-back {
        border-color: var(--colour-border);
        color: var(--colour-text-secondary);
      }

      .header-back mat-icon {
        margin-right: var(--spacing-xs);
      }

      .account-summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
        gap: var(--spacing-sm);
        margin-bottom: var(--spacing-lg);
      }

      .account-summary-card {
        display: grid;
        gap: 0.2rem;
        min-height: 76px;
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
        color: var(--colour-text-primary);
      }

      .summary-label {
        color: var(--colour-text-secondary);
        font-size: 0.78rem;
        font-weight: 850;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }

      .account-summary-card strong {
        overflow-wrap: anywhere;
      }

      .profile-picture-section {
        display: flex;
        align-items: center;
        gap: var(--spacing-lg);
        margin-bottom: var(--spacing-lg);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
      }

      .profile-picture-preview {
        display: grid;
        place-items: center;
        width: 112px;
        height: 112px;
        flex: 0 0 112px;
        overflow: hidden;
        border: 2px solid var(--colour-border);
        border-radius: 50%;
        background: var(--colour-surface);
        color: var(--colour-text-secondary);
      }

      .profile-picture-preview img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .profile-picture-preview mat-icon {
        width: 56px;
        height: 56px;
        font-size: 56px;
      }

      .profile-picture-copy h3,
      .profile-picture-copy p {
        margin: 0;
      }

      .profile-picture-copy p {
        margin-top: var(--spacing-xs);
        color: var(--colour-text-secondary);
      }

      .profile-picture-actions {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-sm);
        margin-top: var(--spacing-md);
      }

      .visually-hidden {
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

      .field-grid {
        display: grid;
        gap: var(--spacing-md);
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      }

      .account-heading {
        margin: 0 0 var(--spacing-md);
      }

      .actions {
        display: flex;
        gap: var(--spacing-sm);
        justify-content: flex-end;
        margin-top: var(--spacing-md);
      }

      .status {
        margin-top: var(--spacing-sm);
      }

      .danger-section {
        display: grid;
        gap: var(--spacing-md);
        margin-top: var(--spacing-xl);
        padding: var(--spacing-md);
        border: 1px solid color-mix(in srgb, var(--colour-danger-text) 56%, var(--colour-border));
        border-radius: var(--radius-lg);
        background:
          radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--colour-danger-text) 12%, transparent), transparent 34%),
          var(--colour-surface-muted);
      }

      .danger-copy h3,
      .danger-copy p,
      .delete-note {
        margin: 0;
      }

      .danger-copy p,
      .delete-note {
        color: var(--colour-text-secondary);
        font-weight: 750;
      }

      .delete-account-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: var(--spacing-md);
      }

      .success {
        color: #2e7d32;
      }

      .error {
        color: #c62828;
      }

      @media (max-width: 600px) {
        .profile-picture-section {
          align-items: flex-start;
          flex-direction: column;
        }
      }
    `,
  ],
})
export class ProfileComponent implements OnInit {
  private appDialog = inject(AppDialogService);
  private authService = inject(AuthService);
  private profileService = inject(ProfileService);
  private location = inject(Location);
  private router = inject(Router);

  profile: User | null = null;
  saving = false;
  pictureSaving = false;
  deletingAccount = false;
  accountDeletePassword = "";
  accountDeleteConfirmation = "";
  successMessage = "";
  errorMessage = "";
  private initialProfileSnapshot = "";

  goBack(): void {
    if (this.canGoBack()) {
      this.location.back();
      return;
    }

    this.router.navigateByUrl("/entries");
  }

  ngOnInit(): void {
    this.profileService.getProfile().subscribe({
      next: (profile) => {
        this.profile = { ...profile };
        this.initialProfileSnapshot = this.serialiseProfile(this.profile);
      },
      error: () => {
        this.errorMessage = "Unable to load profile details.";
      },
    });
  }

  onSubmit(): void {
    if (!this.profile) {
      return;
    }

    const validationError = this.validateProfile(this.profile);
    if (validationError) {
      this.errorMessage = validationError;
      this.successMessage = "";
      return;
    }

    this.saving = true;
    this.successMessage = "";
    this.errorMessage = "";

    const updatePayload = this.buildProfileUpdatePayload(this.profile);

    this.profileService.updateProfile(updatePayload).subscribe({
      next: (response) => {
        this.successMessage = response.message;
        this.saving = false;
        if (this.profile) {
          this.initialProfileSnapshot = this.serialiseProfile(this.profile);
        }
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Account update failed. Please try again.";
        this.saving = false;
      },
    });
  }

  getSignInMethodLabel(): string {
    if (!this.profile) {
      return "Loading";
    }
    if (this.profile.auth_provider === "google" || this.profile.password_auth_enabled === false) {
      return "Google";
    }
    return "Password";
  }

  getRegisteredDateLabel(): string {
    const registeredAt = this.profile?.registered_at;
    if (!registeredAt) {
      return "Not recorded";
    }
    const date = new Date(registeredAt);
    if (Number.isNaN(date.getTime())) {
      return registeredAt;
    }
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  getDisplayNameLength(): number {
    return String(this.profile?.display_name || "").trim().length;
  }

  getProfilePictureAlt(): string {
    const name =
      this.profile?.display_name ||
      this.profile?.first_name ||
      this.profile?.username ||
      "User";
    return `${name}'s profile picture`;
  }

  onProfilePictureSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file || !this.profile) return;

    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      this.errorMessage = "Choose a JPEG, PNG, or WebP image.";
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      this.errorMessage = "Profile images must be 5 MB or smaller.";
      return;
    }

    this.pictureSaving = true;
    this.errorMessage = "";
    this.successMessage = "";
    this.profileService.uploadProfilePicture(file).subscribe({
      next: (response) => {
        this.profile = { ...response.user };
        this.pictureSaving = false;
        this.successMessage = response.message;
      },
      error: (error) => {
        this.pictureSaving = false;
        this.errorMessage =
          error?.error?.error || "Profile picture upload failed. Please try again.";
      },
    });
  }

  removeProfilePicture(): void {
    if (!this.profile?.profile_picture_url || this.pictureSaving) return;

    void this.appDialog.confirm({
      title: "Remove profile picture?",
      message: "Your account will return to the standard profile icon.",
      confirmText: "Remove picture",
      cancelText: "Keep picture",
      variant: "danger",
    }).then((confirmed) => {
      if (!confirmed) return;

      this.pictureSaving = true;
      this.errorMessage = "";
      this.successMessage = "";
      this.profileService.deleteProfilePicture().subscribe({
        next: (response) => {
          this.profile = { ...response.user };
          this.pictureSaving = false;
          this.successMessage = response.message;
        },
        error: (error) => {
          this.pictureSaving = false;
          this.errorMessage =
            error?.error?.error || "Profile picture removal failed. Please try again.";
        },
      });
    });
  }

  requiresPassword(): boolean {
    return this.profile?.password_auth_enabled !== false;
  }

  canDeleteAccount(): boolean {
    if (this.deletingAccount) return false;
    if (this.accountDeleteConfirmation.trim() !== "DELETE MY ACCOUNT") return false;
    return !this.requiresPassword() || this.accountDeletePassword.length > 0;
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

      this.deletingAccount = true;
      this.errorMessage = "";
      this.profileService.deleteAccount({
        password: this.requiresPassword() ? this.accountDeletePassword : "",
        confirmation: this.accountDeleteConfirmation.trim(),
      }).subscribe({
        next: () => {
          this.deletingAccount = false;
          this.authService.logout({
            reason: "account-deleted",
            replaceUrl: true,
          });
        },
        error: (error) => {
          this.deletingAccount = false;
          this.errorMessage =
            error?.error?.error || "Account deletion failed. Please try again.";
        },
      });
    });
  }

  hasPendingChanges(): boolean {
    if (!this.profile) {
      return false;
    }
    return this.serialiseProfile(this.profile) !== this.initialProfileSnapshot;
  }

  canDeactivate(): boolean | Promise<boolean> {
    if (!this.hasPendingChanges() || this.saving || this.deletingAccount) {
      return true;
    }

    return this.appDialog.confirm({
      title: "Discard Account changes?",
      message: "You have unsaved Account changes. Leaving now will discard them.",
      confirmText: "Discard changes",
      cancelText: "Stay here",
      variant: "danger",
    });
  }

  @HostListener("window:beforeunload", ["$event"])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (!this.hasPendingChanges() || this.saving || this.deletingAccount) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  }

	  private validateProfile(profile: User): string | null {
	    const displayName = String(profile.display_name || "").trim();
	    if (displayName && displayName.length > 24) {
	      return "Display name must be 24 characters or fewer.";
	    }
	    if (displayName && !/^[A-Za-z0-9][A-Za-z0-9_-]{0,23}$/.test(displayName)) {
	      return "Display name may only use letters, numbers, hyphens, and underscores.";
	    }

    return null;
  }

  private serialiseProfile(profile: User): string {
    return JSON.stringify({
      first_name: String(profile.first_name || "").trim(),
      last_name: String(profile.last_name || "").trim(),
      age: profile.age ?? null,
      display_name: String(profile.display_name || "").trim(),
      pronouns: String(profile.pronouns || "").trim(),
      gender: String(profile.gender || "").trim(),
    });
  }

  private buildProfileUpdatePayload(profile: User): Partial<User> {
    return {
      first_name: String(profile.first_name || "").trim(),
      last_name: String(profile.last_name || "").trim(),
      age: profile.age ?? undefined,
      display_name: String(profile.display_name || "").trim(),
      pronouns: String(profile.pronouns || "").trim(),
      gender: String(profile.gender || "").trim(),
    };
  }

  private canGoBack(): boolean {
    if (typeof window === "undefined") {
      return false;
    }

    const navigationId = window.history.state?.navigationId;
    if (typeof navigationId === "number") {
      return navigationId > 1;
    }

    return window.history.length > 1;
  }
}
