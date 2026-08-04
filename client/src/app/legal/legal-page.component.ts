import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";

type LegalPageKind = "privacy" | "terms" | "cookies";

interface LegalSection {
  heading: string;
  body: string;
}

interface LegalPageContent {
  eyebrow: string;
  title: string;
  summary: string;
  icon: string;
  sections: LegalSection[];
}

const LEGAL_CONTENT: Record<LegalPageKind, LegalPageContent> = {
  privacy: {
    eyebrow: "Privacy",
    title: "Privacy policy",
    summary:
      "OpenMynd is designed around private journalling, user ownership, and clear control over AI-assisted features.",
    icon: "shield",
    sections: [
      {
        heading: "What OpenMynd stores",
        body:
          "OpenMynd stores account details, diary entries, dream entries, thought records, important days, settings, attachments, generated images, imports, and related metadata needed to run the app.",
      },
      {
        heading: "How AI features use your data",
        body:
          "AI analysis uses the entry content and only the context you enable, such as previous entries or attachment-derived text. AI-generated images use saved image prompts and do not require public sharing of your diary.",
      },
      {
        heading: "Data portability",
        body:
          "Export tools are intended to let you keep a local copy of your diary data and media. Database and backup hardening remains part of production-readiness work.",
      },
    ],
  },
  terms: {
    eyebrow: "Terms",
    title: "Terms and conditions",
    summary:
      "These terms describe the expected use of OpenMynd while the product is prepared for wider release.",
    icon: "description",
    sections: [
      {
        heading: "Personal diary use",
        body:
          "OpenMynd is a personal journalling and reflection tool. It is not a medical, legal, crisis, or financial advice service.",
      },
      {
        heading: "User responsibility",
        body:
          "You are responsible for the entries, files, and settings you add. Keep exports and backups secure, especially where they contain personal or sensitive content.",
      },
      {
        heading: "AI limitations",
        body:
          "AI responses may be incomplete or inaccurate. Treat them as reflective assistance rather than professional advice or a definitive record of events.",
      },
    ],
  },
  cookies: {
    eyebrow: "Cookies",
    title: "Cookie policy",
    summary:
      "OpenMynd uses essential local browser storage to keep the app usable and personalised.",
    icon: "cookie",
    sections: [
      {
        heading: "Essential storage",
        body:
          "The app may use browser storage for authentication state, theme choice, view preferences, and other settings needed for normal operation.",
      },
      {
        heading: "Preference storage",
        body:
          "Display mode, colour theme, and similar preferences can be stored locally so the interface stays consistent when you return.",
      },
      {
        heading: "Analytics and marketing",
        body:
          "No marketing or analytics cookie controls are active in this local build. If those services are introduced later, this page and the settings flow must be updated first.",
      },
    ],
  },
};

@Component({
  selector: "app-legal-page",
  standalone: true,
  imports: [CommonModule, RouterLink, MatIconModule],
  template: `
    <section class="legal-page" data-testid="legal-page">
      <a
        routerLink="/entries"
        class="legal-back-link"
        data-testid="legal-back-link"
      >
        <mat-icon aria-hidden="true">arrow_back</mat-icon>
        Back to app
      </a>

      <article class="legal-card" [attr.data-testid]="'legal-' + pageKind">
        <header class="legal-hero">
          <span class="legal-icon" aria-hidden="true">
            <mat-icon>{{ page.icon }}</mat-icon>
          </span>
          <p class="legal-eyebrow">{{ page.eyebrow }}</p>
          <h1>{{ page.title }}</h1>
          <p>{{ page.summary }}</p>
        </header>

        <div class="legal-section-list">
          <section
            class="legal-section"
            *ngFor="let section of page.sections"
          >
            <h2>{{ section.heading }}</h2>
            <p>{{ section.body }}</p>
          </section>
        </div>
      </article>
    </section>
  `,
  styles: [
    `
      .legal-page {
        display: grid;
        gap: var(--spacing-md);
        max-width: 920px;
        margin: 0 auto;
      }

      .legal-back-link {
        display: inline-flex;
        align-items: center;
        justify-self: start;
        gap: var(--spacing-xs);
        min-height: 44px;
        padding: 0 var(--spacing-sm);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
        color: var(--colour-text-primary);
        font-weight: 800;
        text-decoration: none;
      }

      .legal-back-link:hover {
        background: var(--colour-control-hover);
      }

      .legal-back-link:focus-visible {
        outline: var(--focus-outline);
        outline-offset: 3px;
      }

      .legal-back-link mat-icon {
        width: 20px;
        height: 20px;
        font-size: 20px;
      }

      .legal-card {
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface);
        box-shadow: 0 14px 34px var(--colour-shadow-soft);
        overflow: hidden;
      }

      .legal-hero {
        display: grid;
        gap: var(--spacing-xs);
        padding: clamp(1.25rem, 4vw, 2.25rem);
        border-bottom: 1px solid var(--colour-border);
        background:
          radial-gradient(
            circle at 10% 0%,
            color-mix(in srgb, var(--colour-primary) 18%, transparent),
            transparent 32%
          ),
          var(--colour-surface-muted);
      }

      .legal-icon {
        display: grid;
        width: 3.5rem;
        height: 3.5rem;
        place-items: center;
        border-radius: var(--radius-pill);
        background: var(--colour-control-selected);
        color: var(--colour-control-selected-text);
      }

      .legal-icon mat-icon {
        width: 28px;
        height: 28px;
        font-size: 28px;
      }

      .legal-eyebrow,
      .legal-hero h1,
      .legal-hero p,
      .legal-section h2,
      .legal-section p {
        margin: 0;
      }

      .legal-eyebrow {
        color: var(--colour-primary);
        font-size: 0.85rem;
        font-weight: 900;
        letter-spacing: 0.12em;
        text-transform: uppercase;
      }

      .legal-hero h1 {
        font-size: clamp(2rem, 5vw, 3.2rem);
        line-height: 1;
      }

      .legal-hero p,
      .legal-section p {
        color: var(--colour-text-secondary);
      }

      .legal-section-list {
        display: grid;
        gap: var(--spacing-sm);
        padding: clamp(1rem, 3vw, 1.5rem);
      }

      .legal-section {
        display: grid;
        gap: 0.45rem;
        padding: var(--spacing-md);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: color-mix(
          in srgb,
          var(--colour-surface-muted) 72%,
          transparent
        );
      }

      .legal-section h2 {
        font-size: 1.1rem;
      }

      @media (max-width: 720px) {
        .legal-section {
          padding: var(--spacing-sm);
        }
      }
    `,
  ],
})
export class LegalPageComponent {
  private readonly route = inject(ActivatedRoute);

  readonly pageKind = this.getPageKind();
  readonly page = LEGAL_CONTENT[this.pageKind];

  private getPageKind(): LegalPageKind {
    const pageKind = this.route.snapshot.data["legalPage"];
    return pageKind === "terms" || pageKind === "cookies"
      ? pageKind
      : "privacy";
  }
}
