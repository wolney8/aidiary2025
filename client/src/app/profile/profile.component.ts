// Profile screen mapping to users table columns
import { Component, OnInit, inject } from "@angular/core";
import { CommonModule, Location } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { MatCardModule } from "@angular/material/card";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { Router } from "@angular/router";
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
                <mat-label>Sex</mat-label>
                <mat-select [(ngModel)]="profile.sex" name="sex">
                  <mat-option value="female">Female</mat-option>
                  <mat-option value="male">Male</mat-option>
                  <mat-option value="non-binary">Non-binary</mat-option>
                  <mat-option value="prefer-not-to-say"
                    >Prefer not to say</mat-option
                  >
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline" class="goals-field">
                <mat-label>Goals</mat-label>
                <textarea
                  matInput
                  rows="3"
                  [(ngModel)]="profile.goals"
                  name="goals"
                ></textarea>
              </mat-form-field>
            </div>

            <div class="actions">
              <button
                mat-stroked-button
                type="button"
                (click)="openSettings()"
              >
                Open Settings
              </button>
              <button
                mat-raised-button
                color="primary"
                type="submit"
                [disabled]="saving"
              >
                Save Changes
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

      .goals-field {
        grid-column: 1 / -1;
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
  private profileService = inject(ProfileService);
  private location = inject(Location);
  private router = inject(Router);

  profile: User | null = null;
  saving = false;
  successMessage = "";
  errorMessage = "";

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

    this.saving = true;
    this.successMessage = "";
    this.errorMessage = "";

    const { id, username, ...updatePayload } = this.profile;

    this.profileService.updateProfile(updatePayload).subscribe({
      next: (response) => {
        this.successMessage = response.message;
        this.saving = false;
      },
      error: () => {
        this.errorMessage = "Profile update failed. Please try again.";
        this.saving = false;
      },
    });
  }

  openSettings(): void {
    this.router.navigateByUrl("/settings/personalisation");
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
