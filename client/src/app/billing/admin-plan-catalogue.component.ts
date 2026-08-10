import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatSelectModule } from "@angular/material/select";
import {
  AdminBillingUser,
  BillingPlan,
  BillingService,
  BillingTier,
} from "../core/services/billing.service";

interface EditablePlan extends BillingPlan {
  featuresText: string;
  quotasText: string;
}

interface EditableAdminUser extends AdminBillingUser {
  selectedTier: BillingTier;
  selectedStatus: string;
}

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
  ],
  template: `
    <section class="admin-plans-page" data-testid="admin-plans-page">
      <a routerLink="/profile" class="admin-back-link">
        <mat-icon aria-hidden="true">arrow_back</mat-icon>
        <span>Back to Account</span>
      </a>

      <header class="admin-plans-hero">
        <p class="admin-eyebrow">Administrator</p>
        <h1>Billing console</h1>
        <p>Manage account access, pricing copy, quotas, and plan visibility.</p>
      </header>

      <p class="admin-status" *ngIf="isLoading" role="status">Loading plan matrix...</p>
      <p class="admin-status is-error" *ngIf="errorMessage" role="alert">{{ errorMessage }}</p>
      <p class="admin-status is-success" *ngIf="successMessage" role="status">{{ successMessage }}</p>

      <section class="admin-access-card" aria-labelledby="admin-user-access-heading">
        <div class="admin-section-header">
          <div>
            <p class="admin-eyebrow">User access</p>
            <h2 id="admin-user-access-heading">Manual account tiers</h2>
          </div>
          <form class="admin-user-search" (ngSubmit)="loadUsers()">
            <mat-form-field appearance="outline">
              <mat-label>Search users</mat-label>
              <input
                matInput
                [(ngModel)]="userSearch"
                name="user_search"
                placeholder="Email, username, or name"
              />
            </mat-form-field>
            <button
              mat-stroked-button
              type="submit"
              class="admin-pill-action"
              [disabled]="usersLoading"
            >
              <mat-icon aria-hidden="true">{{ usersLoading ? "hourglass_top" : "search" }}</mat-icon>
              <span>{{ usersLoading ? "Searching..." : "Search" }}</span>
            </button>
          </form>
        </div>

        <p class="admin-user-note">
          Manual tiers are owner overrides. Stripe subscriptions still manage paid self-service accounts.
        </p>

        <div class="admin-users-list" *ngIf="!usersLoading; else loadingUsers">
          <article
            class="admin-user-row"
            *ngFor="let user of users"
            [attr.data-testid]="'admin-user-' + user.id"
          >
            <div class="admin-user-identity">
              <div class="admin-user-avatar" aria-hidden="true">
                {{ getUserInitial(user) }}
              </div>
              <div>
                <h3>{{ getUserDisplayName(user) }}</h3>
                <p>{{ user.email || user.username }} · {{ getEntitlementLabel(user) }}</p>
              </div>
            </div>

            <div class="admin-user-controls">
              <mat-form-field appearance="outline">
                <mat-label>Tier</mat-label>
                <mat-select [(ngModel)]="user.selectedTier" [name]="'user_' + user.id + '_tier'">
                  <mat-option *ngFor="let tier of tierOptions" [value]="tier">
                    {{ tier }}
                  </mat-option>
                </mat-select>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Status</mat-label>
                <mat-select [(ngModel)]="user.selectedStatus" [name]="'user_' + user.id + '_status'">
                  <mat-option *ngFor="let status of statusOptions" [value]="status">
                    {{ status }}
                  </mat-option>
                </mat-select>
              </mat-form-field>

              <button
                mat-raised-button
                color="primary"
                type="button"
                class="admin-pill-action"
                [disabled]="savingUserId === user.id"
                (click)="saveUserEntitlement(user)"
              >
                <mat-icon aria-hidden="true">
                  {{ savingUserId === user.id ? "hourglass_top" : "save" }}
                </mat-icon>
                <span>{{ savingUserId === user.id ? "Saving..." : "Save access" }}</span>
              </button>
            </div>
          </article>

          <p class="admin-empty-state" *ngIf="!users.length">No users found.</p>
        </div>

        <ng-template #loadingUsers>
          <p class="admin-status" role="status">Loading users...</p>
        </ng-template>
      </section>

      <div class="admin-plan-list" *ngIf="!isLoading">
        <article class="admin-plan-card" *ngFor="let plan of plans" [attr.data-testid]="'admin-plan-' + plan.tier">
          <header class="admin-plan-card-header">
            <div>
              <p class="admin-tier">{{ plan.tier }}</p>
              <h2>{{ plan.public_name }}</h2>
            </div>
            <mat-checkbox [(ngModel)]="plan.is_public" [name]="plan.tier + '_public'">
              Public
            </mat-checkbox>
          </header>

          <div class="admin-plan-grid">
            <mat-form-field appearance="outline">
              <mat-label>Public name</mat-label>
              <input matInput [(ngModel)]="plan.public_name" [name]="plan.tier + '_name'" maxlength="40" />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Strapline</mat-label>
              <input matInput [(ngModel)]="plan.strapline" [name]="plan.tier + '_strapline'" maxlength="90" />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Monthly price, pence</mat-label>
              <input matInput type="number" [(ngModel)]="plan.monthly_price_gbp_pence" [name]="plan.tier + '_monthly'" />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Annual price, pence</mat-label>
              <input matInput type="number" [(ngModel)]="plan.annual_price_gbp_pence" [name]="plan.tier + '_annual'" />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Annual discount %</mat-label>
              <input matInput type="number" [(ngModel)]="plan.annual_discount_percent" [name]="plan.tier + '_discount'" />
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Sort order</mat-label>
              <input matInput type="number" [(ngModel)]="plan.sort_order" [name]="plan.tier + '_sort'" />
            </mat-form-field>
          </div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Description</mat-label>
            <textarea matInput rows="2" [(ngModel)]="plan.description" [name]="plan.tier + '_description'"></textarea>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Features, one per line</mat-label>
            <textarea matInput rows="4" [(ngModel)]="plan.featuresText" [name]="plan.tier + '_features'"></textarea>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Quotas JSON</mat-label>
            <textarea matInput rows="5" [(ngModel)]="plan.quotasText" [name]="plan.tier + '_quotas'"></textarea>
          </mat-form-field>

          <div class="admin-plan-actions">
            <button
              mat-raised-button
              color="primary"
              type="button"
              class="admin-save-plan"
              [disabled]="savingTier === plan.tier"
              (click)="savePlan(plan)"
            >
              <mat-icon aria-hidden="true">{{ savingTier === plan.tier ? "hourglass_top" : "save" }}</mat-icon>
              <span>{{ savingTier === plan.tier ? "Saving..." : "Save plan" }}</span>
            </button>
          </div>
        </article>
      </div>
    </section>
  `,
  styles: [`
    .admin-plans-page {
      display: grid;
      gap: var(--spacing-md);
      max-width: 1180px;
      margin: 0 auto;
    }

    .admin-back-link,
    .admin-status,
    .admin-access-card,
    .admin-plan-card,
    .admin-plans-hero {
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-elevated);
      box-shadow: 0 14px 34px var(--colour-shadow-soft);
    }

    .admin-back-link,
    .admin-pill-action,
    .admin-save-plan {
      display: inline-flex;
      align-items: center;
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
    .admin-pill-action mat-icon,
    .admin-save-plan mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    .admin-plans-hero {
      display: grid;
      gap: var(--spacing-xs);
      padding: var(--spacing-lg);
      border-radius: var(--radius-lg);
      background:
        radial-gradient(circle at 10% 0%, color-mix(in srgb, var(--colour-primary) 20%, transparent), transparent 34%),
        var(--colour-surface-muted);
    }

    .admin-eyebrow,
    .admin-plans-hero h1,
    .admin-plans-hero p,
    .admin-plan-card h2,
    .admin-tier,
    .admin-status {
      margin: 0;
    }

    .admin-eyebrow,
    .admin-tier {
      color: var(--colour-primary);
      font-size: 0.8rem;
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .admin-plans-hero h1 {
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 1;
    }

    .admin-plans-hero p {
      color: var(--colour-text-secondary);
      font-weight: 760;
    }

    .admin-status {
      width: fit-content;
      padding: var(--spacing-sm) var(--spacing-md);
      border-radius: var(--radius-pill);
      color: var(--colour-text-secondary);
      font-weight: 850;
    }

    .admin-status.is-error {
      border-color: var(--colour-danger-border);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    .admin-status.is-success {
      border-color: var(--colour-success-text);
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
    }

    .admin-access-card {
      display: grid;
      gap: var(--spacing-md);
      padding: var(--spacing-lg);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-elevated);
    }

    .admin-section-header,
    .admin-user-row,
    .admin-user-controls,
    .admin-user-identity,
    .admin-user-search {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
    }

    .admin-section-header,
    .admin-user-row {
      justify-content: space-between;
    }

    .admin-section-header h2,
    .admin-user-identity h3,
    .admin-user-identity p,
    .admin-user-note,
    .admin-empty-state {
      margin: 0;
    }

    .admin-user-note,
    .admin-user-identity p,
    .admin-empty-state {
      color: var(--colour-text-secondary);
      font-weight: 750;
    }

    .admin-user-search {
      align-items: flex-start;
    }

    .admin-user-search mat-form-field {
      width: min(24rem, 52vw);
    }

    .admin-users-list {
      display: grid;
      gap: var(--spacing-sm);
    }

    .admin-user-row {
      padding: var(--spacing-sm);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-muted);
    }

    .admin-user-avatar {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 44px;
      height: 44px;
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, var(--colour-primary) 16%, var(--colour-surface));
      color: var(--colour-primary);
      font-weight: 950;
      text-transform: uppercase;
    }

    .admin-user-controls mat-form-field {
      width: 10rem;
    }

    .admin-pill-action {
      min-height: 44px;
      border-radius: var(--radius-pill);
      font-weight: 900;
    }

    .admin-plan-list {
      display: grid;
      gap: var(--spacing-md);
    }

    .admin-plan-card {
      display: grid;
      gap: var(--spacing-md);
      padding: var(--spacing-lg);
      border-radius: var(--radius-lg);
    }

    .admin-plan-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-md);
    }

    .admin-plan-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--spacing-md);
    }

    .full-width {
      width: 100%;
    }

    .admin-plan-actions {
      display: flex;
      justify-content: flex-end;
    }

    .admin-save-plan {
      min-height: 48px;
      font-weight: 900;
    }

    @media (max-width: 920px) {
      .admin-plan-grid {
        grid-template-columns: 1fr;
      }

      .admin-section-header,
      .admin-user-row,
      .admin-user-controls,
      .admin-user-search {
        align-items: stretch;
        flex-direction: column;
      }

      .admin-user-search mat-form-field,
      .admin-user-controls mat-form-field {
        width: 100%;
      }
    }
  `],
})
export class AdminPlanCatalogueComponent implements OnInit {
  private readonly billingService = inject(BillingService);

