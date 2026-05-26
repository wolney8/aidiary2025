import { Component, HostListener, inject, ViewChild, ElementRef, OnInit, OnDestroy } from '@angular/core';
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
import { MatSelectModule } from '@angular/material/select';
import { MatDialog } from '@angular/material/dialog';
import { COMMA, ENTER } from '@angular/cdk/keycodes';
import { debounceTime, Subject, takeUntil } from 'rxjs';
import { EntriesService } from '../../core/services/entries.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { ConfirmDialogComponent, ConfirmDialogData } from '../../shared/components/confirm-dialog/confirm-dialog.component';
import { DailyAnalysisResponse, DreamAnalysisResponse, MoodOption, AIStyleOption, DreamFieldOptions } from '../../core/models/entry.model';

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
    MatIconModule,
    MatSelectModule
  ],
  providers: [
    { provide: MAT_DATE_LOCALE, useValue: 'en-GB' },
    { provide: MAT_DATE_FORMATS, useValue: UK_DATE_FORMATS }
  ],
  templateUrl: './create.component.html',
  styleUrls: ['./create.component.scss', './edit-layout.scss'],
})
export class CreateComponent implements OnInit, OnDestroy {
  private router = inject(Router);
  private route = inject(ActivatedRoute);
  private entriesService = inject(EntriesService);
  private analysisService = inject(AnalysisService);
  private dialog = inject(MatDialog);
  @ViewChild('fileInput') fileInput?: ElementRef<HTMLInputElement>;

  private destroy$ = new Subject<void>();
  private autosaveSubject = new Subject<void>();

  entryDate: Date | null = new Date();
  entryTitle = '';
  content = '';
  tags: string[] = [];
  leaveItToAI = false;
  selectedType: 'daily' | 'dream' = 'daily';
  isSaving = false;
  errorMessage = '';
  maxDate = new Date();
  isEditing = false;
  editingId: number | null = null;

  // Enhanced fields for both entry types
  selectedMood = '';
  selectedAIStyle = 'friendly';

  // Dream-specific fields matching database schema
  dreamCast = '';
  dreamLocation = '';
  dreamPeriod = '';
  dreamEmotion = '';
  dreamPlot = '';
  dreamSymbolsAndImagery = '';
  dreamInsight = '';
  dreamAction = '';
  dreamOther = '';

  // New properties for wireframe layout
  autosaveStatus: 'idle' | 'saving' | 'saved' | 'error' = 'idle';
  heroImageUrl = '';
  heroImageExpanded = false; // Changed from heroImageCollapsed
  hasAIResponse = false;
  aiResponseData: any = null;
  lastAutosaveTime: Date | null = null;
  hasAutosavedChanges = false;

  readonly separatorKeysCodes = [ENTER, COMMA] as const;
  private initialDate = this.entryDate?.toDateString() ?? '';
  private originalFormState: any = null;

  // Mood options for both entry types
  moodOptions: MoodOption[] = [
    { emoji: '😊', label: 'Happy', value: 'happy' },
    { emoji: '😔', label: 'Sad', value: 'sad' },
    { emoji: '😴', label: 'Tired', value: 'tired' },
    { emoji: '😰', label: 'Anxious', value: 'anxious' },
    { emoji: '😡', label: 'Angry', value: 'angry' },
    { emoji: '🤔', label: 'Thoughtful', value: 'thoughtful' },
    { emoji: '😌', label: 'Peaceful', value: 'peaceful' },
    { emoji: '🤗', label: 'Grateful', value: 'grateful' },
    { emoji: '😕', label: 'Confused', value: 'confused' },
    { emoji: '💪', label: 'Energetic', value: 'energetic' }
  ];

