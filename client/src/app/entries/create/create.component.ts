// Create entry with support for daily and dream flows
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { EntriesService } from '../../core/services/entries.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { DailyAnalysisResponse, DreamAnalysisResponse } from '../../core/models/entry.model';

@Component({
  selector: 'app-create',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatSlideToggleModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatButtonToggleModule
  ],
  template: `
    <div class="create-container">
      <mat-card>
        <mat-card-header>
          <mat-card-title>New Diary Entry</mat-card-title>
          <mat-slide-toggle [(ngModel)]="leaveItToAI">
            Leave it to AI
          </mat-slide-toggle>
        </mat-card-header>

        <mat-card-content>
          <mat-button-toggle-group
            class="entry-type-toggle"
            [(ngModel)]="selectedType"
            name="entryType"
            aria-label="Entry type toggle"
          >
            <mat-button-toggle value="daily">Daily Entry</mat-button-toggle>
            <mat-button-toggle value="dream">Dream Entry</mat-button-toggle>
          </mat-button-toggle-group>
          <p class="hint" *ngIf="leaveItToAI">
            We'll run an AI analysis straight after saving this entry.
          </p>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Date</mat-label>
            <input matInput [matDatepicker]="picker" [(ngModel)]="entryDate" name="entry_date">
            <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
            <mat-datepicker #picker></mat-datepicker>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Title</mat-label>
            <input matInput [(ngModel)]="entryTitle" name="title">
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>{{ selectedType === 'dream' ? 'Describe your dream' : 'Describe your day' }}</mat-label>
            <textarea
              matInput
              [(ngModel)]="content"
              name="content"
              rows="10"
              placeholder="Share highlights, themes, or key moments..."
            ></textarea>
          </mat-form-field>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>My Tags (comma separated)</mat-label>
            <input matInput [(ngModel)]="tagsInput" name="tags">
          </mat-form-field>

          <div class="actions">
            <button mat-stroked-button color="warn" (click)="cancelCreate()" [disabled]="isSaving">
              Cancel
            </button>
            <button mat-raised-button (click)="saveAsDraft()" [disabled]="isSaving">
              Save Entry
            </button>
            <button mat-raised-button color="primary" (click)="saveAndAnalyse()" [disabled]="isSaving">
              Save & Analyse
            </button>
          </div>

          <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .create-container {
      max-width: 800px;
      margin: 0 auto;
    }

    .full-width {
      width: 100%;
      margin-bottom: var(--spacing-sm);
    }

    .entry-type-toggle {
      margin-bottom: var(--spacing-sm);
    }

    .hint {
      margin-bottom: var(--spacing-sm);
      color: #555;
    }

    .actions {
      display: flex;
      gap: var(--spacing-sm);
      justify-content: flex-end;
      margin-top: var(--spacing-sm);
    }

    mat-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--spacing-md);
    }

    .error {
      color: #c62828;
      margin-top: var(--spacing-sm);
    }
  `]
})
export class CreateComponent {
  private router = inject(Router);
  private entriesService = inject(EntriesService);
  private analysisService = inject(AnalysisService);

  entryDate: Date | null = new Date();
  entryTitle = '';
  content = '';
  tagsInput = '';
  leaveItToAI = false;
  selectedType: 'daily' | 'dream' = 'daily';
  isSaving = false;
  errorMessage = '';

  saveAsDraft(): void {
    this.persistEntry(this.leaveItToAI);
  }

  saveAndAnalyse(): void {
    this.persistEntry(true);
  }