  plans: EditablePlan[] = [];
  users: EditableAdminUser[] = [];
  userSearch = "";
  isLoading = true;
  usersLoading = true;
  savingTier: BillingTier | null = null;
  savingUserId: number | null = null;
  errorMessage = "";
  successMessage = "";
  readonly tierOptions: BillingTier[] = [
    "free",
    "personal",
    "plus",
    "complimentary",
    "lifetime",
    "administrator",
  ];
  readonly statusOptions = ["active", "inactive", "past_due", "cancelled", "expired"];

  ngOnInit(): void {
    this.loadUsers();
    this.billingService.getAdminPlans().subscribe({
      next: (response) => {
        this.plans = response.plans.map((plan) => this.toEditablePlan(plan));
        this.isLoading = false;
      },
      error: (error) => {
        this.errorMessage =
          error?.error?.error || "Plan matrix could not be loaded.";
        this.isLoading = false;
      },
    });
  }

  loadUsers(): void {
    this.usersLoading = true;
    this.errorMessage = "";
    this.billingService.getAdminUsers(this.userSearch).subscribe({
      next: (response) => {
        this.users = response.users.map((user) => this.toEditableUser(user));
        this.usersLoading = false;
      },
      error: (error) => {
        this.usersLoading = false;
        this.errorMessage = error?.error?.error || "Users could not be loaded.";
      },
    });
  }