  // AI style options for both entry types
  aiStyleOptions: AIStyleOption[] = [
    { label: 'Friendly & Supportive', value: 'friendly', description: 'Warm, encouraging responses' },
    { label: 'Professional & Clinical', value: 'clinical', description: 'Structured, therapeutic approach' },
    { label: 'Reflective & Deep', value: 'reflective', description: 'Thoughtful, introspective analysis' },
    { label: 'Brief & Practical', value: 'brief', description: 'Concise, actionable insights' },
    { label: 'Creative & Symbolic', value: 'creative', description: 'Metaphorical, artistic interpretation' }
  ];

  // Dream field options with common values
  dreamFieldOptions: DreamFieldOptions = {
    emotions: [
      'Joy', 'Fear', 'Anger', 'Sadness', 'Surprise', 'Disgust', 
      'Love', 'Anxiety', 'Excitement', 'Confusion', 'Peace', 'Frustration'
    ],
    periods: [
      'Childhood', 'Teenage years', 'Present day', 'Future', 'Past life', 
      'Medieval times', 'Victorian era', 'Ancient times', 'Dystopian future', 'Timeless'
    ]
  };

  ngOnInit(): void {
    // Set up autosave with debounce
    this.autosaveSubject
      .pipe(
        debounceTime(5000), // 5 second delay
        takeUntil(this.destroy$)
      )
      .subscribe(() => {
        if (this.isEditing && this.hasUnsavedChanges()) {
          this.performAutosave();
        }
      });

    // Update time display every 10 seconds
    setInterval(() => {
      if (this.lastAutosaveTime) {
        // Trigger change detection for time updates
      }
    }, 10000);

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

      // Check for edit ID parameter
      const idParam = params.get('id');
      if (idParam) {
        this.isEditing = true;
        this.editingId = Number(idParam);
        this.loadEntryForEditing(this.editingId);
      }
    });

    // Store initial form state after loading
    setTimeout(() => this.storeOriginalFormState(), 100);
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadEntryForEditing(id: number): void {
    // Try loading as daily first
    this.entriesService.getDailyEntry(id).subscribe({
      next: entry => {
        this.populateForm(entry, 'daily');
      },
      error: () => {
        this.entriesService.getDreamEntry(id).subscribe(entry => {
          this.populateForm(entry, 'dream');
        });
      }
    });
  }

  populateForm(entry: any, type: 'daily' | 'dream'): void {
    this.selectedType = type;
    this.entryDate = new Date(entry.entry_date);
    this.entryTitle = entry.title || '';
    this.tags = entry.tags ? entry.tags.split(',').map((t: string) => t.trim()).filter((t: string) => t) : [];
    this.selectedMood = entry.mood || '';
    this.selectedAIStyle = entry.ai_style || 'friendly';

    // Check if there's AI response data
    if (entry.ai_analysis || entry.ai_interpretation) {
      this.hasAIResponse = true;
      this.aiResponseData = {
        analysis: entry.ai_analysis,
        interpretation: entry.ai_interpretation,
        keywords: entry.ai_keywords ? entry.ai_keywords.split(',').map((k: string) => k.trim()).filter((k: string) => k) : [],
        people: entry.ai_people ? entry.ai_people.split(',').map((p: string) => p.trim()).filter((p: string) => p) : []
      };
    }

    if (type === 'daily') {
      this.content = entry.user_message || '';
    } else {
      this.dreamCast = entry.cast || '';
      this.dreamLocation = entry.location || '';
      this.dreamPeriod = entry.period || '';
      this.dreamEmotion = entry.emotion || '';
      this.dreamPlot = entry.plot || '';
      this.dreamSymbolsAndImagery = entry.symbols_and_imagery || '';
      this.dreamInsight = entry.insight || '';
      this.dreamAction = entry.action || '';
      this.dreamOther = entry.other || '';
    }
  }

  saveAsDraft(): void {
    this.persistEntry(this.leaveItToAI);
  }

  saveAndAnalyse(): void {
    this.persistEntry(true);
  }

  private persistEntry(shouldAnalyse: boolean, callback?: () => void): void {
    this.errorMessage = '';

    if (!this.entryDate) {
      this.errorMessage = 'Please select a date for this entry.';
      return;
    }

    // Content validation - required for daily entries, optional for dreams
    if (this.selectedType === 'daily' && !this.content.trim()) {
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
        tags,
        mood: this.selectedMood,
        ai_style: this.selectedAIStyle
      };

      if (this.isEditing && this.editingId) {
        // Update existing entry
        this.entriesService.updateDailyEntry(this.editingId, payload).subscribe({
          next: () => {
            if (callback) {
              callback();
            } else if (shouldAnalyse) {
              this.runDailyAnalysis(this.editingId!);
            } else {
              this.finishNavigation(this.editingId!);
            }
          },
          error: () => this.handleError('Failed to update your daily entry.')
        });
      } else {
        // Create new entry
        this.entriesService.createDailyEntry(payload).subscribe({
          next: (created) => {
            if (callback) {
              callback();
            } else if (shouldAnalyse) {
              this.runDailyAnalysis(created.id!);
            } else {
              this.finishNavigation(created.id!);
            }
          },
          error: () => this.handleError('Failed to save your daily entry.')
        });
      }
    } else {
      // For dreams, use dreamPlot instead of content
      const dreamPlotContent = this.dreamPlot.trim() || 'Dream entry';
      
      const payload = {
        entry_date: entryDate,
        title: trimmedTitle,
        plot: dreamPlotContent,
        tags,
        mood: this.selectedMood,
        ai_style: this.selectedAIStyle,
        cast: this.dreamCast.trim(),
        location: this.dreamLocation.trim(),
        period: this.dreamPeriod.trim(),
        emotion: this.dreamEmotion.trim(),
        symbols_and_imagery: this.dreamSymbolsAndImagery.trim(),
        insight: this.dreamInsight.trim(),
        action: this.dreamAction.trim(),
        other: this.dreamOther.trim()
      };

      if (this.isEditing && this.editingId) {
        // Update existing dream entry
        this.entriesService.updateDreamEntry(this.editingId, payload).subscribe({
          next: () => {
            if (callback) {
              callback();
            } else if (shouldAnalyse) {
              this.runDreamAnalysis(this.editingId!);
            } else {
              this.finishNavigation(this.editingId!);
            }
          },
          error: () => this.handleError('Failed to update your dream entry.')
        });
      } else {
        // Create new dream entry
        this.entriesService.createDreamEntry(payload).subscribe({
          next: (created) => {
            if (callback) {
              callback();
            } else if (shouldAnalyse) {
              this.runDreamAnalysis(created.id!);
            } else {
              this.finishNavigation(created.id!);
            }
          },
          error: () => this.handleError('Failed to save your dream entry.')
        });
      }
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
          daily_people_names: dailyAnalysis.daily_people_names,
          daily_places: dailyAnalysis.daily_places
        }).subscribe({
          next: () => this.finishNavigation(entryId),
          error: () => this.handleError('Saving AI insights failed. Please try again.')
        });
      },
      error: () => this.handleError('AI analysis failed. Please try again later.')
    });
  }

  private runDreamAnalysis(entryId: number): void {
    // For dream analysis, use the plot field or combine dream fields
    const analysisText = this.dreamPlot.trim() || 
      `Cast: ${this.dreamCast} Location: ${this.dreamLocation} Plot: ${this.dreamPlot} Emotion: ${this.dreamEmotion}`;
    
    this.analysisService.analyseText({
      mode: 'dream',
      text: analysisText
    }).subscribe({
      next: (analysis) => {
        const dreamAnalysis = analysis as DreamAnalysisResponse;
        this.entriesService.updateDreamEntry(entryId, {
          summary: dreamAnalysis.summary,
          interpretation: dreamAnalysis.interpretation,
          image_prompt: dreamAnalysis.image_prompt,
          tags: this.tags.length ? this.tags.join(',') : dreamAnalysis.tags,
          dream_people_names: dreamAnalysis.dream_people_names,
          dream_places: dreamAnalysis.dream_places
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
    if (!this.hasUnsavedChanges() && !this.hasAutosavedChanges) {
      // No changes, navigate back immediately
      this.router.navigate(['/entries']);
      return;
    }

    // Show confirmation dialog for unsaved changes
    const dialogData: ConfirmDialogData = {
      title: 'Unsaved Changes',
      message: 'You have unsaved changes that are stored in your session. What would you like to do?',
      confirmText: 'Save & Leave',
      cancelText: 'Keep Editing',
      hasUnsavedChanges: true
    };

    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '400px',
      maxWidth: '90vw',
      data: dialogData,
      disableClose: true,
      autoFocus: false,
      restoreFocus: false,
      panelClass: 'custom-dialog-container'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result === 'save') {
        // Save and then navigate
        this.persistEntry(false, () => {
          this.router.navigate(['/entries']);
        });
      } else if (result === false) {
        // Continue editing - do nothing, stay on page
        return;
      }
      // If result is true (confirm without save), just navigate
      if (result === true) {
        this.clearAutosaveData();
        this.router.navigate(['/entries']);
      }
    });
  }

  addTag(event: MatChipInputEvent): void {
    const value = (event.value || '').trim();
    if (value && !this.tags.includes(value)) {
      this.tags.push(value);
      if (this.isEditing) {
        this.onContentChange();
      }
    }
    event.chipInput?.clear();
  }

  removeTag(tag: string | number): void {
    if (typeof tag === 'string') {
      this.tags = this.tags.filter(t => t !== tag);
    } else {
      this.tags.splice(tag, 1);
    }
    if (this.isEditing) {
      this.onContentChange();
    }
  }

  onTypeChange() {
    // Clear content when switching between types to avoid confusion
    this.content = '';
    this.tags = [];
    
    // Reset dream-specific fields when switching away from dream type
    if (this.selectedType !== 'dream') {
      this.resetDreamFields();
    }
  }

  private resetDreamFields() {
    this.dreamCast = '';
    this.dreamLocation = '';
    this.dreamPeriod = '';
    this.dreamEmotion = '';
    this.dreamPlot = '';
    this.dreamSymbolsAndImagery = '';
    this.dreamInsight = '';
    this.dreamAction = '';
    this.dreamOther = '';
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
    // Always return true - we handle confirmations via our modal in cancelCreate()
    return true;
  }

  @HostListener('window:beforeunload', ['$event'])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    // Completely disable browser warning - we handle this with our modal
    // Don't set event.returnValue or call preventDefault
    return;
  }

  private hasUnsavedChanges(): boolean {
    if (!this.originalFormState) {
      // If no original state, check if any content exists
      const hasBasicChanges = Boolean(
        (this.entryTitle && this.entryTitle.trim()) ||
        (this.content && this.content.trim()) ||
        this.tags.length ||
        this.selectedMood ||
        this.selectedAIStyle !== 'friendly' ||
        (this.entryDate && this.entryDate.toDateString() !== this.initialDate)
      );

      const hasDreamChanges = this.selectedType === 'dream' && Boolean(
        this.dreamCast.trim() ||
        this.dreamLocation.trim() ||
        this.dreamPeriod.trim() ||
        this.dreamEmotion.trim() ||
        this.dreamPlot.trim() ||
        this.dreamSymbolsAndImagery.trim() ||
        this.dreamInsight.trim() ||
        this.dreamAction.trim() ||
        this.dreamOther.trim()
      );

      return hasBasicChanges || hasDreamChanges;
    }

    // Compare current state with original for edit mode
    return (
      this.entryTitle !== this.originalFormState.entryTitle ||
      this.content !== this.originalFormState.content ||
      this.dreamCast !== this.originalFormState.dreamCast ||
      this.dreamLocation !== this.originalFormState.dreamLocation ||
      this.dreamEmotion !== this.originalFormState.dreamEmotion ||
      this.dreamPlot !== this.originalFormState.dreamPlot ||
      this.selectedMood !== this.originalFormState.selectedMood ||
      JSON.stringify(this.tags) !== JSON.stringify(this.originalFormState.tags)
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
    this.selectedMood = '';
    this.selectedAIStyle = 'friendly';
    this.resetDreamFields();
  }

  // New methods for wireframe functionality
  onContentChange(): void {
    if (this.isEditing) {
      this.autosaveSubject.next(); // Trigger autosave timer
    }
  }

  private storeOriginalFormState(): void {
    this.originalFormState = {
      entryTitle: this.entryTitle,
      content: this.content,
      dreamCast: this.dreamCast,
      dreamLocation: this.dreamLocation,
      dreamEmotion: this.dreamEmotion,
      dreamPlot: this.dreamPlot,
      tags: [...this.tags],
      selectedMood: this.selectedMood
    };
  }

  private performAutosave(): void {
    // Don't set isSaving - this is just a session save, not a real save
    this.autosaveStatus = 'saving';
    
    // Create a temporary save (in-memory or session storage)
    const currentState = {
      entryTitle: this.entryTitle,
      content: this.content,
      dreamCast: this.dreamCast,
      dreamLocation: this.dreamLocation,
      dreamEmotion: this.dreamEmotion,
      dreamPlot: this.dreamPlot,
      tags: [...this.tags],
      selectedMood: this.selectedMood,
      timestamp: new Date().toISOString()
    };
    
    // Store in session storage for persistence across page refreshes
    sessionStorage.setItem(`autosave_${this.editingId}`, JSON.stringify(currentState));
    
    setTimeout(() => {
      this.autosaveStatus = 'saved';
      this.lastAutosaveTime = new Date();
      this.hasAutosavedChanges = true;
    }, 500); // Faster feedback
  }

  toggleHeroImageSection(): void {
    this.heroImageExpanded = !this.heroImageExpanded;
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event): void {
    // Close hero image if clicking outside and it's expanded
    if (this.heroImageExpanded) {
      const target = event.target as HTMLElement;
      const heroSection = document.querySelector('.hero-image-section');
      
      if (heroSection && !heroSection.contains(target)) {
        this.heroImageExpanded = false;
      }
    }
  }

  getCurrentAIResponse(): string {
    if (!this.aiResponseData) return '';
    
    if (this.selectedType === 'daily') {
      return this.aiResponseData.analysis || '';
    } else {
      return this.aiResponseData.interpretation || '';
    }
  }

  getAIKeywords(): string[] {
    if (!this.aiResponseData) return [];
    return this.aiResponseData.keywords || [];
  }

  getAIPeople(): string[] {
    if (!this.aiResponseData) return [];
    return this.aiResponseData.people || [];
  }

  regenerateAIResponse(): void {
    if (!this.hasAIResponse || !this.editingId) return;
    
        
    // Implement AI response regeneration
    console.log('Regenerating AI response for entry:', this.editingId);
  }

  saveAndStay(): void {
    // Manual autosave - doesn't confirm changes, just saves to session
    this.performAutosave();
  }

  saveAndView(): void {
    // Actually save to database and navigate to view entry page
    if (this.isEditing && this.editingId) {
      // This will set isSaving and disable buttons during actual save
      this.persistEntry(false, () => {
        this.clearAutosaveData();
        this.router.navigate(['/entries', this.editingId]);
      });
    }
  }

  private clearAutosaveData(): void {
    if (this.editingId) {
      sessionStorage.removeItem(`autosave_${this.editingId}`);
    }
    this.hasAutosavedChanges = false;
    this.autosaveStatus = 'idle';
  }

  formatAutosaveTime(): string {
    if (!this.lastAutosaveTime) return '';
    const now = new Date();
    const diff = Math.floor((now.getTime() - this.lastAutosaveTime.getTime()) / 1000);
    
    if (diff < 10) return 'just now';
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minute${Math.floor(diff / 60) !== 1 ? 's' : ''} ago`;
    return `${Math.floor(diff / 3600)} hour${Math.floor(diff / 3600) !== 1 ? 's' : ''} ago`;
  }
}
