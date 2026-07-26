import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import {
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from "@angular/router";

@Component({
  selector: "app-settings",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
  ],
  template: `
    <section class="settings-shell" data-testid="settings-shell">
      <header class="settings-header" data-testid="settings-header">
        <h1>Settings</h1>
        <p>Manage your account preferences, AI behaviour, and diary data tools.</p>
      </header>

      <nav class="settings-nav" aria-label="Settings sections">
        <a
          mat-stroked-button
          class="settings-nav-link"
          routerLink="/settings/appearance"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          data-testid="settings-nav-appearance"
        >
          <mat-icon>palette</mat-icon>
          Appearance
        </a>

        <a
          mat-stroked-button
          class="settings-nav-link"
          routerLink="/settings/personalisation"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          data-testid="settings-nav-customisation"
        >
          <mat-icon>tune</mat-icon>
          Customisation
        </a>

        <a
          mat-stroked-button
          class="settings-nav-link"
          routerLink="/settings/import"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          data-testid="settings-nav-import"
        >
          <mat-icon>upload_file</mat-icon>
          Import
        </a>

        <a
          mat-stroked-button
          class="settings-nav-link"
          routerLink="/settings/export"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
          data-testid="settings-nav-export"
        >
          <mat-icon>download</mat-icon>
          Export
        </a>
      </nav>

      <mat-card class="settings-content" data-testid="settings-content">
        <mat-card-content>
          <router-outlet></router-outlet>
        </mat-card-content>
      </mat-card>
    </section>
  `,
  styles: [
    `
      .settings-shell {
        display: grid;
        gap: var(--spacing-lg);
      }

      .settings-header h1 {
        margin: 0 0 var(--spacing-xs);
      }

      .settings-header p {
        margin: 0;
        color: var(--colour-text-secondary);
      }

      .settings-nav {
        display: flex;
        flex-wrap: wrap;
        gap: var(--spacing-xs);
        align-items: center;
        padding: var(--spacing-xs);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
        width: fit-content;
        max-width: 100%;
      }

      .settings-nav-link {
        min-height: 44px;
        border-color: transparent;
        color: var(--colour-text-secondary);
        background: transparent;
      }

      .settings-nav-link:hover {
        border-color: var(--colour-border);
        background: var(--colour-control-hover);
        color: var(--colour-text-primary);
      }

      .settings-nav-link mat-icon {
        margin-right: var(--spacing-xs);
      }

      .settings-nav-link.is-active {
        --mdc-outlined-button-label-text-color: var(
          --colour-control-selected-text
        );
        --mdc-outlined-button-outline-color: var(--colour-control-selected);

        border-color: var(--colour-control-selected);
        background: var(--colour-control-selected);
        color: var(--colour-control-selected-text);
        box-shadow: 0 8px 20px var(--colour-primary-shadow);
      }

      :host ::ng-deep .settings-nav-link.is-active .mdc-button__label {
        color: var(--colour-control-selected-text) !important;
      }

      .settings-nav-link.is-active mat-icon {
        color: currentColor;
      }

      .settings-content {
        border-radius: var(--radius-lg);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }

      .settings-content mat-card-content {
        padding: var(--spacing-md);
      }

      @media (max-width: 720px) {
        .settings-shell {
          gap: var(--spacing-md);
        }

        .settings-nav {
          width: auto;
          border-radius: var(--radius-lg);
        }

        .settings-nav-link {
          flex: 1 1 calc(50% - var(--spacing-xs));
          justify-content: center;
        }

        .settings-content mat-card-content {
          padding: var(--spacing-sm);
        }
      }
    `,
  ],
})
export class SettingsComponent {}
