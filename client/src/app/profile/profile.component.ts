// Profile screen mapping to users table columns
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
    <div class="profile-container" *ngIf="profile">
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
          <mat-card-title>Profile</mat-card-title>
        </mat-card-header>

        <mat-card-content>
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
                  maxlength="8"
                />
                <mat-hint align="start">Letters only, up to 8 characters.</mat-hint>
                <mat-hint align="end">{{ getDisplayNameLength() }}/8</mat-hint>
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

      .success {
        color: #2e7d32;
      }

      .error {
        color: #c62828;
      }
    `,
  ],
})
export class ProfileComponent implements OnInit {
  private appDialog = inject(AppDialogService);
  private profileService = inject(ProfileService);
  private location = inject(Location);
  private router = inject(Router);

  profile: User | null = null;
  saving = false;
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

    const { id, username, ...updatePayload } = this.profile;

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
          error?.error?.error || "Profile update failed. Please try again.";
        this.saving = false;
      },
    });
  }

  getDisplayNameLength(): number {
    return String(this.profile?.display_name || "").trim().length;
  }

  hasPendingChanges(): boolean {
    if (!this.profile) {
      return false;
    }
    return this.serialiseProfile(this.profile) !== this.initialProfileSnapshot;
  }

  canDeactivate(): boolean | Promise<boolean> {
    if (!this.hasPendingChanges() || this.saving) {
      return true;
    }

    return this.appDialog.confirm({
      title: "Discard Profile changes?",
      message: "You have unsaved Profile changes. Leaving now will discard them.",
      confirmText: "Discard changes",
      cancelText: "Stay here",
      variant: "danger",
    });
  }

  @HostListener("window:beforeunload", ["$event"])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (!this.hasPendingChanges() || this.saving) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  }

  private validateProfile(profile: User): string | null {
    const displayName = String(profile.display_name || "").trim();
    if (displayName && displayName.length > 8) {
      return "Display name must be 8 characters or fewer.";
    }
    if (displayName && !/^[A-Za-z][A-Za-z '\-]{0,7}$/.test(displayName)) {
      return "Display name may only use letters, spaces, apostrophes, and hyphens.";
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
