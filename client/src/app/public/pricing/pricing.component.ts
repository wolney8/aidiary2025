import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { RouterLink } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";

interface PricingPlan {
  name: string;
  icon: string;
  summary: string;
  features: string[];
  label: string;
}

const PLANS: PricingPlan[] = [
  {
    name: "Free",
    icon: "spa",
    label: "Entry tier",
    summary: "Private journalling with limited AI analysis.",
    features: [
      "Diary, dream, thought record, and important day entries",
      "Basic import, export, and dashboard views",
      "Monthly AI analysis allowance",
    ],
  },
  {
    name: "Personal",
    icon: "auto_awesome",
    label: "Core plan",
    summary: "Higher AI usage for regular reflection.",
    features: [
      "Larger monthly AI analysis allowance",
      "Richer attachment and dashboard workflows as they launch",
      "Stripe-hosted subscription management",
    ],
  },
  {
    name: "Plus",
    icon: "workspace_premium",
    label: "Power user",
    summary: "More headroom for advanced use.",
    features: [
      "Highest standard monthly AI analysis allowance",
      "More room for OCR, transcription, and advanced analytics",
      "Priority path for future export/import portability features",
    ],
  },
];

@Component({
  selector: "app-pricing",
  standalone: true,
  imports: [CommonModule, RouterLink, MatIconModule],
  template: `
    <section class="pricing-page" data-testid="pricing-page">
      <a routerLink="/dashboard" class="pricing-back-link">
        <mat-icon aria-hidden="true">arrow_back</mat-icon>
        Back to app
      </a>

      <header class="pricing-hero">
        <p class="pricing-eyebrow">Pricing</p>
        <h1>OpenMynd plans</h1>
        <p>
          Public pricing is finalised before launch. Plan access is managed through
          OpenMynd entitlements and Stripe-hosted billing.
        </p>
      </header>

      <div class="pricing-grid" aria-label="OpenMynd plans">
        <article class="pricing-card" *ngFor="let plan of plans">
          <div class="pricing-card__icon" aria-hidden="true">
            <mat-icon>{{ plan.icon }}</mat-icon>
          </div>
          <p class="pricing-card__label">{{ plan.label }}</p>
          <h2>{{ plan.name }}</h2>
          <p>{{ plan.summary }}</p>
          <ul>
            <li *ngFor="let feature of plan.features">
              <mat-icon aria-hidden="true">check_circle</mat-icon>
              <span>{{ feature }}</span>
            </li>
          </ul>
        </article>
      </div>

      <section class="pricing-note" aria-labelledby="pricing-note-heading">
        <mat-icon aria-hidden="true">info</mat-icon>
        <div>
          <h2 id="pricing-note-heading">Billing and cancellation</h2>
          <p>
            Paid plans use Stripe Checkout and Stripe Customer Portal. Card details are
            handled by Stripe, not stored in OpenMynd.
          </p>
        </div>
      </section>
    </section>
  `,
  styles: [
    `
      .pricing-page {
        display: grid;
        gap: var(--spacing-md);
        max-width: 1120px;
        margin: 0 auto;
      }

      .pricing-back-link,
      .pricing-card,
      .pricing-note {
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
        box-shadow: 0 14px 34px var(--colour-shadow-soft);
      }

      .pricing-back-link {
        display: inline-flex;
        align-items: center;
        justify-self: start;
        gap: var(--spacing-xs);
        min-height: 44px;
        padding: 0 var(--spacing-sm);
        border-radius: var(--radius-pill);
        color: var(--colour-text-primary);
        font-weight: 850;
        text-decoration: none;
      }

      .pricing-back-link:hover {
        background: var(--colour-control-hover);
      }

      .pricing-back-link:focus-visible,
      .pricing-card:focus-within {
        outline: var(--focus-outline);
        outline-offset: 3px;
      }

      .pricing-back-link mat-icon {
        width: 20px;
        height: 20px;
        font-size: 20px;
      }

      .pricing-hero {
        display: grid;
        gap: var(--spacing-xs);
        padding: clamp(1.5rem, 4vw, 2.5rem);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background:
          radial-gradient(
            circle at 14% 0%,
            color-mix(in srgb, var(--colour-primary) 22%, transparent),
            transparent 34%
          ),
          var(--colour-surface-muted);
      }

      .pricing-eyebrow,
      .pricing-hero h1,
      .pricing-hero p,
      .pricing-card h2,
      .pricing-card p,
      .pricing-note h2,
      .pricing-note p {
        margin: 0;
      }

      .pricing-eyebrow,
      .pricing-card__label {
        color: var(--colour-primary);
        font-size: 0.84rem;
        font-weight: 900;
        letter-spacing: 0.12em;
        text-transform: uppercase;
      }

      .pricing-hero h1 {
        font-size: clamp(2.2rem, 5vw, 4rem);
        line-height: 1;
      }

      .pricing-hero p,
      .pricing-card p,
      .pricing-note p {
        color: var(--colour-text-secondary);
      }

      .pricing-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: var(--spacing-md);
      }

      .pricing-card {
        display: grid;
        align-content: start;
        gap: var(--spacing-sm);
        padding: var(--spacing-lg);
        border-radius: var(--radius-lg);
      }

      .pricing-card__icon {
        display: grid;
        width: 3.25rem;
        height: 3.25rem;
        place-items: center;
        border-radius: var(--radius-pill);
        background: var(--colour-control-selected);
        color: var(--colour-control-selected-text);
      }

      .pricing-card__icon mat-icon {
        width: 28px;
        height: 28px;
        font-size: 28px;
      }

      .pricing-card ul {
        display: grid;
        gap: var(--spacing-xs);
        margin: 0;
        padding: 0;
        list-style: none;
      }

      .pricing-card li,
      .pricing-note {
        display: flex;
        align-items: flex-start;
        gap: var(--spacing-xs);
      }

      .pricing-card li mat-icon {
        flex: 0 0 20px;
        width: 20px;
        height: 20px;
        color: var(--colour-success-text);
        font-size: 20px;
      }

      .pricing-note {
        padding: var(--spacing-md);
        border-radius: var(--radius-lg);
      }

      .pricing-note > mat-icon {
        flex: 0 0 28px;
        width: 28px;
        height: 28px;
        color: var(--colour-primary);
        font-size: 28px;
      }

      @media (max-width: 880px) {
        .pricing-grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class PricingComponent {
  readonly plans = PLANS;
}
