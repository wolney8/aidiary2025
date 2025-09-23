// Create entry with support for daily and dream flows
import { Component, HostListener, inject, ViewChild, ElementRef, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule, MAT_DATE_FORMATS, MAT_DATE_LOCALE } from '@angular/material/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatChipsModule, MatChipInputEvent } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { EntriesService } from '../../core/services/entries.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { DailyAnalysisResponse, DreamAnalysisResponse } from '../../core/models/entry.model';

const UK_DATE_FORMATS = {
  parse: {
    dateInput: 'dd/MM/yyyy'
  },
  display: {
    dateInput: 'dd/MM/yyyy',
    monthYearLabel: 'MMMM yyyy',
    dateA11yLabel: 'dd/MM/yyyy',
    monthYearA11yLabel: 'MMMM yyyy'
  }
};

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
    MatButtonToggleModule,
    MatChipsModule,
    MatIconModule
  ],
  providers: [
    { provide: MAT_DATE_LOCALE, useValue: 'en-GB' },
    { provide: MAT_DATE_FORMATS, useValue: UK_DATE_FORMATS }
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
            <input matInput [matDatepicker]="picker" [(ngModel)]="entryDate" name="entry_date" [max]="maxDate">
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
            <mat-label>My Tags</mat-label>
            <mat-chip-grid #chipGrid>
              <mat-chip-row *ngFor="let tag of tags" (removed)="removeTag(tag)">
                {{ tag }}
                <button matChipRemove type="button">
                  <mat-icon>cancel</mat-icon>
                </button>
              </mat-chip-row>
              <input
                placeholder="Type and press enter"
                [matChipInputFor]="chipGrid"
                [matChipInputSeparatorKeyCodes]="separatorKeysCodes"
                [matChipInputAddOnBlur]="true"
                (matChipInputTokenEnd)="addTag($event)"
              />
            </mat-chip-grid>
          </mat-form-field>

          <div class="actions">
            <button mat-stroked-button color="warn" (click)="cancelCreate()" [disabled]="isSaving">
              Cancel
            </button>

            <ng-container *ngIf="!leaveItToAI; else aiActions">
              <button mat-stroked-button (click)="triggerImageUpload()" [disabled]="isSaving">
                Upload Image
              </button>
              <button mat-raised-button color="primary" (click)="saveAsDraft()" [disabled]="isSaving">
                Save Entry
              </button>
            </ng-container>

            <ng-template #aiActions>
              <button mat-raised-button color="primary" (click)="saveAndAnalyse()" [disabled]="isSaving">
                Save & Analyse
              </button>
            </ng-template>
          </div>

          <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
          <input #fileInput type="file" class="hidden" (change)="handleImageUpload($event)" accept="image/*" />
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

    .hidden {
      display: none;
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
export class CreateComponent implements OnInit {
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private entriesService = inject(EntriesService);
  private analysisService = inject(AnalysisService);
  @ViewChild('fileInput') fileInput?: ElementRef<HTMLInputElement>;

  entryDate: Date | null = new Date();
  entryTitle = '';
  content = '';
  tags: string[] = [];
  leaveItToAI = false;
  selectedType: 'daily' | 'dream' = 'daily';
  isSaving = false;
  errorMessage = '';
  maxDate = new Date();
  readonly separatorKeysCodes = [ENTER, COMMA] as const;
  private initialDate = this.entryDate?.toDateString() ?? '';

  ngOnInit(): void {
    // Check for pre-populated date and type from query params
    this.route.queryParamMap.subscribe(params => {
      const dateParam = params.get('date');
      if (dateParam) {
        // Parse UK format date DD/MM/YYYY
        const [day, month, year] = dateParam.split('/');
        if (day && month && year) {
          const parsedDate = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
          if (!isNaN(parsedDate.getTime())) {
            this.entryDate = parsedDate;
            this.initialDate = this.entryDate.toDateString();
          }
        }
      }

      // Check for entry type parameter
      const typeParam = params.get('type');
      if (typeParam === 'dream' || typeParam === 'daily') {
        this.selectedType = typeParam;
      }
    });
  }

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
    const tags = this.tags.join(',');
    const trimmedTitle = this.entryTitle.trim();
    const body = this.content.trim();

    if (this.selectedType === 'daily') {
      const payload = {
        entry_date: entryDate,
        title: trimmedTitle,
        user_message: body,
        tags
      };

      this.entriesService.createDailyEntry(payload).subscribe({
        next: (created) => {
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
          tags: this.tags.length ? this.tags.join(',') : dailyAnalysis.tags,
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
          tags: this.tags.length ? this.tags.join(',') : dreamAnalysis.tags,
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
    this.resetForm();
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

  cancelCreate(): void {
    if (!this.hasUnsavedChanges() || confirm('Discard this entry?')) {
      this.resetForm();
      this.router.navigate(['/entries']);
    }
  }

  addTag(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();
    if (value && !this.tags.includes(value)) {
      this.tags.push(value);
    }
    event.chipInput?.clear();
  }

  removeTag(tag: string): void {
    this.tags = this.tags.filter(t => t !== tag);
  }

  triggerImageUpload(): void {
    this.fileInput?.nativeElement.click();
  }

  handleImageUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length) {
      // Placeholder for future upload handling
      alert('Image upload is not implemented yet.');
      input.value = '';
    }
  }

  canDeactivate(): boolean {
    return !this.hasUnsavedChanges() || confirm('Discard your entry?');
  }

  @HostListener('window:beforeunload', ['$event'])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.hasUnsavedChanges()) {
      event.preventDefault();
      event.returnValue = '';
    }
  }

  private hasUnsavedChanges(): boolean {
    return Boolean(
      (this.entryTitle && this.entryTitle.trim()) ||
      (this.content && this.content.trim()) ||
      this.tags.length ||
      (this.entryDate && this.entryDate.toDateString() !== this.initialDate)
    );
  }

  private resetForm(): void {
    this.isSaving = false;
    this.errorMessage = '';
    this.entryDate = new Date();
    this.initialDate = this.entryDate.toDateString();
    this.entryTitle = '';
    this.content = '';
    this.tags = [];
    this.leaveItToAI = false;
    this.selectedType = 'daily';
  }
}
