import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  hasUnsavedChanges?: boolean;
}

@Component({
  selector: 'app-confirm-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <div class="confirm-dialog">
      <div class="dialog-header">
        <div class="header-content">
          <mat-icon class="warning-icon" *ngIf="data.hasUnsavedChanges">warning</mat-icon>
          <h2 mat-dialog-title>{{ data.title }}</h2>
        </div>
      </div>
      
      <mat-dialog-content>
        <p class="main-message">{{ data.message }}</p>
        <div class="info-section" *ngIf="data.hasUnsavedChanges">
          <div class="info-content">
            <mat-icon class="info-icon">info</mat-icon>
            <span>Your recent changes are preserved in this session and can be saved.</span>
          </div>
        </div>
      </mat-dialog-content>
      
      <mat-dialog-actions align="end">
        <button mat-button 
                [mat-dialog-close]="false" 
                class="cancel-button">
          {{ data.cancelText || 'Cancel' }}
        </button>
        <button mat-button 
                [mat-dialog-close]="true" 
                color="warn"
                *ngIf="data.hasUnsavedChanges">
          Discard Changes
        </button>
        <button mat-button 
                [mat-dialog-close]="true" 
                color="warn"
                *ngIf="!data.hasUnsavedChanges">
          {{ data.confirmText || 'Confirm' }}
        </button>
        <button mat-raised-button 
                [mat-dialog-close]="'save'" 
                color="primary"
                *ngIf="data.hasUnsavedChanges">
          {{ data.confirmText || 'Save & Leave' }}
        </button>
      </mat-dialog-actions>
    </div>
  `,
  styles: [`
    .confirm-dialog {
      max-width: 400px;
      min-width: 320px;
      padding: 0;
      overflow: hidden;
    }
    
    .dialog-header {
      padding: 24px 24px 20px 24px;
      border-bottom: 1px solid #e0e0e0;
    }
    
    .header-content {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    
    .warning-icon {
      color: #ff6f00;
      font-size: 24px;
      width: 24px;
      height: 24px;
      flex-shrink: 0;
    }
    
    h2 {
      margin: 0;
      font-size: 20px;
      font-weight: 500;
      color: #1f1f1f;
      line-height: 1.2;
    }
    
    mat-dialog-content {
      padding: 20px 24px 8px 24px;
      margin: 0;
      max-height: none;
      overflow: visible;
    }
    
    .main-message {
      margin: 0 0 16px 0;
      font-size: 14px;
      line-height: 1.5;
      color: #424242;
    }
    
    .info-section {
      margin: 0;
    }
    
    .info-content {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 12px 16px;
      background-color: #e8f5e8;
      border: 1px solid #c8e6c9;
      border-radius: 8px;
      border-left: 4px solid #4caf50;
    }
    
    .info-icon {
      color: #2e7d32;
      font-size: 20px;
      width: 20px;
      height: 20px;
      flex-shrink: 0;
      margin-top: 1px;
    }
    
    .info-content span {
      font-size: 13px;
      line-height: 1.4;
      color: #2e7d32;
    }
    
    mat-dialog-actions {
      padding: 16px 24px 24px 24px;
      gap: 8px;
      margin: 0;
      min-height: auto;
    }
    
    .cancel-button {
      color: #5f6368;
    }
    
    .cancel-button:hover {
      background-color: rgba(95, 99, 104, 0.04);
    }
    
    /* Remove scrollbar and ensure proper sizing */
    ::ng-deep .mat-mdc-dialog-container {
      max-height: 90vh;
      overflow: visible;
    }
    
    ::ng-deep .mat-mdc-dialog-surface {
      overflow: visible;
    }
  `]
})
export class ConfirmDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<ConfirmDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: ConfirmDialogData
  ) {}
}