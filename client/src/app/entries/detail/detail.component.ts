// Entry detail view with two-column layout
import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { EntriesService } from '../../core/services/entries.service';
import { SearchService } from '../../core/services/search.service';

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
            <mat-card-title>
              {{ getTitle() }}
              <button mat-icon-button (click)="editEntry()" title="Edit Entry" class="edit-button">
                <mat-icon>edit</mat-icon>
              </button>
            </mat-card-title>
          </mat-card-header>
          <mat-card-content>
            <div *ngIf="isDream()">
              <div class="section" *ngIf="entry.plot">
                <h4>Plot:</h4>
                <p>{{ entry.plot }}</p>
              </div>
              <div class="section" *ngIf="entry.cast">
                <h4>Cast:</h4>
                <p>{{ entry.cast }}</p>
              </div>
              <div class="section" *ngIf="entry.location">
                <h4>Location:</h4>
                <p>{{ entry.location }}</p>
              </div>
              <div class="section" *ngIf="entry.period">
                <h4>Period:</h4>
                <p>{{ entry.period }}</p>
              </div>
              <div class="section" *ngIf="entry.emotion">
                <h4>Emotion:</h4>
                <p>{{ entry.emotion }}</p>
              </div>
              <div class="section" *ngIf="entry.symbols_and_imagery">
                <h4>Symbols and Imagery:</h4>
                <p>{{ entry.symbols_and_imagery }}</p>
              </div>
              <div class="section" *ngIf="entry.insight">
                <h4>Insight:</h4>
                <p>{{ entry.insight }}</p>
              </div>
              <div class="section" *ngIf="entry.action">
                <h4>Action:</h4>
                <p>{{ entry.action }}</p>
              </div>
              <div class="section" *ngIf="entry.other">
                <h4>Other:</h4>
                <p>{{ entry.other }}</p>
              </div>
            </div>
            <div *ngIf="!isDream()">
              <p>{{ getUserContent() }}</p>
            </div>
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
            <div *ngIf="isDream()">
              <div class="section" *ngIf="entry.summary">
                <h4>Summary:</h4>
                <p>{{ entry.summary }}</p>
              </div>
              <div class="section" *ngIf="entry.interpretation">
                <h4>Interpretation:</h4>
                <p>{{ entry.interpretation }}</p>
              </div>
            </div>
            <div *ngIf="!isDream()">
              <p>{{ entry.ai_response }}</p>
            </div>
          </mat-card-content>
        </mat-card>
      </div>
      
      <!-- Metadata bar -->
      <div class="metadata-bar">
        <div class="metadata-section">
          <h4>My Tags:</h4>
          <mat-chip-listbox>
            <mat-chip-option *ngFor="let tag of getTags()" 
                           (click)="searchForTag(tag)"
                           [class.clickable-chip]="true">
              {{ tag }}
            </mat-chip-option>
          </mat-chip-listbox>
        </div>
        
        <div class="metadata-section">
          <h4>Keywords:</h4>
          <mat-chip-listbox>
            <mat-chip-option *ngFor="let tag of getTagsArray()" 
                           (click)="searchForTag(tag)"
                           [class.clickable-chip]="true">
              {{ tag }}
            </mat-chip-option>
          </mat-chip-listbox>
        </div>
        
        <div class="metadata-section" *ngIf="getPeopleArray().length > 0">
          <h4>People:</h4>
          <mat-chip-listbox>
            <mat-chip-option *ngFor="let person of getPeopleArray()" 
                           (click)="searchForPerson(person)"
                           [class.clickable-chip]="true">
              <mat-icon>person</mat-icon>
              {{ person }}
            </mat-chip-option>
          </mat-chip-listbox>
        </div>
        
        <div class="metadata-section" *ngIf="getPlacesArray().length > 0">
          <h4>Places:</h4>
          <mat-chip-listbox>
            <mat-chip-option *ngFor="let place of getPlacesArray()" 
                           (click)="searchForPlace(place)"
                           [class.clickable-chip]="true">
              <mat-icon>place</mat-icon>
              {{ place }}
            </mat-chip-option>
          </mat-chip-listbox>
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

    .edit-button {
      float: right;
      margin-left: auto;
    }

    mat-card-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
    }

    .section {
      margin-bottom: var(--spacing-md);
    }

    .section h4 {
      margin: 0 0 var(--spacing-xs) 0;
      font-weight: 500;
    }

    .section p {
      margin: 0;
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
          color: #424242;
          font-weight: 500;
        }
        
        mat-chip-listbox {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
        }
        
        .clickable-chip {
          cursor: pointer;
          transition: all 0.2s ease;
          
          &:hover {
            background-color: #2196f3 !important;
            color: white !important;
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
          }
          
          mat-icon {
            font-size: 16px;
            width: 16px;
            height: 16px;
            margin-right: 4px;
          }
        }
      }
      
      .edit-button {
        margin-left: auto;
        color: #666;
        transition: color 0.2s ease;
        
        &:hover {
          color: #2196f3;
        }
      }
      
      mat-card-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
    }
  `]
})
export class DetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private entriesService = inject(EntriesService);
  private searchService = inject(SearchService);
  
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
  
  getTagsArray(): string[] {
    return this.getTags();
  }
  
  getPeopleNames(): string {
    return this.isDream() ? this.entry.dream_people_names || '' : this.entry.daily_people_names || '';
  }
  
  getPeopleArray(): string[] {
    const peopleStr = this.isDream() ? this.entry.dream_people_names : this.entry.daily_people_names;
    return peopleStr ? peopleStr.split(',').map((p: string) => p.trim()).filter((p: string) => p) : [];
  }
  
  getPlacesArray(): string[] {
    const placesStr = this.isDream() ? this.entry.dream_places : this.entry.daily_places;
    return placesStr ? placesStr.split(',').map((p: string) => p.trim()).filter((p: string) => p) : [];
  }
  
  searchForTag(tag: string): void {
    this.router.navigate(['/entries'], { queryParams: { search: tag } });
  }
  
  searchForPerson(person: string): void {
    this.router.navigate(['/entries'], { queryParams: { search: person } });
  }
  
  searchForPlace(place: string): void {
    this.router.navigate(['/entries'], { queryParams: { search: place } });
  }

  editEntry(): void {
    if (!this.entry) return;
    
    // Navigate to create/edit page with entry ID for editing
    this.router.navigate(['/entries/create'], { 
      queryParams: { 
        type: this.entryType,
        id: this.entry.id 
      } 
    });
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
