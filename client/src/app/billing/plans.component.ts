import { CommonModule } from "@angular/common";
import { Component, OnInit, inject } from "@angular/core";
import { RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import {
  BillingPlan,
  BillingService,
  BillingStatus,
  CheckoutTier,
} from "../core/services/billing.service";

type BillingPeriod = "monthly" | "annual";

@Component({
  selector: "app-plans",
  standalone: true,
  imports: [CommonModule, RouterLink, MatButtonModule, MatIconModule],
  template: `
    <section class="plans-page" data-testid="plans-page">
      <a routerLink="/profile" class="plans-back-link">
        <mat-icon aria-hidden="true">arrow_back</mat-icon>
        <span>Back to Account</span>
      </a>

      <header class="plans-hero">
        <p class="plans-eyebrow">Plans</p>
        <h1>Choose how much AI support you need</h1>
      </header>

      <div
        class="plans-period-toggle"
        role="group"
        aria-label="Choose billing period"
        data-testid="plans-billing-period-toggle"
      >
        <button
          type="button"
          class="plans-period-option"
          [class.is-active]="selectedBillingPeriod === 'monthly'"
          [attr.aria-pressed]="selectedBillingPeriod === 'monthly'"
          (click)="setBillingPeriod('monthly')"
        >
          Monthly
        </button>
        <button
          type="button"
          class="plans-period-option"
          [class.is-active]="selectedBillingPeriod === 'annual'"
          [attr.aria-pressed]="selectedBillingPeriod === 'annual'"
          (click)="setBillingPeriod('annual')"
        >
          Annual
          <span class="plans-period-saving" *ngIf="bestAnnualDiscountPercent > 0">
            Save {{ bestAnnualDiscountPercent }}%
          </span>
        </button>
      </div>

      <div class="plans-status" *ngIf="isLoading" role="status">
        <mat-icon aria-hidden="true">hourglass_top</mat-icon>
        <span>Loading plans...</span>
      </div>

      <p class="plans-status is-error" *ngIf="errorMessage" role="alert">
        {{ errorMessage }}
      </p>

      <div
        class="plans-grid"
        *ngIf="!isLoading && plans.length"
        [class.is-period-monthly]="selectedBillingPeriod === 'monthly'"
        [class.is-period-annual]="selectedBillingPeriod === 'annual'"
        aria-label="OpenMynd plans"
      >
        <article
          class="plans-card"
          *ngFor="let plan of plans"
          [class.is-current]="plan.tier === currentTier"
          [class.is-free]="plan.tier === 'free'"
          [class.is-plus]="plan.tier === 'personal'"
          [class.is-premier]="plan.tier === 'plus'"
          [attr.data-testid]="'plans-card-' + plan.tier"
        >
          <div class="plans-card-header">
            <div class="plans-card-icon" aria-hidden="true">
              <mat-icon>{{ getPlanIcon(plan) }}</mat-icon>
            </div>
            <span class="current-pill" *ngIf="plan.tier === currentTier">Current</span>
          </div>

          <h2>{{ plan.public_name }}</h2>
          <p class="plans-strapline">{{ plan.strapline }}</p>

          <div class="plans-price" *ngIf="plan.monthly_price_gbp_pence > 0; else freePrice">
            <strong>{{ getPlanPriceLabel(plan) }}</strong>
            <span>/{{ getPlanBillingUnit(plan) }}</span>
            <small *ngIf="getPlanSavingLabel(plan)">
              {{ getPlanSavingLabel(plan) }}
            </small>
          </div>
          <ng-template #freePrice>
            <div class="plans-price">
              <strong>Free</strong>
              <span>No card required</span>
            </div>
          </ng-template>

          <ul class="plans-features">
            <li *ngFor="let feature of plan.features">
              <mat-icon aria-hidden="true">check_circle</mat-icon>
              <span>{{ feature }}</span>
            </li>
          </ul>

          <button
            *ngIf="isCheckoutTier(plan.tier); else freeAction"
            mat-raised-button
            color="primary"
            type="button"
            class="plans-action"
            [disabled]="!canStartCheckout(plan.tier)"
            (click)="startCheckout(plan.tier)"
          >
            <mat-icon aria-hidden="true">
              {{ busyTier === plan.tier ? "hourglass_top" : "workspace_premium" }}
            </mat-icon>
            <span>{{ getCheckoutLabel(plan) }}</span>
          </button>
          <ng-template #freeAction>
            <span class="plans-free-note" *ngIf="plan.tier === 'free'">
              Free remains available by default.
            </span>
          </ng-template>
        </article>
      </div>
    </section>
  `,
  styles: [`
    .plans-page {
      display: grid;
      gap: var(--spacing-md);
      max-width: 1120px;
      margin: 0 auto;
    }

    .plans-back-link,
    .plans-status,
    .plans-card {
      border: 1px solid var(--colour-border);
      background: var(--colour-surface-elevated);
      box-shadow: 0 14px 34px var(--colour-shadow-soft);
    }

    .plans-back-link,
    .plans-status,
    .plans-action {
      display: inline-flex;
      align-items: center;
      gap: var(--spacing-xs);
      border-radius: var(--radius-pill);
    }

    .plans-back-link {
      justify-self: start;
      min-height: 44px;
      padding: 0 var(--spacing-sm);
      color: var(--colour-text-primary);
      font-weight: 900;
      text-decoration: none;
    }

    .plans-back-link mat-icon,
    .plans-status mat-icon,
    .plans-action mat-icon,
    .plans-features mat-icon {
      width: 20px;
      height: 20px;
      font-size: 20px;
    }

    .plans-hero {
      display: grid;
      gap: var(--spacing-xs);
      padding: clamp(1.5rem, 4vw, 2.5rem);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background:
        radial-gradient(circle at 16% 0%, color-mix(in srgb, var(--colour-primary) 24%, transparent), transparent 34%),
        radial-gradient(circle at 84% 12%, color-mix(in srgb, var(--colour-accent) 14%, transparent), transparent 30%),
        var(--colour-surface-muted);
    }

    .plans-eyebrow,
    .plans-hero h1,
    .plans-card h2,
    .plans-card p,
    .plans-price,
    .plans-free-note {
      margin: 0;
    }

    .plans-eyebrow {
      color: var(--colour-primary);
      font-size: 0.84rem;
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .plans-hero h1 {
      max-width: 760px;
      font-size: clamp(2rem, 4.5vw, 3.4rem);
      line-height: 1;
      letter-spacing: -0.055em;
    }

    .plans-status {
      width: fit-content;
      padding: var(--spacing-sm) var(--spacing-md);
      color: var(--colour-text-secondary);
      font-weight: 850;
    }

    .plans-period-toggle {
      display: inline-flex;
      justify-self: center;
      width: fit-content;
      padding: 4px;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      box-shadow: 0 12px 26px var(--colour-shadow-soft);
    }

    .plans-period-option {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-xs);
      min-height: 44px;
      padding: 0 var(--spacing-md);
      border: 0;
      border-radius: var(--radius-pill);
      background: transparent;
      color: var(--colour-text-secondary);
      cursor: pointer;
      font: inherit;
      font-weight: 900;
      transition:
        background 180ms ease,
        color 180ms ease,
        box-shadow 180ms ease;
    }

    .plans-period-option.is-active {
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      box-shadow: 0 10px 22px var(--colour-shadow-soft);
    }

    .plans-period-option:focus-visible {
      outline: var(--focus-outline);
      outline-offset: var(--focus-offset);
    }

    .plans-period-saving {
      padding: 0.12rem 0.42rem;
      border-radius: var(--radius-pill);
      background: color-mix(in srgb, #fbbf24 24%, var(--colour-surface-elevated));
      color: #2f1a00;
      font-size: 0.76rem;
      font-weight: 950;
      box-shadow: inset 0 0 0 1px color-mix(in srgb, #f59e0b 34%, transparent);
    }

    :host-context(html[data-theme="dark"]) .plans-period-saving {
      background: color-mix(in srgb, #fbbf24 36%, #2a1a05);
      color: #fff7d6;
    }

    .plans-status.is-error {
      border-color: var(--colour-danger-border);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }

    .plans-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: var(--spacing-md);
    }

    .plans-card {
      display: grid;
      align-content: start;
      gap: var(--spacing-md);
      padding: var(--spacing-lg);
      border-radius: var(--radius-lg);
      background:
        radial-gradient(circle at 12% 0%, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 10%, transparent), transparent 38%),
        linear-gradient(145deg, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 5%, transparent), transparent 58%),
        var(--colour-surface-elevated);
    }

    .plans-card.is-free {
      --plan-accent: var(--colour-success-text);
    }

    .plans-card.is-plus {
      --plan-accent: #f59e0b;
    }

    .plans-card.is-premier {
      --plan-accent: #a78bfa;
    }

    .plans-card.is-current {
      border-color: var(--plan-accent, var(--colour-primary));
      background:
        radial-gradient(circle at 12% 0%, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 30%, transparent), transparent 38%),
        linear-gradient(145deg, color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 16%, transparent), transparent 58%),
        var(--colour-surface-elevated);
      box-shadow:
        0 0 0 4px color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 38%, transparent),
        0 0 42px color-mix(in srgb, var(--plan-accent, var(--colour-primary)) 28%, transparent),
        0 20px 46px var(--colour-shadow-medium);
    }

    .plans-card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-sm);
    }

    .plans-card-icon {
      display: grid;
      width: 52px;
      height: 52px;
      place-items: center;
      border-radius: var(--radius-pill);
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
    }

    .plans-card-icon mat-icon {
      width: 28px;
      height: 28px;
      font-size: 28px;
    }

    .current-pill {
      padding: 0.24rem 0.7rem;
      border-radius: var(--radius-pill);
      background: var(--colour-success-bg);
      color: var(--colour-success-text);
      font-size: 0.8rem;
      font-weight: 900;
    }

    .plans-strapline,
    .plans-free-note {
      color: var(--colour-text-secondary);
      font-weight: 750;
    }

    .plans-price {
      display: grid;
      gap: 0.15rem;
    }

    .plans-grid.is-period-monthly .plans-card {
      animation: plans-card-period-flip-monthly 520ms cubic-bezier(0.2, 0, 0, 1);
    }

    .plans-grid.is-period-annual .plans-card {
      animation: plans-card-period-flip-annual 520ms cubic-bezier(0.2, 0, 0, 1);
    }

    @keyframes plans-card-period-flip-monthly {
      0% {
        opacity: 0.72;
        transform: perspective(900px) rotateY(-8deg) translateY(8px) scale(0.985);
      }
      100% {
        opacity: 1;
        transform: perspective(900px) rotateY(0deg) translateY(0) scale(1);
      }
    }

    @keyframes plans-card-period-flip-annual {
      0% {
        opacity: 0.72;
        transform: perspective(900px) rotateY(8deg) translateY(8px) scale(0.985);
      }
      100% {
        opacity: 1;
        transform: perspective(900px) rotateY(0deg) translateY(0) scale(1);
      }
    }

    .plans-price strong {
      font-size: 2rem;
      letter-spacing: -0.04em;
    }

    .plans-price span,
    .plans-price small {
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    .plans-features {
      display: grid;
      gap: var(--spacing-xs);
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .plans-features li {
      display: flex;
      align-items: flex-start;
      gap: var(--spacing-xs);
      color: var(--colour-text-primary);
      font-weight: 750;
      line-height: 1.45;
    }

    .plans-features mat-icon {
      flex: 0 0 20px;
      color: var(--colour-success-text);
    }

    .plans-action {
      min-height: 48px;
      justify-content: center;
      font-weight: 900;
      --mdc-protected-button-container-color: var(--colour-control-selected);
      --mdc-protected-button-label-text-color: var(--colour-control-selected-text);
      --mat-protected-button-state-layer-color: var(--colour-control-selected-text);
    }

    @media (prefers-reduced-motion: reduce) {
      .plans-period-option {
        transition: none;
      }

      .plans-grid.is-period-monthly .plans-card,
      .plans-grid.is-period-annual .plans-card {
        animation: none;
      }
    }

    @media (max-width: 900px) {
      .plans-grid {
        grid-template-columns: 1fr;
      }
    }
  `],
})
export class PlansComponent implements OnInit {
  private readonly billingService = inject(BillingService);

  billingStatus: BillingStatus | null = null;
  plans: BillingPlan[] = [];
  isLoading = true;
  errorMessage = "";
  busyTier: CheckoutTier | null = null;
  selectedBillingPeriod: BillingPeriod = "monthly";

  get currentTier(): string {
    return this.billingStatus?.entitlement?.tier || "free";
  }

  get bestAnnualDiscountPercent(): number {
    return this.plans.reduce(
      (best, plan) => Math.max(best, plan.annual_discount_percent || 0),
      0,
    );
  }

  ngOnInit(): void {
    this.billingService.getStatus().subscribe({
      next: (status) => {
        this.billingStatus = status;
        this.plans = status.plans || [];
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = "Plans could not be loaded.";
        this.isLoading = false;
      },
    });
  }

  formatCurrency(pence: number): string {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
      maximumFractionDigits: pence % 100 === 0 ? 0 : 2,
    }).format(pence / 100);
  }

  getPlanPriceLabel(plan: BillingPlan): string {
    const price =
      this.selectedBillingPeriod === "annual" && plan.annual_price_gbp_pence
        ? plan.annual_price_gbp_pence
        : plan.monthly_price_gbp_pence;
    return this.formatCurrency(price);
  }

  getPlanSavingLabel(plan: BillingPlan): string {
    if (
      this.selectedBillingPeriod !== "annual" ||
      !plan.annual_discount_percent ||
      !plan.annual_price_gbp_pence
    ) {
      return "";
    }
    return `Save ${plan.annual_discount_percent}% annually`;
  }

  getPlanBillingUnit(plan: BillingPlan): "month" | "year" {
    return this.selectedBillingPeriod === "annual" && plan.annual_price_gbp_pence
      ? "year"
      : "month";
  }

  getPlanIcon(plan: BillingPlan): string {
    if (plan.tier === "free") return "spa";
    if (plan.tier === "plus") return "workspace_premium";
    return "auto_awesome";
  }

  isCheckoutTier(tier: string): tier is CheckoutTier {
    return tier === "personal" || tier === "plus";
  }

  canStartCheckout(tier: CheckoutTier): boolean {
    return Boolean(
      this.billingStatus?.stripe_configured &&
        this.billingStatus.checkout_tiers.includes(tier) &&
        (this.billingStatus.checkout_periods?.[tier] || []).includes(this.selectedBillingPeriod) &&
        this.busyTier === null,
    );
  }

  setBillingPeriod(period: BillingPeriod): void {
    this.selectedBillingPeriod = period;
  }

  getCheckoutLabel(plan: BillingPlan): string {
    if (this.busyTier === plan.tier) return "Opening...";
    if (plan.tier === this.currentTier) return "Current plan";
    return `Upgrade to ${plan.public_name}`;
  }

  startCheckout(tier: CheckoutTier): void {
    if (!this.canStartCheckout(tier)) return;
    this.busyTier = tier;
    this.errorMessage = "";
    this.billingService.startCheckout(tier, this.selectedBillingPeriod).subscribe({
      next: (response) => {
        window.location.href = response.url;
      },
      error: (error) => {
        this.errorMessage = error?.error?.error || "Checkout could not be started.";
        this.busyTier = null;
      },
    });
  }
}
