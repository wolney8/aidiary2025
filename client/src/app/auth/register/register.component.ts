// Registration component
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule
  ],
  template: `
    <div class="auth-container" data-testid="register-page">
      <mat-card class="auth-card">
        <mat-card-header>
          <h1 mat-card-title>Create Account</h1>
        </mat-card-header>
        
        <mat-card-content>
          <form (ngSubmit)="onSubmit()" [attr.aria-busy]="submitting">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Username</mat-label>
              <input
                matInput
                [(ngModel)]="formData.username"
                name="username"
                maxlength="32"
                autocomplete="username"
                required
              >
              <mat-hint>Use 3-32 letters, numbers, dots, underscores, or hyphens.</mat-hint>
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="formData.password"
                name="password"
                maxlength="128"
                autocomplete="new-password"
                required
              >
              <mat-hint>Use 8-128 characters with letters and numbers.</mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Confirm Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="confirmPassword"
                name="confirmPassword"
                autocomplete="new-password"
                required
              >
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>First Name</mat-label>
              <input
                matInput
                [(ngModel)]="formData.first_name"
                name="first_name"
                maxlength="12"
                autocomplete="given-name"
              >
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Last Name</mat-label>
              <input
                matInput
                [(ngModel)]="formData.last_name"
                name="last_name"
                maxlength="12"
                autocomplete="family-name"
              >
            </mat-form-field>
            
            <button
              mat-raised-button
              color="primary"
              type="submit"
              class="full-width"
              [disabled]="submitting"
              data-testid="register-submit"
            >
              {{ submitting ? "Creating account..." : "Register" }}
            </button>
          </form>

          <p class="status error" *ngIf="errorMessage" role="alert" data-testid="register-error">{{ errorMessage }}</p>
          
          <p class="login-link">
            Already have an account? <a routerLink="/login">Login here</a>
          </p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .auth-container {
      box-sizing: border-box;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      padding: var(--spacing-md);
      background: var(--colour-background);
    }
    
    mat-card {
      max-width: 400px;
      width: 100%;
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-surface-elevated);
      color: var(--colour-text-primary);
    }
    
    .full-width {
      width: 100%;
      margin-bottom: var(--spacing-sm);
    }
    
    .login-link {
      text-align: center;
      margin-top: var(--spacing-md);
    }

    .status {
      margin-top: var(--spacing-sm);
    }

    .error {
      padding: 12px;
      border: 1px solid var(--colour-danger-text);
      border-radius: var(--radius-md);
      background: var(--colour-danger-bg);
      color: var(--colour-danger-text);
    }
  `]
})
export class RegisterComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  
  formData = {
    username: '',
    password: '',
    first_name: '',
    last_name: ''
  };
  confirmPassword = '';
  submitting = false;
  errorMessage = '';
  
  onSubmit(): void {
    this.errorMessage = '';

    if (this.formData.password !== this.confirmPassword) {
      this.errorMessage = 'Password confirmation does not match.';
      return;
    }

    if (this.formData.password.length < 8 || this.formData.password.length > 128) {
      this.errorMessage = 'Password must be between 8 and 128 characters.';
      return;
    }

    if (!/[A-Za-z]/.test(this.formData.password) || !/[0-9]/.test(this.formData.password)) {
      this.errorMessage = 'Password must include letters and numbers.';
      return;
    }

    this.submitting = true;
    this.authService.register(this.formData).subscribe({
      next: () => this.router.navigate(['/entries']),
      error: err => {
        this.errorMessage =
          err?.error?.error || 'Registration failed. Please try again.';
        this.submitting = false;
      },
      complete: () => {
        this.submitting = false;
      }
    });
  }
}
