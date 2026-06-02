import { Component } from "@angular/core";
import { CommonModule, Location } from "@angular/common";
import { Router, RouterModule } from "@angular/router";
import { MatIconModule } from "@angular/material/icon";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";

@Component({
  selector: "app-settings",
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatIconModule,
    MatCardModule,
    MatButtonModule,
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

          <mat-card class="settings-card">
            <mat-card-header>
              <mat-icon mat-card-avatar>key</mat-icon>
              <mat-card-title>API Keys</mat-card-title>
              <mat-card-subtitle
                >Connect external AI services</mat-card-subtitle
              >
            </mat-card-header>
            <mat-card-content>
              Manage your Daily and Dream diary API keys used for profile-level
              AI features.
            </mat-card-content>
            <mat-card-actions>
              <a mat-flat-button color="primary" routerLink="/settings/api-keys"
                >Manage Keys</a
              >
            </mat-card-actions>
          </mat-card>

          <mat-card class="settings-card">
            <mat-card-header>
              <mat-icon mat-card-avatar>psychology</mat-icon>
              <mat-card-title>AI Coach Preferences</mat-card-title>
              <mat-card-subtitle
                >Tune tone, reminders, and insight depth</mat-card-subtitle
              >
            </mat-card-header>
            <mat-card-content>
              Set the coach names used for Daily and Dream diary companion
              prompts.
            </mat-card-content>
            <mat-card-actions>
              <a mat-flat-button color="primary" routerLink="/settings/ai-coach"
                >Edit Preferences</a
              >
            </mat-card-actions>
          </mat-card>
        </section>
      </ng-container>

      <ng-template #childPage>
        <div class="child-nav">
          <button
            mat-stroked-button
            type="button"
            class="header-back"
            (click)="goBack()"
            aria-label="Go back"
          >
            <mat-icon>arrow_back</mat-icon>
            Back
          </button>
        </div>
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

      .child-nav {
        margin-bottom: var(--spacing-md);
      }

      .header-back {
        border-color: var(--colour-border);
        color: var(--colour-text-secondary);
      }

      .header-back mat-icon {
        margin-right: var(--spacing-xs);
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
  constructor(
    private readonly router: Router,
    private readonly location: Location,
  ) {}

  goBack(): void {
    if (this.canGoBack()) {
      this.location.back();
      return;
    }

    this.router.navigateByUrl("/settings");
  }

  isLandingPage(): boolean {
    return this.getCurrentPath() === "/settings";
  }

  private getCurrentPath(): string {
    return this.router.url.split("?")[0].split("#")[0];
  }

  private canGoBack(): boolean {
    if (typeof window === "undefined") {
      return false;
    }

    const navigationId = window.history.state?.navigationId;
    if (typeof navigationId === "number") {
      return navigationId > 1;
    }

    return window.history.length > 1;
  }
}
