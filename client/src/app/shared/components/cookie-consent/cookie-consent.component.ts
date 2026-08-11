import { CommonModule } from "@angular/common";
import { Component, HostListener, OnInit } from "@angular/core";
import { RouterLink } from "@angular/router";

type CookieConsentChoice = "accepted" | "rejected" | "essential";

const COOKIE_CONSENT_KEY = "openmynd_cookie_consent";

@Component({
  selector: "app-cookie-consent",
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <aside
      *ngIf="isVisible"
      class="cookie-banner"
      aria-labelledby="cookie-banner-title"
      data-testid="cookie-consent-banner"
    >
      <div class="cookie-copy">
        <h2 id="cookie-banner-title">Cookies</h2>
        <p>
          OpenMynd uses essential cookies for sign-in and app security. Optional
          cookies can help improve the product.
          <a routerLink="/cookies">Cookie Policy</a>
        </p>
      </div>

      <div class="cookie-actions" *ngIf="!showPreferences">
        <button type="button" class="cookie-action" (click)="saveChoice('rejected')">
          Reject optional
        </button>
        <button type="button" class="cookie-action" (click)="showPreferences = true">
          Manage
        </button>
        <button type="button" class="cookie-action primary" (click)="saveChoice('accepted')">
          Accept optional
        </button>
      </div>

      <div class="cookie-preferences" *ngIf="showPreferences">
        <label>
          <input type="checkbox" checked disabled />
          Essential cookies
        </label>
        <label>
          <input
            type="checkbox"
            [checked]="optionalCookies"
            (change)="setOptionalCookies($event)"
          />
          Optional analytics
        </label>
        <div class="cookie-actions">
          <button type="button" class="cookie-action" (click)="showPreferences = false">
            Back
          </button>
          <button type="button" class="cookie-action primary" (click)="savePreferenceChoice()">
            Save choices
          </button>
        </div>
      </div>
    </aside>
  `,
  styles: [`
    .cookie-banner {
      position: fixed;
      right: var(--spacing-md);
      bottom: var(--spacing-md);
      left: var(--spacing-md);
      z-index: 2200;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: var(--spacing-md);
      align-items: center;
      max-width: 980px;
      margin: 0 auto;
      padding: var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: 28px;
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
      box-shadow: 0 24px 70px var(--colour-shadow-medium);
    }

    .cookie-copy h2,
    .cookie-copy p {
      margin: 0;
    }

    .cookie-copy {
      display: grid;
      gap: 0.25rem;
    }

    .cookie-copy h2 {
      font-size: 1rem;
      letter-spacing: -0.02em;
    }

    .cookie-copy p {
      color: var(--colour-text-secondary);
      line-height: 1.45;
    }

    .cookie-copy a {
      color: var(--colour-primary);
      font-weight: 900;
      text-decoration: underline;
      text-underline-offset: 0.18em;
    }

    .cookie-actions {
      display: flex;
      gap: var(--spacing-xs);
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .cookie-action {
      min-height: 44px;
      padding: 0 var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-pill);
      background: var(--colour-surface-muted);
      color: var(--colour-text-primary);
      cursor: pointer;
      font: inherit;
      font-weight: 900;
    }

    .cookie-action.primary {
      border-color: transparent;
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
    }

    .cookie-action:hover {
      background: var(--colour-control-hover);
    }

    .cookie-action.primary:hover {
      background: var(--colour-control-selected);
      filter: brightness(1.04);
    }

    .cookie-action:focus-visible {
      outline: var(--focus-outline);
      outline-offset: 3px;
    }

    .cookie-preferences {
      display: grid;
      gap: var(--spacing-sm);
      min-width: min(100%, 320px);
    }

    .cookie-preferences label {
      display: flex;
      align-items: center;
      gap: var(--spacing-xs);
      color: var(--colour-text-secondary);
      font-weight: 800;
    }

    @media (max-width: 760px) {
      .cookie-banner {
        grid-template-columns: 1fr;
      }

      .cookie-actions {
        justify-content: flex-start;
      }
    }
  `],
})
export class CookieConsentComponent implements OnInit {
  isVisible = false;
  showPreferences = false;
  optionalCookies = false;

  ngOnInit(): void {
    this.isVisible = !localStorage.getItem(COOKIE_CONSENT_KEY);
  }

  @HostListener("window:openmynd-cookie-preferences")
  openPreferences(): void {
    this.optionalCookies = this.currentChoiceAllowsOptionalCookies();
    this.showPreferences = true;
    this.isVisible = true;
  }

  savePreferenceChoice(): void {
    this.saveChoice(this.optionalCookies ? "accepted" : "essential");
  }

  setOptionalCookies(event: Event): void {
    this.optionalCookies =
      event.target instanceof HTMLInputElement ? event.target.checked : false;
  }

  saveChoice(choice: CookieConsentChoice): void {
    localStorage.setItem(
      COOKIE_CONSENT_KEY,
      JSON.stringify({
        choice,
        optionalCookies: choice === "accepted",
        savedAt: new Date().toISOString(),
      }),
    );
    this.isVisible = false;
  }

  private currentChoiceAllowsOptionalCookies(): boolean {
    const rawChoice = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!rawChoice) return false;
    try {
      const parsed = JSON.parse(rawChoice) as { optionalCookies?: unknown };
      return parsed.optionalCookies === true;
    } catch {
      return false;
    }
  }
}
