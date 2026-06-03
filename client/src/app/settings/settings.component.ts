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
    <section class="settings-shell">
      <header class="settings-header">
        <h1>Settings</h1>
        <p>Manage your account preferences, AI behaviour, and diary data tools.</p>
      </header>

      <div class="settings-summary">
        <mat-card class="summary-card">
          <mat-card-content>
            <mat-icon>person</mat-icon>
            <div>
              <h2>Profile</h2>
              <p>Biographical details and reflection goals.</p>
              <a mat-button routerLink="/profile">Open Profile</a>
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card class="summary-card">
          <mat-card-content>
            <mat-icon>tune</mat-icon>
            <div>
              <h2>Personalisation</h2>
              <p>Display name, pronouns, AI style, and coach settings.</p>
              <a mat-button routerLink="/settings/personalisation"
                >Open Personalisation</a
              >
            </div>
          </mat-card-content>
        </mat-card>

        <mat-card class="summary-card">
          <mat-card-content>
            <mat-icon>database</mat-icon>
            <div>
              <h2>Data Tools</h2>
              <p>Import, export, and future portability actions.</p>
            </div>
          </mat-card-content>
        </mat-card>
      </div>

      <nav class="settings-nav" aria-label="Settings sections">
        <a
          mat-stroked-button
          routerLink="/settings/personalisation"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          <mat-icon>tune</mat-icon>
          Personalisation
        </a>

        <a
          mat-stroked-button
          routerLink="/settings/import"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          <mat-icon>upload_file</mat-icon>
          Import
        </a>

        <a
          mat-stroked-button
          routerLink="/settings/export"
          routerLinkActive="is-active"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          <mat-icon>download</mat-icon>
          Export
        </a>
      </nav>

      <mat-card class="settings-content">
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
        gap: var(--spacing-md);
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
        gap: var(--spacing-sm);
      }

      .settings-summary {
        display: grid;
        gap: var(--spacing-sm);
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }

      .summary-card {
        border: 1px solid var(--colour-border);
        background: var(--colour-surface-muted);
      }

      .summary-card mat-card-content {
        display: flex;
        gap: var(--spacing-sm);
        align-items: flex-start;
      }

      .summary-card mat-icon {
        color: var(--colour-primary);
        margin-top: 2px;
      }

      .summary-card h2 {
        font-size: 1rem;
        margin: 0 0 var(--spacing-xs);
      }

      .summary-card p {
        margin: 0 0 var(--spacing-sm);
        color: var(--colour-text-secondary);
      }

      .settings-nav a.is-active {
        border-color: var(--colour-primary);
        color: var(--colour-primary);
      }

      .settings-content {
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }
    `,
  ],
})
export class SettingsComponent {}
