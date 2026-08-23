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
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatNativeDateModule } from "@angular/material/core";
import { MatDialog } from "@angular/material/dialog";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { firstValueFrom } from "rxjs";
import { AppDialogService } from "../core/services/app-dialog.service";
import { AuthService } from "../core/services/auth.service";
import {
  BillingTier,
  BillingPeriod,
  BillingStorageUsageMetric,
  BillingService,
  BillingStatus,
  BillingUsageMetric,
  CheckoutTier,
} from "../core/services/billing.service";
import { ProfileMediaAsset, ProfileService } from "../core/services/profile.service";
import { User } from "../core/models/user.model";
import { MediaPreviewDialogComponent } from "./media-preview-dialog.component";

interface AccountUsageCard {
  key: string;
  icon: string;
  label: string;
  description: string;
  metric?: BillingUsageMetric;
  storageMetric?: BillingStorageUsageMetric;
}

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
    MatCheckboxModule,
    MatDatepickerModule,
    MatNativeDateModule,
    RouterLink,
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
              <span
                *ngIf="profile.email"
                class="verification-pill"
                [class.is-verified]="profile.email_verified"
              >
                <mat-icon aria-hidden="true">{{ profile.email_verified ? "verified" : "mark_email_unread" }}</mat-icon>
                <span>{{ profile.email_verified ? "Verified" : "Unverified" }}</span>
              </span>
              <button
                *ngIf="profile.email && !profile.email_verified"
                mat-stroked-button
                type="button"
                class="summary-action"
                [disabled]="resendingVerification"
                (click)="resendVerificationEmail()"
                data-testid="account-resend-verification"
              >
                <mat-icon aria-hidden="true">{{ resendingVerification ? "hourglass_top" : "outgoing_mail" }}</mat-icon>
                <span>{{ resendingVerification ? "Sending..." : "Resend verification" }}</span>
              </button>
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
                  (input)="markProfileDirty()"
                />
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Last Name</mat-label>
                <input
                  matInput
                  [(ngModel)]="profile.last_name"
                  name="last_name"
                  (input)="markProfileDirty()"
                />
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Date of birth</mat-label>
                <input
                  matInput
                  [matDatepicker]="dateOfBirthPicker"
                  [(ngModel)]="dateOfBirthValue"
                  name="date_of_birth"
                  [max]="today"
                  (dateChange)="onDateOfBirthChange()"
                />
                <mat-datepicker-toggle
                  matIconSuffix
                  [for]="dateOfBirthPicker"
                ></mat-datepicker-toggle>
                <mat-datepicker #dateOfBirthPicker></mat-datepicker>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Display Name</mat-label>
                <input
                  matInput
                  [(ngModel)]="profile.display_name"
                  name="display_name"
                  maxlength="24"
                  (input)="markProfileDirty()"
                />
                <mat-hint align="start">Letters, numbers, hyphens, or underscores.</mat-hint>
                <mat-hint align="end">{{ getDisplayNameLength() }}/24</mat-hint>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Pronouns</mat-label>
                <mat-select
                  [(ngModel)]="profile.pronouns"
                  name="pronouns"
                  (selectionChange)="markProfileDirty()"
                >
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
                <mat-select
                  [(ngModel)]="profile.gender"
                  name="gender"
                  (selectionChange)="markProfileDirty()"
                >
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
                [disabled]="saving"
              >
                {{ saving ? "Saving..." : "Save Changes" }}
              </button>
            </div>
          </form>

          <p class="status success" *ngIf="successMessage">
            {{ successMessage }}
          </p>
          <p class="status error" *ngIf="errorMessage">{{ errorMessage }}</p>

          <section
            class="billing-section"
            aria-labelledby="billing-heading"
            data-testid="account-billing-section"
          >
            <div class="billing-header">
              <div class="billing-copy">
                <span class="section-eyebrow">Billing</span>
                <h3 id="billing-heading">Plan and subscription</h3>
                <p>View your plan, usage, upgrades, and billing controls.</p>
              </div>

              <div class="billing-actions">
                <div
                  class="billing-period-toggle"
                  role="group"
                  aria-label="Choose billing period for upgrades"
                  data-testid="account-billing-period-toggle"
                >
                  <button
                    type="button"
                    class="billing-period-option"
                    [class.is-active]="selectedBillingPeriod === 'monthly'"
                    [attr.aria-pressed]="selectedBillingPeriod === 'monthly'"
                    (click)="setBillingPeriod('monthly')"
                  >
                    Monthly
                  </button>
                  <button
                    type="button"
                    class="billing-period-option"
                    [class.is-active]="selectedBillingPeriod === 'annual'"
                    [attr.aria-pressed]="selectedBillingPeriod === 'annual'"
                    (click)="setBillingPeriod('annual')"
                  >
                    Annual
                    <span class="billing-saving-pill">Save up to 20%</span>
                  </button>
                </div>
                <button
                  *ngFor="let tier of getUpgradeTiers()"
                  mat-raised-button
                  color="primary"
                  type="button"
                  class="billing-action"
                  [disabled]="!canStartCheckout(tier)"
                  (click)="startCheckout(tier)"
                  [attr.data-testid]="'account-billing-' + tier"
                >
                  <mat-icon aria-hidden="true">
                    {{ billingBusyTier === tier ? "hourglass_top" : "open_in_new" }}
                  </mat-icon>
                  <span class="billing-action-label">
                    {{ getCheckoutButtonLabel(tier) }}
                  </span>
                </button>
                <button
                  mat-stroked-button
                  type="button"
                  class="billing-action"
                  [disabled]="!canOpenBillingPortal()"
                  (click)="openBillingPortal()"
                  data-testid="account-billing-portal"
                >
                  <mat-icon aria-hidden="true">
                    {{ billingPortalBusy ? "hourglass_top" : "receipt_long" }}
                  </mat-icon>
                  <span class="billing-action-label">
                    {{ billingPortalBusy ? "Opening..." : "Manage billing" }}
                  </span>
                </button>
                <a
                  mat-stroked-button
                  routerLink="/plans"
                  class="billing-action"
                  data-testid="account-billing-plans"
                >
                  <mat-icon aria-hidden="true">sell</mat-icon>
                  <span class="billing-action-label">See plans</span>
                </a>
                <a
                  *ngIf="billingStatus?.is_admin"
                  mat-stroked-button
                  routerLink="/admin"
                  class="billing-action"
                  data-testid="account-admin-plans"
                >
                  <mat-icon aria-hidden="true">admin_panel_settings</mat-icon>
                  <span class="billing-action-label">Admin console</span>
                </a>
              </div>
            </div>

            <div class="billing-current-card">
              <div class="billing-plan-mark">
                <mat-icon aria-hidden="true">workspace_premium</mat-icon>
              </div>
              <div>
                <span class="summary-label">Current plan</span>
                <strong>{{ getBillingTierLabel() }}</strong>
                <p class="billing-subscription-meta" *ngIf="getSubscriptionMetaLabel()">
                  {{ getSubscriptionMetaLabel() }}
                </p>
              </div>
              <span class="billing-status-pill" *ngIf="billingStatus">
                {{ getBillingStatusLabel() }}
              </span>
            </div>

            <div
              class="billing-usage-grid"
              *ngIf="getBillingUsageCards().length"
              aria-label="Monthly usage"
            >
              <article
                class="billing-usage-card"
                *ngFor="let card of getBillingUsageCards()"
                [attr.data-testid]="'account-usage-' + card.key"
              >
                <div class="billing-usage-heading">
                  <span class="billing-usage-icon">
                    <mat-icon aria-hidden="true">{{ card.icon }}</mat-icon>
                  </span>
                  <div>
                    <h4>{{ card.label }}</h4>
                    <p>{{ card.description }}</p>
                  </div>
                </div>
                <strong>{{ getCardUsageLabel(card) }}</strong>
                <small class="billing-usage-note" *ngIf="getCardUsageNote(card)">
                  {{ getCardUsageNote(card) }}
                </small>
                <div
                  class="billing-meter"
                  role="meter"
                  [attr.aria-label]="card.label + ' used this month'"
                  aria-valuemin="0"
                  [attr.aria-valuemax]="getCardUsageMax(card)"
                  [attr.aria-valuenow]="getCardUsageNow(card)"
                  [attr.aria-valuetext]="getCardUsageLabel(card)"
                >
                  <span [style.width.%]="getCardUsagePercent(card)"></span>
                </div>
              </article>
            </div>

            <section
              class="media-cleanup-panel"
              aria-labelledby="media-cleanup-heading"
              *ngIf="billingStatus?.usage?.storage"
              data-testid="account-media-cleanup"
            >
              <div class="media-cleanup-header">
                <div>
                  <span class="section-eyebrow">Storage cleanup</span>
                  <h3 id="media-cleanup-heading">Manage attachments</h3>
                  <p>Review measured attachment files that count toward storage limits.</p>
                </div>
                <button
                  mat-stroked-button
                  type="button"
                  class="billing-action"
                  (click)="toggleMediaCleanup()"
                  [disabled]="mediaAssetsLoading"
                  data-testid="account-media-cleanup-toggle"
                >
                  <mat-icon aria-hidden="true">
                    {{ showMediaCleanup ? "expand_less" : "folder_managed" }}
                  </mat-icon>
                  <span class="billing-action-label">
                    {{ showMediaCleanup ? "Hide media" : "Review media" }}
                  </span>
                </button>
              </div>

              <div class="media-cleanup-list" *ngIf="showMediaCleanup">
                <p class="billing-note" *ngIf="mediaAssetsLoading">Loading media...</p>
                <p class="status error" *ngIf="mediaAssetsError">{{ mediaAssetsError }}</p>

                <div
                  class="media-review-toolbar"
                  *ngIf="!mediaAssetsLoading && mediaAssets.length"
                  aria-label="Media review search and filters"
                >
                  <mat-form-field appearance="outline" class="media-search-field">
                    <mat-label>Search media</mat-label>
                    <mat-icon matPrefix aria-hidden="true">search</mat-icon>
                    <input
                      matInput
                      type="search"
                      [(ngModel)]="mediaSearchTerm"
                      name="media_search"
                      placeholder="Filename, entry, date..."
                      data-testid="account-media-search"
                    />
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="media-filter-field">
                    <mat-label>Type</mat-label>
                    <mat-select
                      [(ngModel)]="mediaTypeFilter"
                      name="media_type_filter"
                      data-testid="account-media-type-filter"
                    >
                      <mat-option value="all">All types</mat-option>
                      <mat-option value="image">Images</mat-option>
                      <mat-option value="pdf">PDFs</mat-option>
                      <mat-option value="audio">Audio</mat-option>
                      <mat-option value="other">Other</mat-option>
                    </mat-select>
                  </mat-form-field>

                  <mat-form-field appearance="outline" class="media-filter-field">
                    <mat-label>Size</mat-label>
                    <mat-select
                      [(ngModel)]="mediaSizeFilter"
                      name="media_size_filter"
                      data-testid="account-media-size-filter"
                    >
                      <mat-option value="all">All sizes</mat-option>
                      <mat-option value="small">Under 1 MB</mat-option>
                      <mat-option value="medium">1-10 MB</mat-option>
                      <mat-option value="large">Over 10 MB</mat-option>
                    </mat-select>
                  </mat-form-field>
                </div>

                <div
                  class="media-selection-toolbar"
                  *ngIf="!mediaAssetsLoading && mediaAssets.length"
                >
                  <mat-checkbox
                    [checked]="areAllFilteredMediaSelected()"
                    [indeterminate]="hasPartialFilteredMediaSelection()"
                    [disabled]="!getFilteredMediaAssets().length || bulkDeletingMediaAssets"
                    (change)="toggleAllFilteredMedia($event.checked)"
                    data-testid="account-media-select-all"
                  >
                    Select visible
                  </mat-checkbox>
                  <span class="media-selection-count">
                    {{ getSelectedMediaCount() }} selected ·
                    {{ getFilteredMediaAssets().length }} shown
                  </span>
                  <button
                    mat-stroked-button
                    type="button"
                    class="billing-action"
                    [disabled]="!getSelectedMediaCount() || bulkDeletingMediaAssets"
                    (click)="clearMediaSelection()"
                  >
                    <mat-icon aria-hidden="true">remove_done</mat-icon>
                    <span>Deselect all</span>
                  </button>
                  <button
                    mat-raised-button
                    color="warn"
                    type="button"
                    class="billing-action"
                    [disabled]="!getSelectedMediaCount() || bulkDeletingMediaAssets"
                    (click)="deleteSelectedMediaAssets()"
                    data-testid="account-media-delete-selected"
                  >
                    <mat-icon aria-hidden="true">
                      {{ bulkDeletingMediaAssets ? "hourglass_top" : "delete_sweep" }}
                    </mat-icon>
                    <span>
                      {{ bulkDeletingMediaAssets ? "Deleting..." : "Delete selected" }}
                    </span>
                  </button>
                </div>

                <p class="billing-note" *ngIf="!mediaAssetsLoading && !mediaAssets.length && !mediaAssetsError">
                  No measured attachments found.
                </p>
                <p
                  class="billing-note"
                  *ngIf="!mediaAssetsLoading && mediaAssets.length && !getFilteredMediaAssets().length"
                >
                  No media matches these filters.
                </p>

                <article
                  class="media-asset-row"
                  *ngFor="let asset of getFilteredMediaAssets()"
                  [class.is-selected]="isMediaAssetSelected(asset)"
                  [attr.data-testid]="'account-media-asset-' + asset.id"
                >
                  <mat-checkbox
                    class="media-asset-select"
                    [checked]="isMediaAssetSelected(asset)"
                    [disabled]="bulkDeletingMediaAssets || deletingMediaAssetId === asset.id"
                    (change)="toggleMediaAssetSelection(asset, $event.checked)"
                    [attr.aria-label]="'Select attachment ' + asset.filename"
                  ></mat-checkbox>
                  <button
                    class="media-asset-preview"
                    [class.is-image]="isImageMedia(asset)"
                    type="button"
                    [disabled]="!asset.url"
                    [attr.aria-label]="'Preview attachment ' + asset.filename"
                    (click)="openMediaPreview(asset)"
                  >
                    <img
                      *ngIf="isImageMedia(asset) && asset.url"
                      [src]="asset.url"
                      [alt]="''"
                      loading="lazy"
                    />
                    <mat-icon *ngIf="!isImageMedia(asset) || !asset.url" aria-hidden="true">
                      {{ getMediaAssetIcon(asset) }}
                    </mat-icon>
                  </button>
                  <div class="media-asset-copy">
                    <div class="media-asset-title-line">
                      <strong>{{ asset.filename }}</strong>
                      <span class="media-type-pill" [ngClass]="getMediaTypeClass(asset)">
                        <mat-icon aria-hidden="true">{{ getMediaAssetIcon(asset) }}</mat-icon>
                        <span>{{ getMediaTypeLabel(asset) }}</span>
                      </span>
                    </div>
                    <span>
                      {{ getEntryTypeLabel(asset.entry_type) }} · {{ asset.entry_title }} ·
                      {{ formatEntryDate(asset.entry_date) }}
                    </span>
                    <audio
                      *ngIf="isAudioMedia(asset) && asset.url"
                      class="media-audio-preview"
                      controls
                      preload="metadata"
                      [attr.aria-label]="'Audio preview for ' + asset.filename"
                    >
                      <source [src]="asset.url" [type]="asset.mime_type" />
                    </audio>
                  </div>
                  <span class="media-size-pill">{{ formatBytes(asset.file_size_bytes) }}</span>
                  <button
                    mat-stroked-button
                    type="button"
                    class="media-entry-link"
                    [disabled]="!asset.url"
                    (click)="openMediaPreview(asset)"
                  >
                    <mat-icon aria-hidden="true">visibility</mat-icon>
                    <span>Preview</span>
                  </button>
                  <a
                    mat-stroked-button
                    class="media-entry-link"
                    [routerLink]="['/entries', asset.entry_id]"
                    [queryParams]="{ entryType: asset.entry_type }"
                  >
                    <mat-icon aria-hidden="true">open_in_new</mat-icon>
                    <span>Entry</span>
                  </a>
                  <button
                    mat-icon-button
                    color="warn"
                    type="button"
                    class="media-delete-button"
                    [disabled]="deletingMediaAssetId === asset.id"
                    (click)="deleteMediaAsset(asset)"
                    [attr.aria-label]="'Delete attachment ' + asset.filename"
                  >
                    <mat-icon aria-hidden="true">
                      {{ deletingMediaAssetId === asset.id ? "hourglass_top" : "delete" }}
                    </mat-icon>
                  </button>
                </article>
              </div>
            </section>

            <p class="billing-note" *ngIf="billingStatus && !billingStatus.stripe_configured">
              Billing is unavailable in this environment.
            </p>
            <p class="billing-note" *ngIf="billingStatus && !billingStatus.has_billing_customer">
              Billing management appears after checkout starts.
            </p>
            <div class="billing-disclosure" data-testid="account-billing-disclosure">
              <mat-icon aria-hidden="true">verified_user</mat-icon>
              <p>
                Stripe hosts checkout and billing management. OpenMynd stores your
                plan entitlement and usage limits, not full card details.
              </p>
            </div>
          </section>

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

      .verification-pill {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        width: fit-content;
        margin-top: var(--spacing-xs);
        padding: 0.28rem 0.62rem;
        border: 1px solid var(--colour-warning-text);
        border-radius: var(--radius-pill);
        background: var(--colour-warning-bg);
        color: var(--colour-warning-text);
        font-size: 0.82rem;
        font-weight: 850;
      }

      .verification-pill.is-verified {
        border-color: var(--colour-success-text);
        background: var(--colour-success-bg);
        color: var(--colour-success-text);
      }

      .verification-pill mat-icon {
        width: 18px;
        height: 18px;
        font-size: 18px;
      }

      .summary-action {
        justify-self: start;
        width: fit-content;
        min-height: 40px;
        margin-top: var(--spacing-sm);
        border-radius: var(--radius-pill);
      }

      .summary-action mat-icon {
        margin-right: var(--spacing-xs);
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

      .section-eyebrow {
        color: var(--colour-text-secondary);
        font-size: 0.78rem;
        font-weight: 900;
        letter-spacing: 0.08em;
        text-transform: uppercase;
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

      .billing-section {
        display: grid;
        grid-template-columns: 1fr;
        gap: var(--spacing-md);
        margin-top: var(--spacing-lg);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
      }

      .billing-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--spacing-md);
      }

      .billing-copy {
        display: grid;
        gap: var(--spacing-xs);
      }

      .billing-copy h3,
      .billing-copy p,
      .billing-note {
        margin: 0;
      }

      .billing-copy p,
      .billing-subscription-meta,
      .billing-note {
        color: var(--colour-text-secondary);
        font-weight: 750;
      }

      .billing-disclosure {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: color-mix(in srgb, var(--colour-primary) 8%, var(--colour-surface));
        color: var(--colour-text-secondary);
        font-weight: 750;
      }

      .billing-disclosure mat-icon {
        width: 22px;
        height: 22px;
        color: var(--colour-primary);
        font-size: 22px;
      }

      .billing-disclosure p {
        margin: 0;
      }

      .billing-current-card {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr) auto;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background:
          radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--colour-primary) 18%, transparent), transparent 42%),
          var(--colour-surface);
      }

      .billing-current-card strong {
        display: block;
        color: var(--colour-text-primary);
        font-size: 1.35rem;
        line-height: 1.2;
      }

      .billing-plan-mark,
      .billing-usage-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: var(--radius-pill);
        background: color-mix(in srgb, var(--colour-primary) 16%, var(--colour-surface));
        color: var(--colour-primary);
      }

      .billing-plan-mark {
        width: 48px;
        height: 48px;
      }

      .billing-status-pill {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 0.18rem 0.58rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface);
        color: var(--colour-text-secondary);
        font-size: 0.82rem;
        font-weight: 850;
      }

      .billing-usage-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: var(--spacing-sm);
      }

      .billing-usage-card {
        display: grid;
        align-content: start;
        gap: var(--spacing-sm);
        min-height: 178px;
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface);
      }

      .billing-usage-heading {
        display: grid;
        grid-template-columns: auto minmax(0, 1fr);
        gap: var(--spacing-sm);
        align-items: start;
      }

      .billing-usage-heading h4,
      .billing-usage-heading p {
        margin: 0;
      }

      .billing-usage-heading h4 {
        color: var(--colour-text-primary);
        font-size: 1rem;
        line-height: 1.2;
      }

      .billing-usage-heading p {
        color: var(--colour-text-secondary);
        font-size: 0.88rem;
        font-weight: 700;
      }

      .billing-usage-icon {
        width: 40px;
        height: 40px;
      }

      .billing-usage-card > strong {
        color: var(--colour-text-primary);
        font-size: 1.12rem;
        line-height: 1.2;
      }

      .billing-usage-note {
        color: var(--colour-text-secondary);
        font-size: 0.78rem;
        font-weight: 750;
        line-height: 1.3;
      }

      .billing-meter {
        height: 10px;
        overflow: hidden;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface);
      }

      .billing-meter span {
        display: block;
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(
          90deg,
          var(--colour-primary),
          var(--colour-accent)
        );
      }

      .billing-actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: var(--spacing-sm);
      }

      .billing-period-toggle {
        display: inline-flex;
        align-items: center;
        width: fit-content;
        padding: 4px;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface);
        box-shadow: 0 8px 20px var(--colour-shadow-soft);
      }

      .billing-period-option {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: var(--spacing-xs);
        min-height: 40px;
        padding: 0 var(--spacing-sm);
        border: 0;
        border-radius: var(--radius-pill);
        background: transparent;
        color: var(--colour-text-secondary);
        cursor: pointer;
        font: inherit;
        font-weight: 900;
      }

      .billing-period-option.is-active {
        background: var(--colour-control-selected);
        color: var(--colour-control-selected-text);
      }

      .billing-period-option:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .billing-saving-pill {
        padding: 0.08rem 0.38rem;
        border-radius: var(--radius-pill);
        background: color-mix(in srgb, var(--colour-warning-text) 16%, var(--colour-surface));
        color: var(--colour-warning-text);
        font-size: 0.72rem;
        font-weight: 950;
        white-space: nowrap;
      }

      .billing-action {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        min-height: 44px;
        border-radius: var(--radius-pill);
      }

      .billing-action mat-icon {
        margin-right: 0;
      }

      .billing-action-label {
        line-height: 1.1;
      }

      .media-cleanup-panel {
        display: grid;
        gap: var(--spacing-md);
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface);
      }

      .media-cleanup-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--spacing-md);
      }

      .media-cleanup-header h3,
      .media-cleanup-header p {
        margin: 0;
      }

      .media-cleanup-header p {
        color: var(--colour-text-secondary);
        font-weight: 750;
      }

      .media-cleanup-list {
        display: grid;
        gap: var(--spacing-sm);
      }

      .media-review-toolbar,
      .media-selection-toolbar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
      }

      .media-review-toolbar mat-form-field {
        margin-bottom: -1.25rem;
      }

      .media-search-field {
        flex: 1 1 260px;
      }

      .media-filter-field {
        flex: 0 1 180px;
      }

      .media-selection-toolbar {
        justify-content: flex-start;
      }

      .media-selection-count {
        color: var(--colour-text-secondary);
        font-size: 0.88rem;
        font-weight: 850;
      }

      .media-asset-row {
        display: grid;
        grid-template-columns: auto auto minmax(0, 1fr) auto auto auto auto;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface-muted);
      }

      .media-asset-row.is-selected {
        border-color: var(--colour-primary);
        background: color-mix(in srgb, var(--colour-primary) 12%, var(--colour-surface-muted));
      }

      .media-asset-select {
        justify-self: center;
      }

      .media-asset-preview {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 56px;
        height: 56px;
        overflow: hidden;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: color-mix(in srgb, var(--colour-primary) 14%, var(--colour-surface));
        color: var(--colour-primary);
        cursor: pointer;
        text-decoration: none;
      }

      .media-asset-preview:disabled {
        cursor: not-allowed;
        opacity: 0.56;
      }

      .media-asset-preview.is-image {
        border-radius: var(--radius-md);
        background: var(--colour-surface);
      }

      .media-asset-preview img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .media-asset-preview mat-icon {
        width: 24px;
        height: 24px;
        font-size: 24px;
      }

      .media-asset-preview:focus-visible {
        outline: var(--focus-outline);
        outline-offset: var(--focus-offset);
      }

      .media-asset-copy {
        display: grid;
        min-width: 0;
        gap: 0.16rem;
      }

      .media-asset-title-line {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: var(--spacing-xs);
        min-width: 0;
      }

      .media-asset-copy strong,
      .media-asset-copy span {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .media-asset-copy span {
        color: var(--colour-text-secondary);
        font-size: 0.86rem;
        font-weight: 750;
      }

      .media-audio-preview {
        width: min(100%, 260px);
        height: 34px;
        margin-top: 0.2rem;
      }

      .media-size-pill,
      .media-type-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 32px;
        padding: 0.18rem 0.62rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface);
        color: var(--colour-text-secondary);
        font-size: 0.82rem;
        font-weight: 900;
        white-space: nowrap;
      }

      .media-type-pill {
        gap: 0.28rem;
        min-height: 28px;
        padding: 0.14rem 0.52rem;
        font-size: 0.76rem;
      }

      .media-type-pill mat-icon {
        width: 16px;
        height: 16px;
        font-size: 16px;
      }

      .media-type-pill.type-image {
        border-color: color-mix(in srgb, var(--colour-success-text) 48%, var(--colour-border));
        background: color-mix(in srgb, var(--colour-success-text) 12%, var(--colour-surface));
        color: var(--colour-success-text);
      }

      .media-type-pill.type-pdf {
        border-color: color-mix(in srgb, var(--colour-danger-text) 42%, var(--colour-border));
        background: color-mix(in srgb, var(--colour-danger-text) 10%, var(--colour-surface));
        color: var(--colour-danger-text);
      }

      .media-type-pill.type-audio {
        border-color: color-mix(in srgb, var(--colour-accent) 44%, var(--colour-border));
        background: color-mix(in srgb, var(--colour-accent) 12%, var(--colour-surface));
        color: var(--colour-accent);
      }

      .media-entry-link {
        display: inline-flex;
        align-items: center;
        gap: var(--spacing-xs);
        min-height: 40px;
        border-radius: var(--radius-pill);
      }

      .media-entry-link mat-icon {
        margin-right: 0;
      }

      .media-entry-link.is-disabled {
        opacity: 0.55;
        pointer-events: none;
      }

      .media-delete-button {
        border: 1px solid color-mix(in srgb, var(--colour-danger-text) 46%, var(--colour-border));
        background: color-mix(in srgb, var(--colour-danger-text) 10%, var(--colour-surface));
        color: var(--colour-danger-text);
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
        .billing-header,
        .billing-actions,
        .media-cleanup-header {
          align-items: stretch;
          flex-direction: column;
          justify-content: flex-start;
        }

        .billing-current-card {
          grid-template-columns: auto minmax(0, 1fr);
        }

        .billing-status-pill {
          grid-column: 1 / -1;
          justify-self: start;
        }

        .profile-picture-section {
          align-items: flex-start;
          flex-direction: column;
        }

        .media-asset-row {
          grid-template-columns: auto auto minmax(0, 1fr);
        }

        .media-size-pill,
        .media-entry-link {
          grid-column: 3 / -1;
          justify-self: start;
        }

        .media-delete-button {
          grid-column: 1 / -1;
          justify-self: start;
        }

      }
    `,
  ],
})
export class ProfileComponent implements OnInit {
  private appDialog = inject(AppDialogService);
  private authService = inject(AuthService);
  private billingService = inject(BillingService);
  private profileService = inject(ProfileService);
  private location = inject(Location);
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private dialog = inject(MatDialog);

  profile: User | null = null;
  saving = false;
  pictureSaving = false;
  deletingAccount = false;
  resendingVerification = false;
  accountDeletePassword = "";
  accountDeleteConfirmation = "";
  successMessage = "";
  errorMessage = "";
  billingStatus: BillingStatus | null = null;
  billingBusyTier: CheckoutTier | null = null;
  billingPortalBusy = false;
  showMediaCleanup = false;
  mediaAssets: ProfileMediaAsset[] = [];
  mediaAssetsLoading = false;
  mediaAssetsError = "";
  mediaSearchTerm = "";
  mediaTypeFilter: "all" | "image" | "pdf" | "audio" | "other" = "all";
  mediaSizeFilter: "all" | "small" | "medium" | "large" = "all";
  selectedMediaAssetIds = new Set<number>();
  bulkDeletingMediaAssets = false;
  deletingMediaAssetId: number | null = null;
  selectedBillingPeriod: BillingPeriod = "monthly";
  readonly today = new Date();
  dateOfBirthValue: Date | null = null;
  private initialProfileSnapshot = "";
  profileDirty = false;

  goBack(): void {
    if (this.canGoBack()) {
      this.location.back();
      return;
    }

    this.router.navigateByUrl("/entries");
  }

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((params) => {
      const billingResult = params.get("billing");
      if (billingResult === "success") {
        this.successMessage = "Billing updated.";
        this.clearBillingQueryParam();
      } else if (billingResult === "cancelled") {
        this.errorMessage = "Billing checkout was cancelled.";
        this.clearBillingQueryParam();
      }
    });
    this.profileService.getProfile().subscribe({
      next: (profile) => {
        this.profile = { ...profile };
        this.dateOfBirthValue = this.parseDateForPicker(profile.date_of_birth);
        this.initialProfileSnapshot = this.serialiseProfile(this.profile);
        this.profileDirty = false;
      },
      error: () => {
        this.errorMessage = "Unable to load profile details.";
      },
    });
    this.loadBillingStatus();
  }

  onSubmit(): void {
    if (!this.profile) {
      return;
    }
    if (!this.hasPendingChanges() && !this.profileDirty) {
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
        this.profile = { ...response.user };
        this.dateOfBirthValue = this.parseDateForPicker(response.user.date_of_birth);
        this.initialProfileSnapshot = this.serialiseProfile(this.profile);
        this.profileDirty = false;
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

  getBillingTierLabel(): string {
    const tier = this.billingStatus?.entitlement?.tier || "free";
    return this.getPlanName(tier);
  }

  getPlanName(tier: string): string {
    const plan = this.billingStatus?.plans?.find((item) => item.tier === tier);
    return plan?.public_name || this.toTitleCase(tier);
  }

  getBillingStatusLabel(): string {
    const status =
      this.billingStatus?.current_subscription?.status ||
      this.billingStatus?.entitlement?.stored_status ||
      this.billingStatus?.entitlement?.status ||
      "active";
    return this.toTitleCase(status.replace(/_/g, " "));
  }

  getSubscriptionMetaLabel(): string {
    const subscription = this.billingStatus?.current_subscription;
    if (!subscription) {
      return "";
    }
    const period =
      subscription.billing_period === "annual"
        ? "Annual billing"
        : subscription.billing_period === "monthly"
          ? "Monthly billing"
          : "Billing period pending";
    const endDate = this.formatBillingDate(subscription.current_period_end);
    if (subscription.cancel_at_period_end && endDate) {
      return `${period}. Cancels on ${endDate}.`;
    }
    if (endDate && subscription.status === "active") {
      return `${period}. Renews on ${endDate}.`;
    }
    return period;
  }

  getBillingUsageCards(): AccountUsageCard[] {
    const usage = this.billingStatus?.usage;
    if (!usage) {
      return [];
    }

    const cards: AccountUsageCard[] = [
      {
        key: "ai-responses",
        icon: "psychology",
        label: "AI responses",
        description: "Entry analysis and richer reflections.",
        metric: usage.ai_analysis,
      },
    ];

    if (usage.storage) {
      cards.push({
        key: "media-storage",
        icon: "hard_drive",
        label: "Media storage",
        description: "Images, PDFs, audio, and profile media.",
        storageMetric: usage.storage,
      });
    }

    if (usage.ai_image) {
      cards.push({
        key: "ai-images",
        icon: "auto_awesome",
        label: "AI images",
        description: "Generated diary and dream images.",
        metric: usage.ai_image,
      });
    }
    if (usage.ocr_page) {
      cards.push({
        key: "pdf-pages",
        icon: "picture_as_pdf",
        label: "PDF pages",
        description: "Pages processed for attachment context.",
        metric: usage.ocr_page,
      });
    }
    if (usage.transcription_minute) {
      cards.push({
        key: "audio-minutes",
        icon: "graphic_eq",
        label: "Audio minutes",
        description: "Voice notes transcribed for context.",
        metric: usage.transcription_minute,
      });
    }
    return cards;
  }

  getUsageLabel(metric: BillingUsageMetric): string {
    if (metric.unlimited || metric.limit === null) {
      return `${metric.used} used`;
    }
    return `${metric.used} of ${metric.limit}`;
  }

  getStorageUsageLabel(metric: BillingStorageUsageMetric): string {
    const used = this.formatMegabytes(metric.used_mb);
    if (metric.unlimited || metric.limit_mb === null) {
      return `${used} used`;
    }
    return `${used} of ${this.formatMegabytes(metric.limit_mb)}`;
  }

  getCardUsageLabel(card: AccountUsageCard): string {
    if (card.storageMetric) {
      return this.getStorageUsageLabel(card.storageMetric);
    }
    return card.metric ? this.getUsageLabel(card.metric) : "0 used";
  }

  getCardUsageNote(card: AccountUsageCard): string {
    if (!card.storageMetric?.estimated) {
      return "";
    }
    const count = card.storageMetric.unmeasured_assets;
    return `${count} older media ${count === 1 ? "item is" : "items are"} not byte-measured yet.`;
  }

  getCardUsageMax(card: AccountUsageCard): number | null {
    if (card.storageMetric) {
      return card.storageMetric.limit_mb;
    }
    return card.metric?.limit ?? null;
  }

  getCardUsageNow(card: AccountUsageCard): number {
    if (card.storageMetric) {
      return card.storageMetric.used_mb;
    }
    return card.metric?.used ?? 0;
  }

  getCardUsagePercent(card: AccountUsageCard): number {
    if (card.storageMetric) {
      if (card.storageMetric.unlimited || !card.storageMetric.limit_mb) {
        return 0;
      }
      return Math.min(100, Math.max(0, (card.storageMetric.used_mb / card.storageMetric.limit_mb) * 100));
    }
    return card.metric ? this.getUsagePercent(card.metric) : 0;
  }

  formatMegabytes(value: number): string {
    if (value >= 1024) {
      return `${(value / 1024).toFixed(value >= 10240 ? 0 : 1)} GB`;
    }
    return `${Number(value.toFixed(value < 10 && value > 0 ? 2 : 0))} MB`;
  }

  toggleMediaCleanup(): void {
    this.showMediaCleanup = !this.showMediaCleanup;
    if (this.showMediaCleanup && !this.mediaAssets.length) {
      this.loadMediaAssets();
    }
  }

  loadMediaAssets(): void {
    this.mediaAssetsLoading = true;
    this.mediaAssetsError = "";

    this.profileService.getMediaAssets(100).subscribe({
      next: (response) => {
        this.mediaAssets = response.assets;
        this.selectedMediaAssetIds = new Set(
          Array.from(this.selectedMediaAssetIds).filter((id) =>
            this.mediaAssets.some((asset) => asset.id === id),
          ),
        );
        this.mediaAssetsLoading = false;
      },
      error: (error) => {
        this.mediaAssetsError =
          error?.error?.error || "Media could not be loaded. Try again in a moment.";
        this.mediaAssetsLoading = false;
      },
    });
  }

  async deleteMediaAsset(asset: ProfileMediaAsset): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "Delete this attachment?",
      message: `${asset.filename} will be removed from its entry and storage. This cannot be undone.`,
      confirmText: "Delete attachment",
      cancelText: "Cancel",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }

    this.deletingMediaAssetId = asset.id;
    this.mediaAssetsError = "";
    this.profileService.deleteMediaAsset(asset.id).subscribe({
      next: () => {
        this.mediaAssets = this.mediaAssets.filter((item) => item.id !== asset.id);
        this.selectedMediaAssetIds.delete(asset.id);
        this.deletingMediaAssetId = null;
        this.loadBillingStatus();
      },
      error: (error) => {
        this.mediaAssetsError =
          error?.error?.error || "Attachment could not be deleted. Try again.";
        this.deletingMediaAssetId = null;
      },
    });
  }

  async deleteSelectedMediaAssets(): Promise<void> {
    const selectedAssets = this.mediaAssets.filter((asset) =>
      this.selectedMediaAssetIds.has(asset.id),
    );
    if (!selectedAssets.length) {
      return;
    }

    const confirmed = await this.appDialog.confirm({
      title: `Delete ${selectedAssets.length} attachments?`,
      message:
        "Selected attachments will be removed from their entries and storage. This cannot be undone.",
      confirmText: "Delete selected",
      cancelText: "Cancel",
      variant: "danger",
    });
    if (!confirmed) {
      return;
    }

    this.bulkDeletingMediaAssets = true;
    this.mediaAssetsError = "";
    const failed: string[] = [];

    for (const asset of selectedAssets) {
      try {
        await firstValueFrom(this.profileService.deleteMediaAsset(asset.id));
        this.mediaAssets = this.mediaAssets.filter((item) => item.id !== asset.id);
        this.selectedMediaAssetIds.delete(asset.id);
      } catch {
        failed.push(asset.filename);
      }
    }

    this.bulkDeletingMediaAssets = false;
    this.loadBillingStatus();
    if (failed.length) {
      this.mediaAssetsError = `Could not delete ${failed.length} attachment${
        failed.length === 1 ? "" : "s"
      }: ${failed.join(", ")}`;
    }
  }

  getFilteredMediaAssets(): ProfileMediaAsset[] {
    const term = this.mediaSearchTerm.trim().toLowerCase();
    return this.mediaAssets.filter((asset) => {
      if (this.mediaTypeFilter !== "all" && this.getMediaKind(asset) !== this.mediaTypeFilter) {
        return false;
      }
      if (!this.matchesMediaSizeFilter(asset)) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [
        asset.filename,
        asset.entry_title,
        asset.entry_date,
        this.getEntryTypeLabel(asset.entry_type),
        this.getMediaTypeLabel(asset),
        asset.mime_type,
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }

  toggleMediaAssetSelection(asset: ProfileMediaAsset, selected: boolean): void {
    const next = new Set(this.selectedMediaAssetIds);
    if (selected) {
      next.add(asset.id);
    } else {
      next.delete(asset.id);
    }
    this.selectedMediaAssetIds = next;
  }

  isMediaAssetSelected(asset: ProfileMediaAsset): boolean {
    return this.selectedMediaAssetIds.has(asset.id);
  }

  toggleAllFilteredMedia(selected: boolean): void {
    const next = new Set(this.selectedMediaAssetIds);
    for (const asset of this.getFilteredMediaAssets()) {
      if (selected) {
        next.add(asset.id);
      } else {
        next.delete(asset.id);
      }
    }
    this.selectedMediaAssetIds = next;
  }

  clearMediaSelection(): void {
    this.selectedMediaAssetIds = new Set();
  }

  getSelectedMediaCount(): number {
    return this.selectedMediaAssetIds.size;
  }

  areAllFilteredMediaSelected(): boolean {
    const filtered = this.getFilteredMediaAssets();
    return Boolean(filtered.length) && filtered.every((asset) => this.selectedMediaAssetIds.has(asset.id));
  }

  hasPartialFilteredMediaSelection(): boolean {
    const filtered = this.getFilteredMediaAssets();
    const selectedCount = filtered.filter((asset) => this.selectedMediaAssetIds.has(asset.id)).length;
    return selectedCount > 0 && selectedCount < filtered.length;
  }

  getEntryTypeLabel(entryType: ProfileMediaAsset["entry_type"]): string {
    return entryType === "dream" ? "Dream" : "Diary";
  }

  getMediaAssetIcon(asset: ProfileMediaAsset): string {
    if (asset.mime_type.startsWith("image/")) {
      return "image";
    }
    if (asset.mime_type === "application/pdf") {
      return "picture_as_pdf";
    }
    if (asset.mime_type.startsWith("audio/")) {
      return "graphic_eq";
    }
    return "attach_file";
  }

  getMediaTypeLabel(asset: ProfileMediaAsset): string {
    switch (this.getMediaKind(asset)) {
      case "image":
        return "Image";
      case "pdf":
        return "PDF";
      case "audio":
        return "Audio";
      default:
        return "File";
    }
  }

  getMediaTypeClass(asset: ProfileMediaAsset): string {
    return `type-${this.getMediaKind(asset)}`;
  }

  getMediaKind(asset: ProfileMediaAsset): "image" | "pdf" | "audio" | "other" {
    if (asset.mime_type.startsWith("image/")) {
      return "image";
    }
    if (asset.mime_type === "application/pdf") {
      return "pdf";
    }
    if (asset.mime_type.startsWith("audio/")) {
      return "audio";
    }
    return "other";
  }

  isImageMedia(asset: ProfileMediaAsset): boolean {
    return asset.mime_type.startsWith("image/");
  }

  isPdfMedia(asset: ProfileMediaAsset): boolean {
    return asset.mime_type === "application/pdf";
  }

  isAudioMedia(asset: ProfileMediaAsset): boolean {
    return asset.mime_type.startsWith("audio/");
  }

  canInlinePreview(asset: ProfileMediaAsset): boolean {
    return Boolean(asset.url) && (this.isImageMedia(asset) || this.isPdfMedia(asset) || this.isAudioMedia(asset));
  }

  openMediaPreview(asset: ProfileMediaAsset): void {
    if (!asset.url) {
      return;
    }
    this.dialog.open(MediaPreviewDialogComponent, {
      data: { asset },
      autoFocus: "dialog",
      restoreFocus: true,
      width: "72rem",
      maxWidth: "calc(100vw - 2rem)",
      maxHeight: "92vh",
    }).afterClosed().subscribe((result) => {
      if (result === "delete") {
        void this.deleteMediaAsset(asset);
      }
    });
  }

  private matchesMediaSizeFilter(asset: ProfileMediaAsset): boolean {
    const size = asset.file_size_bytes || 0;
    if (this.mediaSizeFilter === "small") {
      return size < 1024 * 1024;
    }
    if (this.mediaSizeFilter === "medium") {
      return size >= 1024 * 1024 && size <= 10 * 1024 * 1024;
    }
    if (this.mediaSizeFilter === "large") {
      return size > 10 * 1024 * 1024;
    }
    return true;
  }

  formatEntryDate(value: string): string {
    if (!value) {
      return "No date";
    }
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
  }

  formatBytes(value: number): string {
    if (value >= 1024 * 1024) {
      return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
    }
    if (value >= 1024) {
      return `${Math.round(value / 1024)} KB`;
    }
    return `${value} B`;
  }

  getUsagePercent(metric: BillingUsageMetric): number {
    if (metric.unlimited || !metric.limit) {
      return 0;
    }
    return Math.min(100, Math.max(0, (metric.used / metric.limit) * 100));
  }

  getUpgradeTiers(): CheckoutTier[] {
    const currentTier = this.billingStatus?.entitlement?.tier || "free";
    const currentRank = this.getTierRank(currentTier);
    return (["personal", "plus"] as CheckoutTier[]).filter((tier) => {
      return this.getTierRank(tier) > currentRank && this.billingStatus?.checkout_tiers.includes(tier);
    });
  }

  setBillingPeriod(period: BillingPeriod): void {
    this.selectedBillingPeriod = period;
  }

  getCheckoutButtonLabel(tier: CheckoutTier): string {
    if (this.billingBusyTier === tier) {
      return "Opening...";
    }
    const cadence = this.selectedBillingPeriod === "annual" ? "annual" : "monthly";
    return `Upgrade to ${this.getPlanName(tier)} ${cadence}`;
  }

  canStartCheckout(tier: CheckoutTier): boolean {
    return Boolean(
      this.billingStatus?.stripe_configured &&
        this.billingStatus.checkout_tiers.includes(tier) &&
        this.getTierRank(tier) > this.getTierRank(this.billingStatus.entitlement.tier) &&
        !this.billingBusyTier &&
        !this.billingPortalBusy,
    );
  }

  canOpenBillingPortal(): boolean {
    return Boolean(
      this.billingStatus?.stripe_configured &&
        this.billingStatus.has_billing_customer &&
        !this.billingBusyTier &&
        !this.billingPortalBusy,
    );
  }

  startCheckout(tier: CheckoutTier): void {
    if (!this.canStartCheckout(tier)) return;

    this.billingBusyTier = tier;
    this.errorMessage = "";
    this.successMessage = "";
    this.billingService.startCheckout(tier, this.selectedBillingPeriod).subscribe({
      next: (response) => {
        window.location.href = response.url;
      },
      error: (error) => {
        this.billingBusyTier = null;
        this.errorMessage =
          error?.error?.error || "Billing checkout could not be started.";
      },
    });
  }

  openBillingPortal(): void {
    if (!this.canOpenBillingPortal()) return;

    this.billingPortalBusy = true;
    this.errorMessage = "";
    this.successMessage = "";
    this.billingService.openCustomerPortal().subscribe({
      next: (response) => {
        window.location.href = response.url;
      },
      error: (error) => {
        this.billingPortalBusy = false;
        this.errorMessage =
          error?.error?.error || "Billing management could not be opened.";
      },
    });
  }

  resendVerificationEmail(): void {
    if (!this.profile?.email || this.profile.email_verified || this.resendingVerification) {
      return;
    }

    this.resendingVerification = true;
    this.errorMessage = "";
    this.successMessage = "";
    this.authService.requestEmailVerification().subscribe({
      next: (response) => {
        this.successMessage = response.message;
        this.resendingVerification = false;
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Verification email could not be sent.";
        this.resendingVerification = false;
      },
    });
  }

  getProfilePictureAlt(): string {
    const name =
      this.profile?.display_name ||
      this.profile?.first_name ||
      this.profile?.username ||
      "User";
    return `${name}'s profile picture`;
  }

  onDateOfBirthChange(): void {
    if (this.profile) {
      this.profile.date_of_birth = this.formatDateForApi(this.dateOfBirthValue);
    }
    this.markProfileDirty();
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

  markProfileDirty(): void {
    this.profileDirty = true;
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

    const dateOfBirth = this.formatDateForApi(this.dateOfBirthValue);
    if (dateOfBirth && this.dateOfBirthValue && this.dateOfBirthValue > this.today) {
      return "Date of birth cannot be in the future.";
    }
    profile.date_of_birth = dateOfBirth;

    return null;
  }

  private serialiseProfile(profile: User): string {
    return JSON.stringify({
      first_name: String(profile.first_name || "").trim(),
      last_name: String(profile.last_name || "").trim(),
      date_of_birth: String(profile.date_of_birth || "").trim(),
      display_name: String(profile.display_name || "").trim(),
      pronouns: String(profile.pronouns || "").trim(),
      gender: String(profile.gender || "").trim(),
    });
  }

  private buildProfileUpdatePayload(profile: User): Partial<User> {
    return {
      first_name: String(profile.first_name || "").trim(),
      last_name: String(profile.last_name || "").trim(),
      date_of_birth: this.formatDateForApi(this.dateOfBirthValue),
      display_name: String(profile.display_name || "").trim(),
      pronouns: String(profile.pronouns || "").trim(),
      gender: String(profile.gender || "").trim(),
    };
  }

  private parseDateForPicker(value?: string | null): Date | null {
    if (!value) {
      return null;
    }
    const [year, month, day] = value.split("-").map(Number);
    if (!year || !month || !day) {
      return null;
    }
    return new Date(year, month - 1, day);
  }

  private formatDateForApi(value: Date | null): string {
    if (!value) {
      return "";
    }
    const year = value.getFullYear();
    const month = `${value.getMonth() + 1}`.padStart(2, "0");
    const day = `${value.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  private loadBillingStatus(): void {
    this.billingService.getStatus().subscribe({
      next: (status) => {
        this.billingStatus = status;
      },
      error: () => {
        this.billingStatus = null;
      },
    });
  }

  private clearBillingQueryParam(): void {
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { billing: null },
      queryParamsHandling: "merge",
      replaceUrl: true,
    });
  }

  private toTitleCase(value: string): string {
    return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  private formatBillingDate(value?: string | null): string {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    }).format(date);
  }

  private getTierRank(tier: BillingTier): number {
    const ranks: Record<BillingTier, number> = {
      free: 0,
      personal: 1,
      plus: 2,
      therapeutic: 3,
      lifetime: 4,
      complimentary: 4,
      administrator: 5,
    };
    return ranks[tier] ?? 0;
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
