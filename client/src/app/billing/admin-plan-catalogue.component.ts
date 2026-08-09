import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCheckboxModule } from "@angular/material/checkbox";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import {
  BillingPlan,
  BillingService,
  BillingTier,
} from "../core/services/billing.service";

interface EditablePlan extends BillingPlan {
  featuresText: string;
  quotasText: string;
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
  ],
  template: `
    <section class="admin-plans-page" data-testid="admin-plans-page">
      <a routerLink="/profile" class="admin-back-link">
        <mat-icon aria-hidden="true">arrow_back</mat-icon>
        <span>Back to Account</span>
      </a>

      <header class="admin-plans-hero">
        <p class="admin-eyebrow">Administrator</p>
        <h1>Plan matrix</h1>
        <p>Changes are reflected anywhere OpenMynd shows plans or enforces usage limits.</p>
      </header>

      <p class="admin-status" *ngIf="isLoading" role="status">Loading plan matrix...</p>
      <p class="admin-status is-error" *ngIf="errorMessage" role="alert">{{ errorMessage }}</p>
      <p class="admin-status is-success" *ngIf="successMessage" role="status">{{ successMessage }}</p>

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
    .admin-plan-card,
    .admin-plans-hero {
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-elevated);
      box-shadow: 0 14px 34px var(--colour-shadow-soft);
    }

    .admin-back-link,
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
    }
  `],
})
export class AdminPlanCatalogueComponent implements OnInit {
  private readonly billingService = inject(BillingService);

  plans: EditablePlan[] = [];
  isLoading = true;
  savingTier: BillingTier | null = null;
  errorMessage = "";
  successMessage = "";

  ngOnInit(): void {
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
}
