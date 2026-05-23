import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterLink } from "@angular/router";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-settings",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
  ],
  template: `
    <div class="settings-page">
      <mat-card>
        <mat-card-header>
          <mat-card-title>Settings</mat-card-title>
        </mat-card-header>

        <mat-card-content>
          <p>Manage your AI Diary settings.</p>
        </mat-card-content>

        <mat-card-actions>
          <a mat-raised-button color="primary" routerLink="/settings/import">
            <mat-icon>upload_file</mat-icon>
            Import entries
          </a>
        </mat-card-actions>
      </mat-card>
    </div>
  `,
  styles: [
    `
      .settings-page {
        display: flex;
        justify-content: center;
        padding: 2rem 1rem;
      }

      mat-card {
        width: 100%;
        max-width: 560px;
      }

      mat-card-actions {
        padding: 0 1rem 1rem;
      }

      a[mat-raised-button] {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
      }
    `,
  ],
})
export class SettingsComponent {}
