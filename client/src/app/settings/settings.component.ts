import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { Router, RouterModule } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";
import { MatChipsModule } from "@angular/material/chips";

@Component({
  selector: "app-settings",
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatIconModule,
    MatCardModule,
    MatButtonModule,
    MatChipsModule,
  ],
  template: `
    <div class="settings-shell" role="main" aria-label="Settings">
      <ng-container *ngIf="isLandingPage(); else childPage">
        <header class="settings-header">
          <h1>Settings</h1>
          <p>Manage your diary tools, data workflows, and personal AI setup.</p>
        </header>

        <section class="settings-grid" aria-label="Settings sections">
          <mat-card class="settings-card">
            <mat-card-header>
              <mat-icon mat-card-avatar>upload_file</mat-icon>
              <mat-card-title>Import Entries</mat-card-title>
              <mat-card-subtitle
                >Bulk import from Excel template</mat-card-subtitle
              >
            </mat-card-header>
            <mat-card-content>
              Bring in existing journal records quickly using the import
              template.
            </mat-card-content>
            <mat-card-actions>
              <a mat-flat-button color="primary" routerLink="/settings/import"
                >Open Import</a
              >
            </mat-card-actions>
          </mat-card>

          <mat-card class="settings-card">
            <mat-card-header>
              <mat-icon mat-card-avatar>download</mat-icon>
              <mat-card-title>Export Entries</mat-card-title>
              <mat-card-subtitle>Download entries as Excel</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              Export your diary data to keep backups or move it to another tool.
            </mat-card-content>
            <mat-card-actions>
              <a mat-flat-button color="primary" routerLink="/settings/export"
                >Open Export</a
              >
            </mat-card-actions>
          </mat-card>

          <mat-card
            class="settings-card settings-card--coming-soon"
            aria-disabled="true"
          >
            <mat-card-header>
              <mat-icon mat-card-avatar>key</mat-icon>
              <mat-card-title>API Keys</mat-card-title>
              <mat-card-subtitle
                >Connect external AI services</mat-card-subtitle
              >
            </mat-card-header>
            <mat-card-content>
              <mat-chip-set>
                <mat-chip>Coming soon</mat-chip>
              </mat-chip-set>
            </mat-card-content>
            <mat-card-actions>
              <button mat-stroked-button disabled>Coming soon</button>
            </mat-card-actions>
          </mat-card>

          <mat-card
            class="settings-card settings-card--coming-soon"
            aria-disabled="true"
          >
            <mat-card-header>
              <mat-icon mat-card-avatar>psychology</mat-icon>
              <mat-card-title>AI Coach Preferences</mat-card-title>
              <mat-card-subtitle
                >Tune tone, reminders, and insight depth</mat-card-subtitle
              >
            </mat-card-header>
            <mat-card-content>
              <mat-chip-set>
                <mat-chip>Coming soon</mat-chip>
              </mat-chip-set>
            </mat-card-content>
            <mat-card-actions>
              <button mat-stroked-button disabled>Coming soon</button>
            </mat-card-actions>
          </mat-card>
        </section>
      </ng-container>

      <ng-template #childPage>
        <div class="settings-content">
          <router-outlet></router-outlet>
        </div>
      </ng-template>
    </div>
  `,
  styles: [
    `
      .settings-shell {
        padding: var(--spacing-md, 16px);
        max-width: 1100px;
        margin: 0 auto;
      }

      .settings-header {
        margin-bottom: 20px;
      }

      .settings-header h1 {
        margin: 0;
      }

      .settings-header p {
        margin: 8px 0 0;
        color: var(--colour-text-secondary);
      }

      .settings-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 16px;
      }

      .settings-card {
        border-radius: var(--radius-md);
        border: 1px solid var(--colour-border);
        background: var(--colour-surface);
      }

      .settings-card mat-card-content {
        color: var(--colour-text-secondary);
      }

      .settings-card--coming-soon {
        opacity: 0.9;
      }

      .settings-content {
        min-width: 0;
      }

      @media (max-width: 900px) {
        .settings-grid {
          grid-template-columns: 1fr;
        }
      }

      @media (max-width: 768px) {
        .settings-shell {
          padding: 8px;
        }
      }
    `,
  ],
})
export class SettingsComponent {
  constructor(private readonly router: Router) {}

  isLandingPage(): boolean {
    return (
      this.router.url === "/settings" ||
      this.router.url.startsWith("/settings?") ||
      this.router.url.startsWith("/settings#")
    );
  }
}
