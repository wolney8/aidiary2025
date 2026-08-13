import { CommonModule } from "@angular/common";
import { Component, OnInit, inject, signal } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import { MatTooltipModule } from "@angular/material/tooltip";
import {
  AdminAnnouncement,
  AdminAnnouncementPayload,
  AdminAnnouncementPlacement,
  AdminAnnouncementSeverity,
  AdminAnnouncementStatus,
  AdminAuditEvent,
  AdminBillingUser,
  AdminOverview,
  AdminOperationsReadiness,
  AdminSecurityAuditReport,
  AdminService,
} from "../core/services/admin.service";
import { BillingPlan, BillingTier } from "../core/services/billing.service";
import { AnnouncementService } from "../core/services/announcement.service";

type AdminSection =
  | "overview"
  | "users"
  | "billing"
  | "announcements"
  | "operations"
  | "security"
  | "audit"
  | "stripe";

interface EditableAdminUser extends AdminBillingUser {
  selectedTier: BillingTier;
  selectedStatus: string;
  savedFeedback?: boolean;
}

interface EditablePlan extends BillingPlan {
  featuresText: string;
  quotaFields: Record<string, number | null>;
  snapshot: string;
}

interface AnnouncementDraft {
  id?: number;
  title: string;
  message: string;
  severity: AdminAnnouncementSeverity;
  placement: AdminAnnouncementPlacement;
  status: AdminAnnouncementStatus;
  starts_at: string;
  ends_at: string;
  timezone: string;
  dismissible: boolean;
  targetType: "all" | "tier" | "user";
  targetValues: string;
}

const QUOTA_FIELDS: Array<{
  key: string;
  label: string;
  unit: string;
}> = [
  { key: "ai_analysis_monthly", label: "AI responses", unit: "monthly" },
  { key: "ai_chat_monthly", label: "AI chat", unit: "monthly" },
  { key: "ai_images_monthly", label: "AI images", unit: "monthly" },
  { key: "ocr_pages_monthly", label: "OCR pages", unit: "monthly" },
  { key: "transcription_minutes_monthly", label: "Transcription", unit: "minutes" },
  { key: "storage_mb", label: "Storage", unit: "MB" },
];

