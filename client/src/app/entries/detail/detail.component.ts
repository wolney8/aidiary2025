// Entry detail view with two-column layout
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { EntriesService } from '../../core/services/entries.service';

@Component({
  selector: 'app-detail',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatButtonModule
  ],
  template: `
    <div class="detail-container" *ngIf="entry">
      <!-- Date navigation -->
      <div class="date-nav">
        <button mat-icon-button>
          <mat-icon>chevron_left</mat-icon>
        </button>
        <h2>{{ entry.entry_date | date:'dd/MM/yyyy' }}</h2>
        <button mat-icon-button>
          <mat-icon>chevron_right</mat-icon>
        </button>
      </div>
      
      <!-- Hero image area -->
      <div class="hero-image">
        <mat-icon>image</mat-icon>
        <button mat-raised-button>Reupload Image</button>
      </div>
      
      <!-- Two-column content -->
      <div class="detail-columns">
        <mat-card>
          <mat-card-header>
            <mat-card-title>{{ getTitle() }}</mat-card-title>
            <button mat-icon-button>
              <mat-icon>edit</mat-icon>
            </button>
          </mat-card-header>
          <mat-card-content>
            <p>{{ getUserContent() }}</p>
          </mat-card-content>
        </mat-card>
        
        <mat-card>
          <mat-card-header>
            <mat-card-title>AI Response</mat-card-title>
            <button mat-icon-button>
              <mat-icon>refresh</mat-icon>
            </button>
          </mat-card-header>
          <mat-card-content>
            <p>{{ getAIContent() }}</p>
          </mat-card-content>
        </mat-card>
      </div>
      
      <!-- Metadata bar -->
      <div class="metadata-bar">
        <div class="metadata-section">
          <h4>My Tags:</h4>
          <mat-chip-set>
            <mat-chip *ngFor="let tag of getTags()">{{ tag }}</mat-chip>
          </mat-chip-set>
        </div>
        
        <div class="metadata-section">
          <h4>Keywords:</h4>
          <p>{{ entry.tags }}</p>
        </div>
        
        <div class="metadata-section">
          <h4>People Names and Places:</h4>
          <p>{{ getPeopleNames() }}</p>
        </div>
        
        <div class="metadata-section" *ngIf="isDream()">
          <h4>Image Generated with prompt:</h4>
          <p>{{ entry.image_prompt }}</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .detail-container {
      max-width: 1200px;
      margin: 0 auto;
    }
    
    .date-nav {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-md);
      margin-bottom: var(--spacing-md);
    }
    
    .hero-image {
      height: 300px;
      background: #f5f5f5;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: var(--spacing-md);
      margin-bottom: var(--spacing-md);
      border-radius: 8px;
      
      mat-icon {
        font-size: 64px;
        width: 64px;
        height: 64px;
        color: #ccc;
      }
    }
    
    .detail-columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--spacing-md);
      margin-bottom: var(--spacing-md);
      
      @media (max-width: 768px) {
        grid-template-columns: 1fr;
      }
    }
    
    .metadata-bar {
      background: #f5f5f5;
      padding: var(--spacing-md);
      border-radius: 8px;
      
      .metadata-section {
        margin-bottom: var(--spacing-md);
        
        h4 {
          margin-bottom: var(--spacing-sm);
        }
      }
    }
  `]
})
export class DetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private entriesService = inject(EntriesService);
  
  entry: any;
  entryType: 'daily' | 'dream' = 'daily';
  
  ngOnInit(): void {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    // Try loading as daily first, then dream if not found
    this.entriesService.getDailyEntry(id).subscribe({
      next: entry => {
        this.entry = entry;
        this.entryType = 'daily';
      },
      error: () => {
        this.entriesService.getDreamEntry(id).subscribe(entry => {
          this.entry = entry;
          this.entryType = 'dream';
        });
      }
    });
  }
  
  getTitle(): string {
    if (!this.entry) {
      return 'Entry';
    }
    if (this.isDream() && this.entry.title) {
      return this.entry.title;
    }
    if (!this.isDream()) {
      // For daily entries, use the title field if available
      if (this.entry.title) {
        return this.entry.title;
      }
      // Fallback to old logic for entries without titles
      const [title] = this.splitDailyMessage(this.entry.user_message || '');
      return title || 'Entry';
    }
    return 'Entry';
  }
  
  getUserContent(): string {
    if (!this.entry) {
      return '';
    }
    if (this.isDream()) {
      return this.entry.plot || '';
    }
    // For daily entries
    if (this.entry.title) {
      // New format: title is separate, user_message contains only content
      return this.entry.user_message || '';
    }
    // Old format: extract content from user_message (skip title part)
    return this.splitDailyMessage(this.entry.user_message || '')[1];
  }
  
  getAIContent(): string {
    return this.isDream() ? this.entry.interpretation || '' : this.entry.ai_response || '';
  }
  
  getTags(): string[] {
    return this.entry.tags ? this.entry.tags.split(',').map((t: string) => t.trim()) : [];
  }
  
  getPeopleNames(): string {
    return this.isDream() ? this.entry.dream_people_names || '' : this.entry.daily_people_names || '';
  }
  
  isDream(): boolean {
    return this.entryType === 'dream';
  }

  private splitDailyMessage(message: string): [string, string] {
    if (!message) {
      return ['', ''];
    }
    const [title, ...rest] = message.split(/\n\n?/);
    if (rest.length === 0) {
      return ['', title];
    }
    return [title, rest.join('\n\n')];
  }
}