  saveUserEntitlement(user: EditableAdminUser): void {
    this.savingUserId = user.id;
    this.errorMessage = "";
    this.successMessage = "";
    this.billingService.updateAdminUserEntitlement(user.id, {
      tier: user.selectedTier,
      status: user.selectedStatus,
    }).subscribe({
      next: (response) => {
        const updated = this.toEditableUser(response.user);
        this.users = this.users.map((item) =>
          item.id === updated.id ? updated : item,
        );
        this.savingUserId = null;
        this.successMessage = `${this.getUserDisplayName(updated)} access updated.`;
      },
      error: (error) => {
        this.savingUserId = null;
        this.errorMessage = error?.error?.error || "User access could not be saved.";
      },
    });
  }

  savePlan(plan: EditablePlan): void {
    let quotas: Record<string, number | null>;
    try {
      quotas = JSON.parse(plan.quotasText) as Record<string, number | null>;
    } catch {
      this.errorMessage = "Quotas must be valid JSON.";
      this.successMessage = "";
      return;
    }

    this.savingTier = plan.tier;
    this.errorMessage = "";
    this.successMessage = "";
    this.billingService.updateAdminPlan(plan.tier, {
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
    }).subscribe({
      next: (response) => {
        const updated = this.toEditablePlan(response.plan);
        this.plans = this.plans.map((item) =>
          item.tier === updated.tier ? updated : item,
        );
        this.savingTier = null;
        this.successMessage = `${updated.public_name} updated.`;
      },
      error: (error) => {
        this.savingTier = null;
        this.errorMessage = error?.error?.error || "Plan could not be saved.";
      },
    });
  }

  private toEditablePlan(plan: BillingPlan): EditablePlan {
    return {
      ...plan,
      featuresText: (plan.features || []).join("\n"),
      quotasText: JSON.stringify(plan.quotas || {}, null, 2),
    };
  }

  private toEditableUser(user: AdminBillingUser): EditableAdminUser {
    return {
      ...user,
      selectedTier: user.entitlement?.tier || "free",
      selectedStatus: user.entitlement?.status || "active",
    };
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
    return this.getUserDisplayName(user).trim().charAt(0) || "?";
  }

  getEntitlementLabel(user: AdminBillingUser): string {
    const tier = user.entitlement?.tier || "free";
    const source = user.entitlement?.source || "system";
    const status = user.entitlement?.status || "active";
    return `${tier} · ${source} · ${status}`;
  }
}