@Component({
  selector: "app-admin-plan-catalogue",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatButtonModule,
    MatCheckboxModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatSelectModule,
    MatTooltipModule,
  ],
  template: `
    <section class="admin-console" data-testid="admin-console-page">
      <a routerLink="/account" class="admin-back-link" data-testid="admin-back-account">
        <mat-icon aria-hidden="true">arrow_back</mat-icon>
        <span>Back to Account</span>
      </a>

      <header class="admin-hero">
        <div>
          <p class="admin-eyebrow">Administrator</p>
          <h1>Admin console</h1>
          <p>Billing, user access, Stripe sync, and platform messages.</p>
        </div>
        <span
          class="admin-stripe-pill"
          [class.admin-stripe-pill--ready]="overview?.stripe?.configured"
          data-testid="admin-stripe-status"
        >
          <mat-icon aria-hidden="true">
            {{ overview?.stripe?.configured ? "verified" : "sync_problem" }}
          </mat-icon>
          <span>{{ overview?.stripe?.configured ? "Stripe connected" : "Stripe not configured" }}</span>
        </span>
      </header>

      <nav class="admin-section-tabs" aria-label="Admin console sections">
        <button
          *ngFor="let section of sections"
          type="button"
          class="admin-section-tab"
          [class.is-active]="activeSection() === section.id"
          (click)="setSection(section.id)"
          [attr.aria-pressed]="activeSection() === section.id"
          [attr.data-testid]="'admin-section-' + section.id"
        >
          <mat-icon aria-hidden="true">{{ section.icon }}</mat-icon>
          <span>{{ section.label }}</span>
        </button>
      </nav>

      <p class="admin-feedback is-error" *ngIf="errorMessage" role="alert">
        <mat-icon aria-hidden="true">error</mat-icon>
        <span>{{ errorMessage }}</span>
      </p>
      <p class="admin-feedback is-success" *ngIf="successMessage" role="status">
        <mat-icon aria-hidden="true">check_circle</mat-icon>
        <span>{{ successMessage }}</span>
      </p>

      <ng-container [ngSwitch]="activeSection()">
        <section
          *ngSwitchCase="'overview'"
          class="admin-section"
          aria-labelledby="admin-overview-heading"
          data-testid="admin-overview-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Overview</p>
              <h2 id="admin-overview-heading">Platform status</h2>
            </div>
            <button mat-stroked-button type="button" class="admin-pill-button" (click)="loadAll()">
              <mat-icon aria-hidden="true">refresh</mat-icon>
              <span>Refresh</span>
            </button>
          </div>

          <div class="admin-metric-grid">
            <article class="admin-metric-card">
              <mat-icon aria-hidden="true">group</mat-icon>
              <strong>{{ overview?.total_users ?? 0 }}</strong>
              <span>Users</span>
            </article>
            <article class="admin-metric-card">
              <mat-icon aria-hidden="true">workspace_premium</mat-icon>
              <strong>{{ overview?.paid_subscriptions ?? 0 }}</strong>
              <span>Paid subscriptions</span>
            </article>
            <article class="admin-metric-card">
              <mat-icon aria-hidden="true">admin_panel_settings</mat-icon>
              <strong>{{ overview?.manual_overrides ?? 0 }}</strong>
              <span>Manual overrides</span>
            </article>
            <article class="admin-metric-card">
              <mat-icon aria-hidden="true">campaign</mat-icon>
              <strong>{{ overview?.published_announcements ?? 0 }}</strong>
              <span>Published messages</span>
            </article>
          </div>
        </section>

        <section
          *ngSwitchCase="'users'"
          class="admin-section"
          aria-labelledby="admin-users-heading"
          data-testid="admin-users-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Users & access</p>
              <h2 id="admin-users-heading">Account entitlements</h2>
            </div>
            <form class="admin-search-bar" (ngSubmit)="loadUsers()">
              <mat-form-field appearance="outline">
                <mat-label>Search users</mat-label>
                <input
                  matInput
                  [(ngModel)]="userSearch"
                  name="admin_user_search"
                  placeholder="Email, username, or name"
                />
              </mat-form-field>
              <button mat-raised-button color="primary" type="submit" class="admin-pill-button">
                <mat-icon aria-hidden="true">search</mat-icon>
                <span>Search</span>
              </button>
            </form>
          </div>

          <div class="admin-table-wrap">
            <table class="admin-user-table">
              <thead>
                <tr>
                  <th scope="col">User</th>
                  <th scope="col">Sign-in</th>
                  <th scope="col">Current access</th>
                  <th scope="col">Monthly use</th>
                  <th scope="col">Set access</th>
                  <th scope="col">Action</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let user of users" [attr.data-testid]="'admin-user-row-' + user.id">
                  <td>
                    <div class="admin-user-cell">
                      <span class="admin-avatar" aria-hidden="true">{{ getUserInitial(user) }}</span>
                      <div>
                        <strong>{{ getUserDisplayName(user) }}</strong>
                        <span>{{ user.email || user.username }}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <div class="admin-chip-list">
                      <span
                        class="admin-chip"
                        *ngFor="let method of user.auth_methods"
                        [attr.data-testid]="'admin-user-auth-' + user.id + '-' + method"
                      >
                        {{ formatEnumLabel(method) }}
                      </span>
                      <span class="admin-chip admin-chip--muted" *ngIf="!user.auth_methods.length">None</span>
                    </div>
                  </td>
                  <td>
                    <div class="admin-chip-list admin-chip-list--access">
                      <span class="admin-chip admin-chip--strong">{{ formatEnumLabel(user.entitlement.tier) }}</span>
                      <span class="admin-chip">{{ formatEnumLabel(user.entitlement.source) }}</span>
                      <span class="admin-chip">{{ formatEnumLabel(user.entitlement.status) }}</span>
                      <span
                        class="admin-chip"
                        [class.admin-chip--danger]="isUserRestricted(user)"
                      >
                        {{ formatEnumLabel(user.account_status || "active") }}
                      </span>
                    </div>
                  </td>
                  <td class="admin-action-cell">
                    <span>{{ quotaText(user.usage?.ai_analysis?.used, user.usage?.ai_analysis?.limit) }} AI</span>
                    <span class="admin-muted">{{ quotaText(user.usage?.ai_image?.used, user.usage?.ai_image?.limit) }} images</span>
                  </td>
                  <td>
                    <div class="admin-inline-controls">
                      <mat-form-field appearance="outline">
                        <mat-label>Tier</mat-label>
                        <mat-select [(ngModel)]="user.selectedTier" [name]="'tier_' + user.id">
                          <mat-option *ngFor="let tier of tierOptions" [value]="tier">{{ formatEnumLabel(tier) }}</mat-option>
                        </mat-select>
                      </mat-form-field>
                      <mat-form-field appearance="outline">
                        <mat-label>Status</mat-label>
                        <mat-select [(ngModel)]="user.selectedStatus" [name]="'status_' + user.id">
                          <mat-option *ngFor="let status of statusOptions" [value]="status">{{ formatEnumLabel(status) }}</mat-option>
                        </mat-select>
                      </mat-form-field>
                    </div>
                  </td>
                  <td>
                    <div class="admin-icon-actions">
                      <button
                        mat-icon-button
                        type="button"
                        class="admin-icon-pill admin-icon-pill--save"
                        [disabled]="savingUserId === user.id || !isUserEntitlementDirty(user)"
                        (click)="saveUserEntitlement(user)"
                        [attr.aria-label]="'Save access changes for ' + getUserDisplayName(user)"
                        [matTooltip]="user.savedFeedback ? 'Saved' : 'Save access changes'"
                      >
                        <mat-icon aria-hidden="true">
                          {{ user.savedFeedback ? "check" : savingUserId === user.id ? "hourglass_top" : "save" }}
                        </mat-icon>
                      </button>
                      <button
                        mat-icon-button
                        type="button"
                        class="admin-icon-pill"
                        [class.admin-icon-pill--danger]="!isUserRestricted(user)"
                        [disabled]="savingUserId === user.id"
                        (click)="toggleUserRestriction(user)"
                        [attr.aria-label]="(isUserRestricted(user) ? 'Restore access for ' : 'Restrict access for ') + getUserDisplayName(user)"
                        [matTooltip]="isUserRestricted(user) ? 'Restore access' : 'Restrict access'"
                      >
                        <mat-icon aria-hidden="true">
                          {{ isUserRestricted(user) ? "lock_open" : "block" }}
                        </mat-icon>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
            <p class="admin-empty" *ngIf="!users.length && !usersLoading">No users found.</p>
          </div>
        </section>

        <section
          *ngSwitchCase="'billing'"
          class="admin-section"
          aria-labelledby="admin-billing-heading"
          data-testid="admin-billing-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Plans & quotas</p>
              <h2 id="admin-billing-heading">Plan matrix</h2>
            </div>
          </div>

          <div class="admin-plan-grid">
            <article
              class="admin-plan-card"
              *ngFor="let plan of plans"
              [attr.data-testid]="'admin-plan-card-' + plan.tier"
            >
              <header>
                <div>
                  <h3>{{ plan.public_name }}</h3>
                  <p>{{ plan.strapline }}</p>
                </div>
                <mat-checkbox [(ngModel)]="plan.is_public" [name]="plan.tier + '_public'">
                  Public
                </mat-checkbox>
              </header>

              <div class="admin-plan-price-row">
                <mat-form-field appearance="outline">
                  <mat-label>Monthly pence</mat-label>
                  <input matInput type="number" [(ngModel)]="plan.monthly_price_gbp_pence" [name]="plan.tier + '_monthly'" />
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>Annual pence</mat-label>
                  <input matInput type="number" [(ngModel)]="plan.annual_price_gbp_pence" [name]="plan.tier + '_annual'" />
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>Discount %</mat-label>
                  <input matInput type="number" [(ngModel)]="plan.annual_discount_percent" [name]="plan.tier + '_discount'" />
                </mat-form-field>
              </div>

              <mat-form-field appearance="outline" class="admin-full-width">
                <mat-label>Public name</mat-label>
                <input matInput [(ngModel)]="plan.public_name" [name]="plan.tier + '_name'" maxlength="40" />
              </mat-form-field>

              <mat-form-field appearance="outline" class="admin-full-width">
                <mat-label>Strapline</mat-label>
                <input matInput [(ngModel)]="plan.strapline" [name]="plan.tier + '_strapline'" maxlength="90" />
              </mat-form-field>

              <mat-form-field appearance="outline" class="admin-full-width">
                <mat-label>Description</mat-label>
                <textarea matInput rows="2" [(ngModel)]="plan.description" [name]="plan.tier + '_description'"></textarea>
              </mat-form-field>

              <div class="admin-quota-grid">
                <mat-form-field appearance="outline" *ngFor="let quota of quotaFields">
                  <mat-label>{{ quota.label }}</mat-label>
                  <input
                    matInput
                    type="number"
                    [(ngModel)]="plan.quotaFields[quota.key]"
                    [name]="plan.tier + '_' + quota.key"
                    placeholder="Blank = unlimited"
                  />
                  <span matTextSuffix>{{ quota.unit }}</span>
                </mat-form-field>
              </div>

              <mat-form-field appearance="outline" class="admin-full-width">
                <mat-label>Features, one per line</mat-label>
                <textarea matInput rows="5" [(ngModel)]="plan.featuresText" [name]="plan.tier + '_features'"></textarea>
              </mat-form-field>

              <footer class="admin-card-actions">
                <button
                  mat-stroked-button
                  type="button"
                  class="admin-pill-button"
                  [disabled]="!isPlanDirty(plan)"
                  (click)="resetPlan(plan)"
                >
                  <mat-icon aria-hidden="true">undo</mat-icon>
                  <span>Cancel</span>
                </button>
                <button
                  mat-raised-button
                  color="primary"
                  type="button"
                  class="admin-pill-button"
                  [disabled]="savingTier === plan.tier || !isPlanDirty(plan)"
                  (click)="savePlan(plan)"
                >
                  <mat-icon aria-hidden="true">{{ savingTier === plan.tier ? "hourglass_top" : "save" }}</mat-icon>
                  <span>{{ savingTier === plan.tier ? "Saving" : "Save plan" }}</span>
                </button>
              </footer>
            </article>
          </div>
        </section>

        <section
          *ngSwitchCase="'announcements'"
          class="admin-section"
          aria-labelledby="admin-announcements-heading"
          data-testid="admin-announcements-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Announcements</p>
              <h2 id="admin-announcements-heading">User banners and bell messages</h2>
            </div>
          </div>

          <form class="admin-announcement-form" (ngSubmit)="saveAnnouncement()">
            <div class="admin-plan-price-row">
              <mat-form-field appearance="outline">
                <mat-label>Title</mat-label>
                <input matInput [(ngModel)]="announcementDraft.title" name="announcement_title" maxlength="90" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Severity</mat-label>
                <mat-select [(ngModel)]="announcementDraft.severity" name="announcement_severity">
                  <mat-option value="info">Info</mat-option>
                  <mat-option value="success">Success</mat-option>
                  <mat-option value="warning">Warning</mat-option>
                  <mat-option value="critical">Critical</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Placement</mat-label>
                <mat-select [(ngModel)]="announcementDraft.placement" name="announcement_placement">
                  <mat-option value="banner">Banner</mat-option>
                  <mat-option value="bell">Bell</mat-option>
                  <mat-option value="both">Both</mat-option>
                </mat-select>
              </mat-form-field>
              <div class="admin-status-control" role="group" aria-label="Announcement status">
                <span class="admin-status-label">Status</span>
                <button
                  type="button"
                  class="admin-schedule-chip"
                  [class.is-active]="announcementDraft.status === 'draft'"
                  (click)="announcementDraft.status = 'draft'"
                >Draft</button>
                <button
                  type="button"
                  class="admin-schedule-chip"
                  [class.is-active]="announcementDraft.status === 'published'"
                  (click)="announcementDraft.status = 'published'"
                >Published</button>
                <p class="admin-field-hint">Draft is hidden. Published appears during its schedule. Archived is retired.</p>
              </div>
            </div>

            <mat-form-field appearance="outline" class="admin-full-width">
              <mat-label>Message</mat-label>
              <textarea matInput rows="3" [(ngModel)]="announcementDraft.message" name="announcement_message" maxlength="500"></textarea>
            </mat-form-field>

            <div class="admin-plan-price-row">
              <mat-form-field appearance="outline">
                <mat-label>Target</mat-label>
                <mat-select [(ngModel)]="announcementDraft.targetType" name="announcement_target_type">
                  <mat-option value="all">All users</mat-option>
                  <mat-option value="tier">Plan tiers</mat-option>
                  <mat-option value="user">User IDs</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Target values</mat-label>
                <input
                  matInput
                  [(ngModel)]="announcementDraft.targetValues"
                  name="announcement_target_values"
                  [disabled]="announcementDraft.targetType === 'all'"
                  placeholder="Comma-separated values"
                />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Timezone</mat-label>
                <mat-select [(ngModel)]="announcementDraft.timezone" name="announcement_timezone">
                  <mat-option *ngFor="let timezone of timezoneOptions" [value]="timezone">{{ timezone }}</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Starts</mat-label>
                <input
                  matInput
                  type="datetime-local"
                  [min]="minDateTimeLocal"
                  [(ngModel)]="announcementDraft.starts_at"
                  name="announcement_starts"
                />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Ends</mat-label>
                <input
                  matInput
                  type="datetime-local"
                  [min]="minDateTimeLocal"
                  [(ngModel)]="announcementDraft.ends_at"
                  name="announcement_ends"
                />
              </mat-form-field>
            </div>

            <div class="admin-schedule-row" aria-label="Announcement schedule shortcuts">
              <button type="button" class="admin-schedule-chip" (click)="publishNow()">Now</button>
              <button type="button" class="admin-schedule-chip" (click)="scheduleForHours(1, 24)">Starts in 1h · 1 day</button>
              <button type="button" class="admin-schedule-chip" (click)="scheduleForHours(24, 72)">Tomorrow · 3 days</button>
              <button type="button" class="admin-schedule-chip" (click)="scheduleForHours(0, 168)">Now · 1 week</button>
              <p class="admin-field-hint">
                Dismissible banners stay dismissed for that user. Create a new announcement to show a fresh message.
              </p>
            </div>

            <div class="admin-card-actions">
              <mat-checkbox [(ngModel)]="announcementDraft.dismissible" name="announcement_dismissible">
                Dismissible
              </mat-checkbox>
              <button mat-stroked-button type="button" class="admin-pill-button" (click)="resetAnnouncementDraft()">
                <mat-icon aria-hidden="true">add</mat-icon>
                <span>New message</span>
              </button>
              <button mat-raised-button color="primary" type="submit" class="admin-pill-button" [disabled]="savingAnnouncement">
                <mat-icon aria-hidden="true">{{ savingAnnouncement ? "hourglass_top" : "save" }}</mat-icon>
                <span>{{ announcementDraft.id ? "Save message" : "Create message" }}</span>
              </button>
            </div>
          </form>

          <div class="admin-announcement-list">
            <article
              class="admin-announcement-row"
              *ngFor="let announcement of announcements"
              [attr.data-testid]="'admin-announcement-' + announcement.id"
            >
              <div>
                <span class="admin-chip admin-chip--strong">{{ formatEnumLabel(announcement.status) }}</span>
                <h3>{{ announcement.title }}</h3>
                <p>{{ announcement.message }}</p>
                <span class="admin-muted">
                  {{ formatEnumLabel(announcement.severity) }} · {{ formatEnumLabel(announcement.placement) }} · {{ targetSummary(announcement) }}
                </span>
                <span class="admin-muted">
                  Fires {{ scheduleSummary(announcement) }} · Read {{ announcement.read_count || 0 }} · Dismissed {{ announcement.dismissed_count || 0 }}
                </span>
              </div>
              <div class="admin-row-actions">
                <button mat-stroked-button type="button" class="admin-pill-button" (click)="editAnnouncement(announcement)">
                  <mat-icon aria-hidden="true">edit</mat-icon>
                  <span>Edit</span>
                </button>
                <button
                  mat-button
                  type="button"
                  class="admin-pill-button admin-danger-action"
                  [disabled]="announcement.status === 'archived'"
                  (click)="archiveAnnouncement(announcement)"
                >
                  <mat-icon aria-hidden="true">archive</mat-icon>
                  <span>Archive</span>
                </button>
              </div>
            </article>
          </div>
        </section>

        <section
          *ngSwitchCase="'operations'"
          class="admin-section"
          aria-labelledby="admin-operations-heading"
          data-testid="admin-operations-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Operations</p>
              <h2 id="admin-operations-heading">Production readiness</h2>
              <p>Safe runtime checks for database, auth, billing, and process health.</p>
            </div>
            <button
              mat-stroked-button
              type="button"
              class="admin-pill-button"
              (click)="loadOperations()"
              data-testid="admin-operations-refresh"
            >
              <mat-icon aria-hidden="true">refresh</mat-icon>
              <span>Refresh</span>
            </button>
          </div>

          <div class="admin-operations-grid" *ngIf="operations as ops; else operationsLoading">
            <article class="admin-readiness-card">
              <span class="admin-readiness-icon" aria-hidden="true">
                <mat-icon>database</mat-icon>
              </span>
              <div>
                <p class="admin-eyebrow">Database</p>
                <h3>{{ formatEnumLabel(ops.database.provider) }}</h3>
                <span class="admin-muted">
                  {{ ops.database.ok ? "Read check passed" : "Read check failed" }}
                  <ng-container *ngIf="ops.database.latency_ms !== null && ops.database.latency_ms !== undefined">
                    · {{ ops.database.latency_ms }} ms
                  </ng-container>
                </span>
              </div>
            </article>

            <article class="admin-readiness-card">
              <span class="admin-readiness-icon" aria-hidden="true">
                <mat-icon>shield_lock</mat-icon>
              </span>
              <div>
                <p class="admin-eyebrow">Sessions</p>
                <h3>{{ ops.auth.cookie_mode ? "Cookie auth" : "Header tokens" }}</h3>
                <span class="admin-muted">
                  CSRF {{ ops.auth.csrf_protect ? "enabled" : "not enabled" }}
                </span>
              </div>
            </article>

            <article class="admin-readiness-card">
              <span class="admin-readiness-icon" aria-hidden="true">
                <mat-icon>payments</mat-icon>
              </span>
              <div>
                <p class="admin-eyebrow">Billing</p>
                <h3>{{ ops.stripe.configured ? "Stripe ready" : "Stripe incomplete" }}</h3>
                <span class="admin-muted">
                  {{ ops.stripe.checkout_tiers.length || 0 }} checkout tiers
                </span>
              </div>
            </article>

            <article class="admin-readiness-card">
              <span class="admin-readiness-icon" aria-hidden="true">
                <mat-icon>monitor_heart</mat-icon>
              </span>
              <div>
                <p class="admin-eyebrow">Runtime</p>
                <h3>{{ formatEnumLabel(ops.app.environment) }}</h3>
                <span class="admin-muted">
                  Rate limits: {{ formatEnumLabel(ops.rate_limits.storage) }}
                </span>
              </div>
            </article>
          </div>

          <ng-template #operationsLoading>
            <p class="admin-empty">Readiness checks have not loaded yet.</p>
          </ng-template>

          <div class="admin-readiness-check-list" *ngIf="operations?.checks?.length">
            <article
              class="admin-readiness-check"
              *ngFor="let check of operations?.checks"
              [attr.data-testid]="'admin-operations-check-' + check.key"
            >
              <span
                class="admin-readiness-status"
                [ngClass]="readinessStatusClass(check.status)"
              >
                <mat-icon aria-hidden="true">{{ readinessIcon(check.status) }}</mat-icon>
                <span>{{ formatEnumLabel(check.status) }}</span>
              </span>
              <div>
                <h3>{{ check.label }}</h3>
                <p>{{ check.detail }}</p>
              </div>
            </article>
          </div>

          <article class="admin-operation-action-card" data-testid="admin-test-email-card">
            <span class="admin-readiness-icon" aria-hidden="true">
              <mat-icon>outgoing_mail</mat-icon>
            </span>
            <div>
              <p class="admin-eyebrow">Transactional email</p>
              <h3>Send test email</h3>
              <p>Verify the configured provider can deliver account emails.</p>
            </div>
            <form class="admin-operation-action-form" (ngSubmit)="sendTestEmail()">
              <mat-form-field appearance="outline">
                <mat-label>Recipient</mat-label>
                <input
                  matInput
                  type="email"
                  [(ngModel)]="testEmailAddress"
                  name="admin_test_email_address"
                  placeholder="admin@example.com"
                />
              </mat-form-field>
              <button
                mat-raised-button
                color="primary"
                type="submit"
                class="admin-pill-button"
                [disabled]="sendingTestEmail"
                data-testid="admin-send-test-email"
              >
                <mat-icon aria-hidden="true">{{ sendingTestEmail ? "hourglass_top" : "send" }}</mat-icon>
                <span>{{ sendingTestEmail ? "Sending" : "Send test" }}</span>
              </button>
            </form>
          </article>
        </section>

        <section
          *ngSwitchCase="'security'"
          class="admin-section"
          aria-labelledby="admin-security-heading"
          data-testid="admin-security-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Security</p>
              <h2 id="admin-security-heading">Security events</h2>
              <p>Recent sign-in, account, and sensitive-action events.</p>
            </div>
            <form class="admin-search-bar admin-security-filters" (ngSubmit)="loadSecurityReport()">
              <mat-form-field appearance="outline">
                <mat-label>Window</mat-label>
                <mat-select [(ngModel)]="securityDays" name="admin_security_days">
                  <mat-option [value]="7">7 days</mat-option>
                  <mat-option [value]="30">30 days</mat-option>
                  <mat-option [value]="90">90 days</mat-option>
                  <mat-option [value]="180">180 days</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Outcome</mat-label>
                <mat-select [(ngModel)]="securityOutcome" name="admin_security_outcome">
                  <mat-option value="">All</mat-option>
                  <mat-option value="success">Success</mat-option>
                  <mat-option value="rejected">Rejected</mat-option>
                  <mat-option value="failure">Failure</mat-option>
                </mat-select>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Event type</mat-label>
                <input
                  matInput
                  [(ngModel)]="securityEventType"
                  name="admin_security_event_type"
                  placeholder="login_failed"
                />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>User ID</mat-label>
                <input
                  matInput
                  type="number"
                  min="1"
                  [(ngModel)]="securityUserId"
                  name="admin_security_user_id"
                />
              </mat-form-field>
              <button
                mat-stroked-button
                type="submit"
                class="admin-pill-button"
                data-testid="admin-security-refresh"
              >
                <mat-icon aria-hidden="true">refresh</mat-icon>
                <span>Refresh</span>
              </button>
              <button
                mat-button
                type="button"
                class="admin-pill-button"
                (click)="clearSecurityFilters()"
                data-testid="admin-security-clear"
              >
                <mat-icon aria-hidden="true">filter_alt_off</mat-icon>
                <span>Clear</span>
              </button>
            </form>
          </div>

          <ng-container *ngIf="securityReport as report; else securityLoading">
            <p class="admin-empty" *ngIf="!report.available">
              {{ report.message || "Security audit events are not available." }}
            </p>

            <div class="admin-metric-grid admin-security-metrics" *ngIf="report.available">
              <article class="admin-metric-card">
                <mat-icon aria-hidden="true">shield</mat-icon>
                <strong>{{ report.total_events }}</strong>
                <span>Total events</span>
              </article>
              <article
                class="admin-metric-card"
                *ngFor="let outcome of report.events_by_outcome.slice(0, 3)"
              >
                <mat-icon aria-hidden="true">{{ securityOutcomeIcon(outcome.outcome) }}</mat-icon>
                <strong>{{ outcome.count }}</strong>
                <span>{{ formatEnumLabel(outcome.outcome) }}</span>
              </article>
            </div>

            <div class="admin-chip-list admin-security-type-list" *ngIf="report.events_by_type.length">
              <span
                class="admin-chip"
                *ngFor="let eventType of report.events_by_type.slice(0, 8)"
              >
                {{ formatEnumLabel(eventType.event_type) }} · {{ eventType.count }}
              </span>
            </div>

            <div class="admin-audit-list" *ngIf="report.recent_events.length; else securityEmpty">
              <article
                class="admin-audit-row"
                *ngFor="let event of report.recent_events"
                [attr.data-testid]="'admin-security-event-' + event.id"
              >
                <span class="admin-readiness-icon admin-security-icon" aria-hidden="true">
                  <mat-icon>{{ securityOutcomeIcon(event.outcome) }}</mat-icon>
                </span>
                <div class="admin-audit-main">
                  <div class="admin-audit-title-row">
                    <h3>{{ formatEnumLabel(event.event_type) }}</h3>
                    <span
                      class="admin-chip admin-chip--strong"
                      [class.admin-chip--danger]="event.outcome !== 'success'"
                    >
                      {{ formatEnumLabel(event.outcome) }}
                    </span>
                  </div>
                  <span class="admin-muted">
                    {{ formatDateTime(event.created_at) }} · User {{ event.user_id || "n/a" }}
                  </span>
                </div>
                <div class="admin-audit-meta">
                  {{ metadataSummary(event.metadata) || "No metadata" }}
                </div>
              </article>
            </div>
          </ng-container>

          <ng-template #securityLoading>
            <p class="admin-empty">Security events have not loaded yet.</p>
          </ng-template>

          <ng-template #securityEmpty>
            <p class="admin-empty">No security events match this filter.</p>
          </ng-template>
        </section>

        <section
          *ngSwitchCase="'stripe'"
          class="admin-section"
          aria-labelledby="admin-stripe-heading"
          data-testid="admin-stripe-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Stripe sync</p>
              <h2 id="admin-stripe-heading">Webhook events</h2>
            </div>
          </div>

          <div class="admin-stripe-summary">
            <span class="admin-status-pill">{{ overview?.stripe?.configured ? "configured" : "not configured" }}</span>
            <span>Checkout tiers: {{ overview?.stripe?.checkout_tiers?.join(", ") || "none" }}</span>
          </div>

          <div class="admin-table-wrap">
            <table class="admin-user-table">
              <thead>
                <tr>
                  <th scope="col">Event</th>
                  <th scope="col">User</th>
                  <th scope="col">Processed</th>
                  <th scope="col">Object</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let event of overview?.recent_billing_events || []">
                  <td>
                    <strong>{{ event.event_type }}</strong>
                    <span class="admin-muted">{{ event.provider_event_id }}</span>
                  </td>
                  <td>{{ event.user_id || "n/a" }}</td>
                  <td>{{ event.processed_at }}</td>
                  <td>{{ event.metadata?.["object_id"] || event.metadata?.["subscription"] || "n/a" }}</td>
                </tr>
              </tbody>
            </table>
            <p class="admin-empty" *ngIf="!overview?.recent_billing_events?.length">No Stripe events recorded yet.</p>
          </div>
        </section>

        <section
          *ngSwitchCase="'audit'"
          class="admin-section"
          aria-labelledby="admin-audit-heading"
          data-testid="admin-audit-section"
        >
          <div class="admin-section-heading">
            <div>
              <p class="admin-eyebrow">Audit</p>
              <h2 id="admin-audit-heading">Admin activity</h2>
              <p>Recent privileged changes across users, plans, and announcements.</p>
            </div>
            <button
              mat-stroked-button
              type="button"
              class="admin-pill-button"
              (click)="loadAuditEvents()"
              data-testid="admin-audit-refresh"
            >
              <mat-icon aria-hidden="true">refresh</mat-icon>
              <span>Refresh</span>
            </button>
          </div>

          <div class="admin-audit-list" *ngIf="auditEvents.length; else auditEmpty">
            <article
              class="admin-audit-row"
              *ngFor="let event of auditEvents"
              [attr.data-testid]="'admin-audit-event-' + event.id"
            >
              <span class="admin-readiness-icon admin-audit-icon" aria-hidden="true">
                <mat-icon>{{ auditIcon(event.action) }}</mat-icon>
              </span>
              <div class="admin-audit-main">
                <div class="admin-audit-title-row">
                  <h3>{{ formatEnumLabel(event.action) }}</h3>
                  <span class="admin-chip admin-chip--strong">{{ formatEnumLabel(event.outcome) }}</span>
                </div>
                <p>
                  <strong>{{ event.actor_name }}</strong>
                  <ng-container *ngIf="event.target_name">
                    changed <strong>{{ event.target_name }}</strong>
                  </ng-container>
                  <ng-container *ngIf="!event.target_name">
                    changed {{ formatEnumLabel(event.resource_type) }}
                  </ng-container>
                </p>
                <span class="admin-muted">
                  {{ formatDateTime(event.created_at) }} · {{ formatEnumLabel(event.resource_type) }}
                  <ng-container *ngIf="event.resource_id"> · {{ event.resource_id }}</ng-container>
                </span>
              </div>
              <div class="admin-audit-meta" *ngIf="auditSummary(event)">
                {{ auditSummary(event) }}
              </div>
            </article>
          </div>

          <ng-template #auditEmpty>
            <p class="admin-empty">No admin activity recorded yet.</p>
          </ng-template>
        </section>
      </ng-container>
    </section>
  `,
  styles: [`
    .admin-console {
      display: grid;
      gap: var(--spacing-md);
      max-width: 1280px;
      margin: 0 auto;
    }

    .admin-back-link,
    .admin-hero,
    .admin-section,
    .admin-feedback,
    .admin-section-tab,
    .admin-metric-card,
    .admin-plan-card,
    .admin-announcement-form,
    .admin-announcement-row,
    .admin-audit-row,
    .admin-readiness-card,
    .admin-readiness-check {
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-elevated);
      box-shadow: 0 14px 34px var(--colour-shadow-soft);
    }

	    .admin-back-link,
	    .admin-pill-button,
	    .admin-section-tab,
	    .admin-status-pill,
	    .admin-chip,
	    .admin-schedule-chip,
	    .admin-stripe-pill {
	      display: inline-flex;
	      align-items: center;
      justify-content: center;
      gap: var(--spacing-xs);
      border-radius: var(--radius-pill);
    }

    .admin-back-link {
      justify-self: start;
      min-height: 44px;
      padding: 0 var(--spacing-sm);
      color: var(--colour-text-primary);
      font-weight: 900;
      text-decoration: none;
    }

    .admin-back-link mat-icon,
    .admin-pill-button mat-icon,
    .admin-section-tab mat-icon,
    .admin-stripe-pill mat-icon,
    .admin-feedback mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
      line-height: 20px;
    }

    .admin-hero {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-md);
      padding: var(--spacing-lg);
      border-radius: var(--radius-lg);
      background:
        radial-gradient(circle at 10% 0%, color-mix(in srgb, var(--colour-primary) 24%, transparent), transparent 34%),
        radial-gradient(circle at 94% 18%, color-mix(in srgb, var(--colour-accent) 18%, transparent), transparent 30%),
        var(--colour-surface-muted);
    }

    .admin-eyebrow,
    .admin-hero h1,
    .admin-hero p,
    .admin-section-heading h2,
    .admin-section-heading p,
    .admin-metric-card strong,
    .admin-metric-card span,
    .admin-plan-card h3,
    .admin-plan-card p,
    .admin-announcement-row h3,
    .admin-announcement-row p,
    .admin-audit-row h3,
    .admin-audit-row p,
    .admin-feedback {
      margin: 0;
    }

    .admin-eyebrow {
      color: var(--colour-primary);
      font-size: 0.78rem;
      font-weight: 950;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .admin-hero h1 {
      font-size: clamp(2.2rem, 5vw, 4rem);
      line-height: 0.95;
    }

    .admin-hero p,
    .admin-muted,
    .admin-section-heading p,
    .admin-plan-card p,
    .admin-announcement-row p {
      color: var(--colour-text-secondary);
      font-weight: 760;
    }

    .admin-stripe-pill,
    .admin-status-pill {
      min-height: 36px;
      padding: 0 var(--spacing-sm);
      background: var(--colour-surface-muted);
      color: var(--colour-text-secondary);
      border: 1px solid var(--colour-border);
      font-weight: 900;
      white-space: nowrap;
    }

    .admin-stripe-pill--ready {
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
      border-color: color-mix(in srgb, var(--colour-success-text) 55%, var(--colour-border));
    }

    .admin-section-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: var(--spacing-xs);
    }

    .admin-section-tab {
      min-height: 48px;
      padding: 0 var(--spacing-md);
      color: var(--colour-text-primary);
      font-weight: 900;
      cursor: pointer;
    }

    .admin-section-tab.is-active {
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      border-color: color-mix(in srgb, var(--colour-primary) 55%, var(--colour-border));
      box-shadow: 0 10px 24px var(--colour-primary-shadow);
    }

    .admin-section,
    .admin-feedback {
      display: grid;
      gap: var(--spacing-md);
      padding: var(--spacing-lg);
      border-radius: var(--radius-lg);
    }

    .admin-feedback {
      grid-template-columns: auto 1fr;
      align-items: center;
      width: fit-content;
      padding: var(--spacing-sm) var(--spacing-md);
      border-radius: var(--radius-pill);
      font-weight: 850;
    }

    .admin-feedback.is-error {
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
      border-color: color-mix(in srgb, var(--colour-danger-text) 55%, var(--colour-border));
    }

    .admin-feedback.is-success {
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
      border-color: color-mix(in srgb, var(--colour-success-text) 55%, var(--colour-border));
    }

    .admin-section-heading {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-md);
    }

    .admin-metric-grid,
    .admin-plan-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: var(--spacing-md);
    }

    .admin-metric-card {
      display: grid;
      gap: var(--spacing-xs);
      padding: var(--spacing-md);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-metric-card mat-icon {
      color: var(--colour-primary);
    }

    .admin-metric-card strong {
      font-size: 2.2rem;
      line-height: 1;
    }

    .admin-search-bar,
    .admin-inline-controls,
    .admin-card-actions,
    .admin-row-actions,
    .admin-stripe-summary {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
      flex-wrap: wrap;
    }

    .admin-operations-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: var(--spacing-md);
    }

    .admin-readiness-card {
      display: grid;
      grid-template-columns: auto 1fr;
      align-items: center;
      gap: var(--spacing-sm);
      min-width: 0;
      padding: var(--spacing-md);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-readiness-card h3,
    .admin-readiness-check h3,
    .admin-readiness-check p {
      margin: 0;
    }

    .admin-readiness-card h3 {
      margin-top: 0.15rem;
      font-size: 1.1rem;
    }

    .admin-readiness-icon,
    .admin-readiness-status {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-xs);
      border-radius: var(--radius-pill);
    }

    .admin-readiness-icon {
      width: 44px;
      height: 44px;
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
    }

    .admin-readiness-icon mat-icon,
    .admin-readiness-status mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
      line-height: 20px;
    }

    .admin-readiness-check-list {
      display: grid;
      gap: var(--spacing-sm);
    }

    .admin-audit-list {
      display: grid;
      gap: var(--spacing-sm);
    }

    .admin-audit-row {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) minmax(10rem, 18rem);
      align-items: center;
      gap: var(--spacing-sm);
      padding: var(--spacing-md);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-audit-main {
      display: grid;
      gap: 0.25rem;
      min-width: 0;
    }

    .admin-audit-title-row {
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
      flex-wrap: wrap;
    }

    .admin-audit-meta {
      color: var(--colour-text-secondary);
      font-size: 0.88rem;
      font-weight: 800;
      text-align: right;
    }

    .admin-audit-icon {
      background: color-mix(in srgb, var(--colour-primary) 26%, var(--colour-surface-elevated));
    }

    .admin-readiness-check {
      display: grid;
      grid-template-columns: max-content 1fr;
      align-items: start;
      gap: var(--spacing-sm);
      padding: var(--spacing-md);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-readiness-check p {
      color: var(--colour-text-secondary);
      font-weight: 760;
    }

    .admin-operation-action-card {
      display: grid;
      grid-template-columns: auto minmax(0, 1fr) minmax(18rem, 30rem);
      align-items: center;
      gap: var(--spacing-md);
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
      box-shadow: 0 14px 34px var(--colour-shadow-soft);
    }

    .admin-operation-action-card h3,
    .admin-operation-action-card p {
      margin: 0;
    }

    .admin-operation-action-card p:not(.admin-eyebrow) {
      color: var(--colour-text-secondary);
      font-weight: 760;
    }

    .admin-operation-action-form {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: var(--spacing-sm);
      min-width: 0;
    }

    .admin-operation-action-form mat-form-field {
      flex: 1 1 14rem;
      min-width: 12rem;
    }

    .admin-readiness-status {
      min-height: 34px;
      padding: 0 var(--spacing-sm);
      border: 1px solid var(--colour-border);
      font-size: 0.8rem;
      font-weight: 950;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .admin-readiness-status--ok {
      background: var(--colour-success-bg);
      border-color: color-mix(in srgb, var(--colour-success-text) 55%, var(--colour-border));
      color: var(--colour-success-text);
    }

    .admin-readiness-status--warning {
      background: var(--colour-warning-bg);
      border-color: color-mix(in srgb, var(--colour-warning-text) 55%, var(--colour-border));
      color: var(--colour-warning-text);
    }

    .admin-readiness-status--blocked {
      background: var(--colour-danger-bg);
      border-color: color-mix(in srgb, var(--colour-danger-text) 55%, var(--colour-border));
      color: var(--colour-danger-text);
    }

    .admin-search-bar mat-form-field {
      width: min(28rem, 52vw);
    }

    .admin-security-filters mat-form-field {
      width: min(11rem, 42vw);
    }

    .admin-security-metrics {
      grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    }

    .admin-security-type-list {
      padding: var(--spacing-xs);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-security-icon {
      background: color-mix(in srgb, var(--colour-accent) 26%, var(--colour-surface-elevated));
    }

	    .admin-table-wrap {
	      overflow-x: hidden;
	      border: 1px solid var(--colour-border);
	      border-radius: var(--radius-lg);
	      background: var(--colour-surface-muted);
	    }

	    .admin-user-table {
	      width: 100%;
	      border-collapse: collapse;
	      table-layout: fixed;
	    }

    .admin-user-table th,
    .admin-user-table td {
      padding: var(--spacing-xs) var(--spacing-sm);
      border-bottom: 1px solid var(--colour-border);
      text-align: left;
      vertical-align: middle;
    }

	    .admin-user-table th {
	      color: var(--colour-text-secondary);
      font-size: 0.82rem;
      letter-spacing: 0.08em;
	      text-transform: uppercase;
	    }

		    .admin-user-table th:nth-child(1),
		    .admin-user-table td:nth-child(1) {
		      width: 24%;
		    }

	    .admin-user-table th:nth-child(2),
	    .admin-user-table td:nth-child(2) {
	      width: 13%;
	    }

		    .admin-user-table th:nth-child(3),
		    .admin-user-table td:nth-child(3) {
		      width: 20%;
		    }

	    .admin-user-table th:nth-child(4),
	    .admin-user-table td:nth-child(4) {
	      width: 13%;
	    }

		    .admin-user-table th:nth-child(5),
		    .admin-user-table td:nth-child(5) {
		      width: 20%;
		    }

	    .admin-user-table th:nth-child(6),
	    .admin-user-table td:nth-child(6) {
	      width: 10%;
	    }

    .admin-user-cell {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }

	    .admin-user-cell div,
	    .admin-user-table td {
	      min-width: 0;
	    }

    .admin-user-cell strong,
    .admin-user-cell span,
    .admin-user-table td > span,
	    .admin-muted {
	      display: block;
	    }

	    .admin-user-cell strong,
	    .admin-user-cell span,
	    .admin-user-table td > span:not(.admin-chip),
	    .admin-muted {
	      max-width: 100%;
	      overflow: hidden;
	      text-overflow: ellipsis;
	      white-space: nowrap;
	    }

		    .admin-avatar {
      display: grid;
      place-items: center;
      flex: 0 0 40px;
      width: 40px;
      height: 40px;
      min-width: 40px;
      max-width: 40px;
      padding: 0;
      border-radius: var(--radius-pill);
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      font-size: 1rem;
		      font-weight: 950;
		      line-height: 1;
      text-align: center;
		    }

    .admin-metric-card mat-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 40px;
      width: 40px;
      height: 40px;
      min-width: 40px;
      max-width: 40px;
      border-radius: var(--radius-pill);
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      font-size: 1rem;
		      font-weight: 950;
		      line-height: 1;
      text-align: center;
	    }

      .admin-chip-list {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.375rem;
        min-width: 0;
      }

      .admin-chip-list--access {
        align-content: flex-start;
      }

	    .admin-chip {
	      min-height: 30px;
	      max-width: 9rem;
	      margin: 0;
	      padding: 0 var(--spacing-xs);
	      border: 1px solid var(--colour-border);
	      background: var(--colour-surface-elevated);
	      color: var(--colour-text-primary);
	      font-size: 0.82rem;
	      font-weight: 900;
	      vertical-align: middle;
	      overflow: hidden;
	      text-overflow: ellipsis;
	      white-space: nowrap;
        line-height: 1;
	    }

	    .admin-chip--strong {
	      background: var(--colour-control-selected);
	      color: var(--colour-control-selected-text);
	      border-color: color-mix(in srgb, var(--colour-primary) 55%, var(--colour-border));
	    }

		    .admin-chip--muted {
		      color: var(--colour-text-secondary);
		    }

      .admin-chip--danger {
        border-color: color-mix(in srgb, var(--colour-danger-text) 60%, var(--colour-border));
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
      }

    .admin-inline-controls mat-form-field {
      width: 9.5rem;
    }

	    .admin-pill-button {
	      min-height: 44px;
	      font-weight: 900;
	    }

      .admin-icon-actions {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 0.35rem;
      }

      .admin-icon-pill {
        display: inline-grid;
        place-items: center;
        width: 40px;
        height: 40px;
        min-width: 40px;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-elevated);
        color: var(--colour-text-primary);
      }

      .admin-icon-pill--save:not(:disabled) {
        border-color: color-mix(in srgb, var(--colour-success-text) 58%, var(--colour-border));
        background: var(--colour-success-bg);
        color: var(--colour-success-text);
      }

      .admin-icon-pill--danger {
        border-color: color-mix(in srgb, var(--colour-danger-text) 58%, var(--colour-border));
        background: var(--colour-danger-bg);
        color: var(--colour-danger-text);
      }

      .admin-icon-pill:disabled {
        opacity: 0.5;
      }

    .admin-plan-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .admin-plan-card,
    .admin-announcement-form,
    .admin-announcement-row {
      display: grid;
      gap: var(--spacing-md);
      padding: var(--spacing-md);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-plan-card header,
    .admin-announcement-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--spacing-md);
    }

    .admin-plan-price-row,
    .admin-quota-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--spacing-sm);
    }

    .admin-quota-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .admin-full-width {
      width: 100%;
    }

    .admin-card-actions {
      justify-content: flex-end;
    }

    .admin-danger-action {
      color: var(--colour-danger-text);
    }

	    .admin-announcement-list {
	      display: grid;
	      gap: var(--spacing-sm);
	    }

	    .admin-status-control {
	      display: flex;
	      align-items: center;
	      gap: var(--spacing-xs);
	      min-height: 56px;
	      padding: var(--spacing-xs);
	      border: 1px solid var(--colour-border);
	      border-radius: var(--radius-lg);
	      background: var(--colour-surface-elevated);
	      flex-wrap: wrap;
	    }

	    .admin-status-label,
	    .admin-field-hint {
	      color: var(--colour-text-secondary);
	      font-size: 0.82rem;
	      font-weight: 850;
	    }

	    .admin-field-hint {
	      flex-basis: 100%;
	      margin: 0;
	    }

	    .admin-schedule-row {
	      display: flex;
	      align-items: center;
	      gap: var(--spacing-xs);
	      flex-wrap: wrap;
	    }

	    .admin-schedule-chip {
	      min-height: 36px;
	      padding: 0 var(--spacing-sm);
	      border: 1px solid var(--colour-border);
	      background: var(--colour-surface-elevated);
	      color: var(--colour-text-primary);
	      font-weight: 900;
	      cursor: pointer;
	    }

	    .admin-schedule-chip.is-active,
	    .admin-schedule-chip:hover,
	    .admin-schedule-chip:focus-visible {
	      background: var(--colour-control-selected);
	      color: var(--colour-control-selected-text);
	      border-color: color-mix(in srgb, var(--colour-primary) 55%, var(--colour-border));
	    }

    .admin-empty {
      margin: 0;
      padding: var(--spacing-md);
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    @media (max-width: 980px) {
      .admin-hero,
      .admin-section-heading,
      .admin-plan-card header,
      .admin-announcement-row {
        align-items: stretch;
        flex-direction: column;
      }

      .admin-audit-row {
        grid-template-columns: 1fr;
      }

      .admin-operation-action-card {
        grid-template-columns: 1fr;
      }

      .admin-operation-action-form {
        align-items: stretch;
        flex-direction: column;
      }

      .admin-audit-meta {
        text-align: left;
      }

      .admin-metric-grid,
      .admin-operations-grid,
      .admin-plan-grid,
      .admin-plan-price-row,
      .admin-quota-grid {
        grid-template-columns: 1fr;
      }

      .admin-search-bar mat-form-field {
        width: 100%;
      }
    }
  `],
})
export class AdminPlanCatalogueComponent implements OnInit {
  private readonly adminService = inject(AdminService);
  private readonly announcementService = inject(AnnouncementService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly sections: Array<{ id: AdminSection; label: string; icon: string }> = [
    { id: "overview", label: "Overview", icon: "dashboard" },
    { id: "users", label: "Users & access", icon: "group" },
    { id: "billing", label: "Plans & quotas", icon: "payments" },
    { id: "announcements", label: "Announcements", icon: "campaign" },
    { id: "operations", label: "Operations", icon: "monitor_heart" },
    { id: "security", label: "Security", icon: "shield_lock" },
    { id: "audit", label: "Audit", icon: "manage_history" },
    { id: "stripe", label: "Stripe sync", icon: "sync" },
  ];
  readonly activeSection = signal<AdminSection>("overview");
  readonly tierOptions: BillingTier[] = [
    "free",
    "personal",
    "plus",
    "therapeutic",
    "complimentary",
    "lifetime",
    "administrator",
  ];
  readonly statusOptions = ["active", "inactive", "past_due", "cancelled", "expired"];
  readonly quotaFields = QUOTA_FIELDS;
  readonly timezoneOptions = [
    "Europe/London",
    "UTC",
    "Europe/Dublin",
    "Europe/Paris",
    "America/New_York",
    "America/Los_Angeles",
    "Australia/Sydney",
  ];
  readonly minDateTimeLocal = this.toDateTimeLocal(new Date().toISOString());

  overview: AdminOverview | null = null;
  operations: AdminOperationsReadiness | null = null;
  securityReport: AdminSecurityAuditReport | null = null;
  users: EditableAdminUser[] = [];
  plans: EditablePlan[] = [];
  announcements: AdminAnnouncement[] = [];
  auditEvents: AdminAuditEvent[] = [];
  userSearch = "";
  usersLoading = false;
  savingUserId: number | null = null;
  savingTier: BillingTier | null = null;
  savingAnnouncement = false;
  sendingTestEmail = false;
  errorMessage = "";
  successMessage = "";
  testEmailAddress = "";
  securityDays = 30;
  securityOutcome = "";
  securityEventType = "";
  securityUserId: number | null = null;
  announcementDraft: AnnouncementDraft = this.emptyAnnouncementDraft();

  ngOnInit(): void {
    this.route.queryParamMap.subscribe((params) => {
      const requested = String(params.get("section") || "overview") as AdminSection;
      this.activeSection.set(
        this.sections.some((section) => section.id === requested) ? requested : "overview",
      );
    });
    this.loadAll();
  }

  setSection(section: AdminSection): void {
    this.activeSection.set(section);
    this.clearFeedback();
    if (section === "operations" && !this.operations) {
      this.loadOperations();
    }
    if (section === "security" && !this.securityReport) {
      this.loadSecurityReport();
    }
    if (section === "audit" && !this.auditEvents.length) {
      this.loadAuditEvents();
    }
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { section },
      queryParamsHandling: "merge",
    });
  }

  loadAll(): void {
    this.errorMessage = "";
    this.loadOverview();
    this.loadOperations(true);
    this.loadUsers();
    this.loadPlans();
    this.loadAnnouncements();
    this.loadSecurityReport(true);
    this.loadAuditEvents(true);
  }

  loadOverview(silent = false): void {
    this.adminService.getOverview().subscribe({
      next: (overview) => (this.overview = overview),
      error: (error) => {
        if (!silent) {
          this.showError(error, "Admin overview could not be loaded.");
        }
      },
    });
  }

  loadOperations(silent = false): void {
    this.adminService.getOperations().subscribe({
      next: (operations) => (this.operations = operations),
      error: (error) => {
        if (!silent) {
          this.showError(error, "Operations readiness could not be loaded.");
        }
      },
    });
  }

  loadUsers(): void {
    this.usersLoading = true;
    this.adminService.getUsers({ search: this.userSearch }).subscribe({
      next: (response) => {
        this.users = response.users.map((user) => ({
          ...user,
          selectedTier: user.entitlement?.tier || "free",
          selectedStatus: user.entitlement?.status || "active",
          savedFeedback: false,
        }));
        this.usersLoading = false;
      },
      error: (error) => {
        this.usersLoading = false;
        this.showError(error, "Users could not be loaded.");
      },
    });
  }

  loadPlans(): void {
    this.adminService.getPlans().subscribe({
      next: (response) => {
        this.plans = response.plans.map((plan) => this.toEditablePlan(plan));
      },
      error: (error) => this.showError(error, "Plans could not be loaded."),
    });
  }

  loadAnnouncements(silent = false): void {
    this.adminService.getAnnouncements().subscribe({
      next: (response) => (this.announcements = response.announcements),
      error: (error) => {
        if (!silent) {
          this.showError(error, "Announcements could not be loaded.");
        }
      },
    });
  }

  loadAuditEvents(silent = false): void {
    this.adminService.getAuditEvents().subscribe({
      next: (response) => (this.auditEvents = response.events),
      error: (error) => {
        if (!silent) {
          this.showError(error, "Admin activity could not be loaded.");
        }
      },
    });
  }

  loadSecurityReport(silent = false): void {
    this.adminService
      .getSecurityAuditReport({
        days: this.securityDays,
        limit: 50,
        outcome: this.securityOutcome,
        event_type: this.securityEventType,
        user_id: this.securityUserId || undefined,
      })
      .subscribe({
        next: (report) => (this.securityReport = report),
        error: (error) => {
          if (!silent) {
            this.showError(error, "Security events could not be loaded.");
          }
        },
      });
  }

  clearSecurityFilters(): void {
    this.securityDays = 30;
    this.securityOutcome = "";
    this.securityEventType = "";
    this.securityUserId = null;
    this.loadSecurityReport();
  }

  sendTestEmail(): void {
    this.sendingTestEmail = true;
    this.clearFeedback();
    this.adminService.sendTestEmail(this.testEmailAddress).subscribe({
      next: (response) => {
        this.sendingTestEmail = false;
        this.testEmailAddress = response.to_address;
        this.successMessage = `Test email sent to ${response.to_address}.`;
        this.loadAuditEvents(true);
      },
      error: (error) => {
        this.sendingTestEmail = false;
        this.showError(error, "Test email could not be sent.");
        this.loadAuditEvents(true);
      },
    });
  }

  saveUserEntitlement(user: EditableAdminUser): void {
    if (!this.isUserEntitlementDirty(user)) return;
    this.savingUserId = user.id;
    this.clearFeedback();
    this.adminService
      .updateUserEntitlement(user.id, {
        tier: user.selectedTier,
        status: user.selectedStatus,
      })
      .subscribe({
        next: (response) => {
          const updated = {
            ...response.user,
            selectedTier: response.user.entitlement?.tier || "free",
            selectedStatus: response.user.entitlement?.status || "active",
            savedFeedback: true,
          };
          this.users = this.users.map((item) =>
            item.id === updated.id ? updated : item,
          );
          this.savingUserId = null;
          this.successMessage = `${this.getUserDisplayName(updated)} access updated.`;
          this.loadOverview(true);
          this.loadAuditEvents(true);
          window.setTimeout(() => this.clearUserSavedFeedback(updated.id), 1800);
        },
        error: (error) => {
          this.savingUserId = null;
          this.showError(error, "User access could not be saved.");
        },
      });
  }

  toggleUserRestriction(user: EditableAdminUser): void {
    this.savingUserId = user.id;
    this.clearFeedback();
    const nextStatus = this.isUserRestricted(user) ? "active" : "restricted";
    this.adminService
      .updateUserAccess(user.id, { account_status: nextStatus })
      .subscribe({
        next: (response) => {
          const updated = {
            ...response.user,
            selectedTier: response.user.entitlement?.tier || "free",
            selectedStatus: response.user.entitlement?.status || "active",
            savedFeedback: true,
          };
          this.users = this.users.map((item) =>
            item.id === updated.id ? updated : item,
          );
          this.savingUserId = null;
          this.successMessage = `${this.getUserDisplayName(updated)} ${nextStatus === "restricted" ? "restricted" : "restored"}.`;
          this.loadOverview(true);
          this.loadAuditEvents(true);
          window.setTimeout(() => this.clearUserSavedFeedback(updated.id), 1800);
        },
        error: (error) => {
          this.savingUserId = null;
          this.showError(error, "User access status could not be saved.");
        },
      });
  }

  savePlan(plan: EditablePlan): void {
    this.savingTier = plan.tier;
    this.clearFeedback();
    const quotas = { ...(plan.quotas || {}) };
    for (const field of QUOTA_FIELDS) {
      const value = plan.quotaFields[field.key];
      quotas[field.key] = value === null || value === undefined || Number.isNaN(Number(value))
        ? null
        : Number(value);
    }
    this.adminService
      .updatePlan(plan.tier, {
        public_name: plan.public_name,
        strapline: plan.strapline,
        description: plan.description,
        monthly_price_gbp_pence: Number(plan.monthly_price_gbp_pence),
        annual_price_gbp_pence: Number(plan.annual_price_gbp_pence),
        annual_discount_percent: Number(plan.annual_discount_percent),
        features: plan.featuresText.split(/\n+/).map((item) => item.trim()).filter(Boolean),
        quotas,
        is_public: Boolean(plan.is_public),
        is_paid: Number(plan.monthly_price_gbp_pence) > 0,
        sort_order: Number(plan.sort_order),
      })
      .subscribe({
        next: (response) => {
          const updated = this.toEditablePlan(response.plan);
          this.plans = this.plans.map((item) =>
            item.tier === updated.tier ? updated : item,
          );
          this.savingTier = null;
          this.successMessage = `${updated.public_name} updated.`;
          this.loadAll();
        },
        error: (error) => {
          this.savingTier = null;
          this.showError(error, "Plan could not be saved.");
        },
      });
  }

  saveAnnouncement(): void {
    this.savingAnnouncement = true;
    this.clearFeedback();
    const payload = this.toAnnouncementPayload();
    const request = this.announcementDraft.id
      ? this.adminService.updateAnnouncement(this.announcementDraft.id, payload)
      : this.adminService.createAnnouncement(payload);
    request.subscribe({
      next: () => {
        this.savingAnnouncement = false;
	        this.successMessage = this.announcementDraft.id
	          ? "Announcement updated."
	          : "Announcement created.";
	        this.resetAnnouncementDraft();
	        this.announcementService.refresh().subscribe({ error: () => undefined });
	        this.loadAnnouncements(true);
	        this.loadOverview(true);
	        this.loadAuditEvents(true);
	      },
      error: (error) => {
        this.savingAnnouncement = false;
        this.showError(error, "Announcement could not be saved.");
      },
    });
  }

  archiveAnnouncement(announcement: AdminAnnouncement): void {
    this.adminService.archiveAnnouncement(announcement.id).subscribe({
      next: () => {
        this.successMessage = "Announcement archived.";
        this.loadAnnouncements(true);
        this.loadOverview(true);
        this.loadAuditEvents(true);
      },
      error: (error) => this.showError(error, "Announcement could not be archived."),
    });
  }

  editAnnouncement(announcement: AdminAnnouncement): void {
    const firstTarget = announcement.targets[0] || { type: "all", value: null };
    this.announcementDraft = {
      id: announcement.id,
      title: announcement.title,
      message: announcement.message,
      severity: announcement.severity,
      placement: announcement.placement,
	      status: announcement.status,
	      starts_at: this.toDateTimeLocal(announcement.starts_at),
	      ends_at: this.toDateTimeLocal(announcement.ends_at),
	      timezone: announcement.timezone || "Europe/London",
	      dismissible: announcement.dismissible,
      targetType: firstTarget.type,
      targetValues:
        firstTarget.type === "all"
          ? ""
          : announcement.targets.map((target) => target.value).filter(Boolean).join(", "),
    };
    this.setSection("announcements");
  }

	  resetAnnouncementDraft(): void {
	    this.announcementDraft = this.emptyAnnouncementDraft();
	  }

	  publishNow(): void {
	    const now = new Date();
	    const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
	    this.announcementDraft.status = "published";
	    this.announcementDraft.starts_at = this.toDateTimeLocal(now.toISOString());
	    this.announcementDraft.ends_at = this.toDateTimeLocal(tomorrow.toISOString());
	  }

	  scheduleForHours(startsInHours: number, durationHours: number): void {
	    const starts = new Date(Date.now() + startsInHours * 60 * 60 * 1000);
	    const ends = new Date(starts.getTime() + durationHours * 60 * 60 * 1000);
	    this.announcementDraft.status = "published";
	    this.announcementDraft.starts_at = this.toDateTimeLocal(starts.toISOString());
	    this.announcementDraft.ends_at = this.toDateTimeLocal(ends.toISOString());
	  }

  resetPlan(plan: EditablePlan): void {
    const original = JSON.parse(plan.snapshot) as BillingPlan;
    const updated = this.toEditablePlan(original);
    this.plans = this.plans.map((item) =>
      item.tier === plan.tier ? updated : item,
    );
  }

  isPlanDirty(plan: EditablePlan): boolean {
    return this.planSnapshot(plan) !== plan.snapshot;
  }

  getUserDisplayName(user: AdminBillingUser): string {
    return (
      user.display_name ||
      [user.first_name, user.last_name].filter(Boolean).join(" ") ||
      user.username ||
      `User ${user.id}`
    );
  }

  getUserInitial(user: AdminBillingUser): string {
    return this.getUserDisplayName(user).trim().charAt(0).toUpperCase() || "?";
  }

  isUserEntitlementDirty(user: EditableAdminUser): boolean {
    return (
      user.selectedTier !== (user.entitlement?.tier || "free") ||
      user.selectedStatus !== (user.entitlement?.status || "active")
    );
  }

  isUserRestricted(user: AdminBillingUser): boolean {
    return String(user.account_status || "active").toLowerCase() === "restricted";
  }

  private clearUserSavedFeedback(userId: number): void {
    this.users = this.users.map((user) =>
      user.id === userId ? { ...user, savedFeedback: false } : user,
    );
  }

  getAuthMethods(user: AdminBillingUser): string {
    return user.auth_methods?.length ? user.auth_methods.join(", ") : "unknown";
  }

  formatEnumLabel(value?: string | null): string {
    const cleaned = String(value || "")
      .trim()
      .replace(/[_-]+/g, " ");
    if (!cleaned) {
      return "Unknown";
    }
    return cleaned
      .split(/\s+/)
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(" ");
  }

  readinessIcon(status?: string): string {
    switch (status) {
      case "ok":
        return "check_circle";
      case "blocked":
        return "error";
      default:
        return "warning";
    }
  }

  readinessStatusClass(status?: string): string {
    return `admin-readiness-status--${status || "warning"}`;
  }

  auditIcon(action?: string): string {
    if (action?.includes("announcement")) return "campaign";
    if (action?.includes("plan")) return "payments";
    if (action?.includes("access")) return "lock_person";
    return "admin_panel_settings";
  }

  securityOutcomeIcon(outcome?: string): string {
    switch (outcome) {
      case "success":
        return "check_circle";
      case "rejected":
        return "block";
      case "failure":
        return "error";
      default:
        return "shield";
    }
  }

  auditSummary(event: AdminAuditEvent): string {
    const metadata = event.metadata || {};
    const newTier = metadata["new_tier"];
    const newStatus = metadata["new_status"];
    const accountStatus = metadata["new_account_status"];
    const publicName = metadata["public_name"];
    const announcementStatus = metadata["status"];
    if (newTier || newStatus) {
      return [newTier, newStatus].filter(Boolean).map((item) => this.formatEnumLabel(String(item))).join(" · ");
    }
    if (accountStatus) {
      return this.formatEnumLabel(String(accountStatus));
    }
    if (publicName) {
      return String(publicName);
    }
    if (announcementStatus) {
      return this.formatEnumLabel(String(announcementStatus));
    }
    return "";
  }

  quotaText(used?: number, limit?: number | null): string {
    if (used === undefined) return "0";
    if (limit === null || limit === undefined) return `${used}/∞`;
    return `${used}/${limit}`;
  }

  metadataSummary(metadata?: Record<string, unknown>): string {
    const entries = Object.entries(metadata || {})
      .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
      .slice(0, 3);
    if (!entries.length) {
      return "";
    }
    return entries
      .map(([key, value]) => `${this.formatEnumLabel(key)}: ${String(value)}`)
      .join(" · ");
  }

	  targetSummary(announcement: AdminAnnouncement): string {
	    if (!announcement.targets?.length || announcement.targets[0].type === "all") {
	      return "All users";
	    }
	    const type = announcement.targets[0].type === "tier" ? "Tiers" : "Users";
	    return `${type}: ${announcement.targets
        .map((target) => this.formatEnumLabel(target.value))
        .join(", ")}`;
	  }

	  scheduleSummary(announcement: AdminAnnouncement): string {
	    const starts = announcement.starts_at
	      ? this.formatDateTime(announcement.starts_at)
	      : "now";
	    const ends = announcement.ends_at
	      ? this.formatDateTime(announcement.ends_at)
	      : "no expiry";
	    return `${starts} to ${ends} (${announcement.timezone || "Europe/London"})`;
	  }

  private toEditablePlan(plan: BillingPlan): EditablePlan {
    const quotaFields: Record<string, number | null> = {};
    for (const field of QUOTA_FIELDS) {
      quotaFields[field.key] = plan.quotas?.[field.key] ?? null;
    }
    const editable: EditablePlan = {
      ...plan,
      featuresText: (plan.features || []).join("\n"),
      quotaFields,
      snapshot: "",
    };
    editable.snapshot = this.planSnapshot(editable);
    return editable;
  }

  private planSnapshot(plan: EditablePlan | BillingPlan): string {
    const quotas = { ...(plan.quotas || {}) };
    const fields = "quotaFields" in plan ? plan.quotaFields : {};
    for (const field of QUOTA_FIELDS) {
      quotas[field.key] = fields[field.key] ?? quotas[field.key] ?? null;
    }
    const features =
      "featuresText" in plan
        ? plan.featuresText.split(/\n+/).map((item) => item.trim()).filter(Boolean)
        : plan.features || [];
    return JSON.stringify({
      tier: plan.tier,
      public_name: plan.public_name,
      strapline: plan.strapline,
      description: plan.description,
      monthly_price_gbp_pence: Number(plan.monthly_price_gbp_pence),
      annual_price_gbp_pence: Number(plan.annual_price_gbp_pence),
      annual_discount_percent: Number(plan.annual_discount_percent),
      quotas,
      features,
      is_public: Boolean(plan.is_public),
      is_paid: Boolean(plan.is_paid),
      sort_order: Number(plan.sort_order),
    });
  }

  private emptyAnnouncementDraft(): AnnouncementDraft {
    return {
      title: "",
      message: "",
      severity: "info",
      placement: "banner",
	      status: "draft",
	      starts_at: "",
	      ends_at: "",
	      timezone: "Europe/London",
	      dismissible: true,
      targetType: "all",
      targetValues: "",
    };
  }

  private toAnnouncementPayload(): AdminAnnouncementPayload {
    const targetValues = this.announcementDraft.targetValues
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    return {
      title: this.announcementDraft.title,
      message: this.announcementDraft.message,
      severity: this.announcementDraft.severity,
      placement: this.announcementDraft.placement,
	      status: this.announcementDraft.status,
	      starts_at: this.fromDateTimeLocal(this.announcementDraft.starts_at),
	      ends_at: this.fromDateTimeLocal(this.announcementDraft.ends_at),
	      timezone: this.announcementDraft.timezone,
	      dismissible: this.announcementDraft.dismissible,
      targets:
        this.announcementDraft.targetType === "all"
          ? [{ type: "all", value: null }]
          : targetValues.map((value) => ({
              type: this.announcementDraft.targetType,
              value,
            })),
    };
  }

	  private toDateTimeLocal(value?: string | null): string {
	    if (!value) return "";
	    const date = new Date(value);
	    if (Number.isNaN(date.getTime())) return value.slice(0, 16);
	    const pad = (part: number) => String(part).padStart(2, "0");
	    return [
	      date.getFullYear(),
	      pad(date.getMonth() + 1),
	      pad(date.getDate()),
	    ].join("-") + `T${pad(date.getHours())}:${pad(date.getMinutes())}`;
	  }

	  private fromDateTimeLocal(value: string): string | null {
	    return value ? value : null;
	  }

	  formatDateTime(value?: string | null): string {
	    if (!value) return "";
	    const date = new Date(value);
	    if (Number.isNaN(date.getTime())) return value;
	    return new Intl.DateTimeFormat(undefined, {
	      dateStyle: "medium",
	      timeStyle: "short",
	    }).format(date);
	  }

  private clearFeedback(): void {
    this.errorMessage = "";
    this.successMessage = "";
  }

  private showError(error: unknown, fallback: string): void {
    const errorLike = error as { error?: { error?: string } };
    this.errorMessage = errorLike?.error?.error || fallback;
    this.successMessage = "";
  }
}
