import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { RouterLink, RouterLinkActive, RouterOutlet } from "@angular/router";

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
        <p>Manage import and export tools for your diary data.</p>
      </header>

      <nav class="settings-nav" aria-label="Settings sections">
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
