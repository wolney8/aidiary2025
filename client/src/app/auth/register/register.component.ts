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
    <div class="auth-container">
      <mat-card>
        <mat-card-header>
          <mat-card-title>Create Account</mat-card-title>
        </mat-card-header>
        
        <mat-card-content>
          <form (ngSubmit)="onSubmit()">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Username</mat-label>
              <input matInput [(ngModel)]="formData.username" name="username" required>
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="formData.password"
                name="password"
                required
              >
              <mat-hint>Use at least 10 characters.</mat-hint>
            </mat-form-field>

            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Confirm Password</mat-label>
              <input
                matInput
                type="password"
                [(ngModel)]="confirmPassword"
                name="confirmPassword"
                required
              >
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>First Name</mat-label>
              <input matInput [(ngModel)]="formData.first_name" name="first_name">
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Last Name</mat-label>
              <input matInput [(ngModel)]="formData.last_name" name="last_name">
            </mat-form-field>
            
            <button
              mat-raised-button
              color="primary"
              type="submit"
              class="full-width"
              [disabled]="submitting"
            >
              {{ submitting ? "Creating account..." : "Register" }}
            </button>
          </form>

          <p class="status error" *ngIf="errorMessage">{{ errorMessage }}</p>
          
          <p class="login-link">
            Already have an account? <a routerLink="/login">Login here</a>
          </p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .auth-container {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      background: #f5f5f5;
    }
    
    mat-card {
      max-width: 400px;
      width: 100%;
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
      color: #c62828;
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

    if (this.formData.password.length < 10) {
      this.errorMessage = 'Password must be at least 10 characters.';
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