  private persistEntry(shouldAnalyse: boolean): void {
    this.errorMessage = '';

    if (!this.entryDate) {
      this.errorMessage = 'Please select a date for this entry.';
      return;
    }

    if (!this.content.trim()) {
      this.errorMessage = 'Please add some notes so the AI has context.';
      return;
    }

    this.isSaving = true;
    const entryDate = this.entryDate.toISOString().split('T')[0];
    const tags = this.normaliseTags(this.tagsInput);
    const trimmedTitle = this.entryTitle.trim();
    const body = this.content.trim();

    if (this.selectedType === 'daily') {
      const payload = {
        entry_date: entryDate,
        user_message: this.composeDailyMessage(trimmedTitle, body),
        tags
      };

      this.entriesService.createDailyEntry(payload).subscribe({
        next: (created) => {
          if (!shouldAnalyse && tags) {
            this.entriesService.updateDailyEntry(created.id!, { tags }).subscribe({
              next: () => this.finishNavigation(created.id!),
              error: () => this.handleError('Failed to store tags for your daily entry.')
            });
            return;
          }
          if (shouldAnalyse) {
            this.runDailyAnalysis(created.id!);
          } else {
            this.finishNavigation(created.id!);
          }
        },
        error: () => this.handleError('Failed to save your daily entry.')
      });
    } else {
      const payload = {
        entry_date: entryDate,
        title: trimmedTitle,
        plot: body,
        tags
      };

      this.entriesService.createDreamEntry(payload).subscribe({
        next: (created) => {
          if (!shouldAnalyse && tags) {
            this.entriesService.updateDreamEntry(created.id!, { tags }).subscribe({
              next: () => this.finishNavigation(created.id!),
              error: () => this.handleError('Failed to store tags for your dream entry.')
            });
            return;
          }
          if (shouldAnalyse) {
            this.runDreamAnalysis(created.id!);
          } else {
            this.finishNavigation(created.id!);
          }
        },
        error: () => this.handleError('Failed to save your dream entry.')
      });
    }
  }

  private runDailyAnalysis(entryId: number): void {
    this.analysisService.analyseText({
      mode: 'daily',
      text: this.content
    }).subscribe({
      next: (analysis) => {
        const dailyAnalysis = analysis as DailyAnalysisResponse;
        this.entriesService.updateDailyEntry(entryId, {
          ai_response: dailyAnalysis.ai_response,
          tags: this.tagsInput.trim() ? this.normaliseTags(this.tagsInput) : dailyAnalysis.tags,
          daily_people_names: dailyAnalysis.daily_people_names
        }).subscribe({
          next: () => this.finishNavigation(entryId),
          error: () => this.handleError('Saving AI insights failed. Please try again.')
        });
      },
      error: () => this.handleError('AI analysis failed. Please try again later.')
    });
  }

  private runDreamAnalysis(entryId: number): void {
    this.analysisService.analyseText({
      mode: 'dream',
      text: this.content
    }).subscribe({
      next: (analysis) => {
        const dreamAnalysis = analysis as DreamAnalysisResponse;
        this.entriesService.updateDreamEntry(entryId, {
          summary: dreamAnalysis.summary,
          interpretation: dreamAnalysis.interpretation,
          image_prompt: dreamAnalysis.image_prompt,
          tags: this.tagsInput.trim() ? this.normaliseTags(this.tagsInput) : dreamAnalysis.tags,
          dream_people_names: dreamAnalysis.dream_people_names
        }).subscribe({
          next: () => this.finishNavigation(entryId),
          error: () => this.handleError('Saving dream analysis failed. Please try again.')
        });
      },
      error: () => this.handleError('AI analysis failed. Please try again later.')
    });
  }

  private finishNavigation(entryId: number): void {
    this.isSaving = false;
    this.router.navigate(['/entries', entryId]);
  }

  private handleError(message: string): void {
    this.isSaving = false;
    this.errorMessage = message;
  }

  private composeDailyMessage(title: string, body: string): string {
    if (title && body) {
      return `${title}\n\n${body}`;
    }
    if (title) {
      return title;
    }
    return body;
  }

  private normaliseTags(tags: string): string {
    return tags
      .split(',')
      .map(tag => tag.trim())
      .filter(tag => tag.length > 0)
      .join(',');
  }

  cancelCreate(): void {
    const hasChanges = this.entryTitle || this.content || this.tagsInput;
    if (!hasChanges || confirm('Discard this entry?')) {
      this.router.navigate(['/entries']);
    }
  }
}
