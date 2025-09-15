// Create entry with "Leave it to AI" option
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
import { EntriesService } from '../../core/services/entries.service';
import { AnalysisService } from '../../core/services/analysis.service';

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
    MatNativeDateModule
  ],
  template: `
    <div class="create-container">
      <mat-card>
        <mat-card-header>
          <mat-card-title>Create Entry</mat-card-title>
          <mat-slide-toggle [(ngModel)]="leaveItToAI">
            Leave it to AI
          </mat-slide-toggle>
        </mat-card-header>
        
        <mat-card-content>
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Date</mat-label>
            <input matInput [matDatepicker]="picker" [(ngModel)]="entryDate">
            <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
            <mat-datepicker #picker></mat-datepicker>
          </mat-form-field>
          
          <mat-form-field appearance="outline" class="full-width" *ngIf="!leaveItToAI">
            <mat-label>Title (for dreams)</mat-label>
            <input matInput [(ngModel)]="title">
          </mat-form-field>
          
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Your Entry</mat-label>
            <textarea 
              matInput 
              [(ngModel)]="content"
              rows="10"
              placeholder="Write about your day or describe your dream..."
            ></textarea>
          </mat-form-field>
          
          <div class="actions">
            <button mat-raised-button (click)="saveAsDraft()">Save as Draft</button>
            <button mat-raised-button color="primary" (click)="saveAndAnalyse()">
              Save and Analyse
            </button>
          </div>
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
    
    .actions {
      display: flex;
      gap: var(--spacing-sm);
      justify-content: flex-end;
    }
    
    mat-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--spacing-md);
    }
  `]
})
export class CreateComponent {
  private router = inject(Router);
  private entriesService = inject(EntriesService);
  private analysisService = inject(AnalysisService);
  
  entryDate = new Date();
  title = '';
  content = '';
  leaveItToAI = false;
  
  saveAsDraft(): void {
    const entry = {
      entry_date: this.entryDate.toISOString().split('T')[0],
      user_message: this.content
    };
    
    this.entriesService.createDailyEntry(entry).subscribe({
      next: (created) => this.router.navigate(['/entries', created.id]),
      error: err => console.error('Failed to save:', err)
    });
  }
  
  saveAndAnalyse(): void {
    const entry = {
      entry_date: this.entryDate.toISOString().split('T')[0],
      user_message: this.content
    };
    
    this.entriesService.createDailyEntry(entry).subscribe({
      next: (created) => {
        // Call analysis API
        this.analysisService.analyseText({
          mode: 'daily',
          text: this.content
        }).subscribe({
          next: (analysis: any) => {
            // Update entry with AI analysis
            this.entriesService.updateDailyEntry(created.id!, {
              ai_response: analysis.ai_response,
              tags: analysis.tags,
              daily_people_names: analysis.daily_people_names
            }).subscribe({
              next: () => this.router.navigate(['/entries', created.id]),
              error: err => console.error('Failed to update with analysis:', err)
            });
          },
          error: err => console.error('Analysis failed:', err)
        });
      },
      error: err => console.error('Failed to save:', err)
    });
  }
}