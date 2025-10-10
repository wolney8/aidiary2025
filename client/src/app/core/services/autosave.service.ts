import { Injectable } from '@angular/core';
import { Subject, debounceTime, distinctUntilChanged } from 'rxjs';

export type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'error';

@Injectable({
  providedIn: 'root'
})
export class AutosaveService {
  private autosaveSubject = new Subject<any>();
  private statusSubject = new Subject<AutosaveStatus>();
  
  status$ = this.statusSubject.asObservable();
  
  constructor() {
    // Set up autosave trigger with 5-second debounce
    this.autosaveSubject
      .pipe(
        debounceTime(5000),
        distinctUntilChanged((prev, curr) => JSON.stringify(prev) === JSON.stringify(curr))
      )
      .subscribe(data => {
        this.performAutosave(data);
      });
  }

  triggerAutosave(data: any): void {
    this.autosaveSubject.next(data);
  }

  private async performAutosave(data: any): Promise<void> {
    this.statusSubject.next('saving');
    
    try {
      // Here we would call the save API
      // For now, simulate save with a delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      this.statusSubject.next('saved');
      
      // Reset to idle after showing saved status
      setTimeout(() => {
        this.statusSubject.next('idle');
      }, 2000);
      
    } catch (error) {
      this.statusSubject.next('error');
      console.error('Autosave failed:', error);
    }
  }

  reset(): void {
    this.statusSubject.next('idle');
  }
}