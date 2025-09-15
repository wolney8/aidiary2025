// Login component
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
  selector: 'app-login',
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
          <mat-card-title>Login to AI Diary</mat-card-title>
        </mat-card-header>
        
        <mat-card-content>
          <form (ngSubmit)="onSubmit()">
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Username</mat-label>
              <input matInput [(ngModel)]="credentials.username" name="username" required>
            </mat-form-field>
            
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Password</mat-label>
              <input matInput type="password" [(ngModel)]="credentials.password" name="password" required>
            </mat-form-field>
            
            <button mat-raised-button color="primary" type="submit" class="full-width">
              Login
            </button>
          </form>
          
          <p class="register-link">
            Don't have an account? <a routerLink="/register">Register here</a>
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
    
    .register-link {
      text-align: center;
      margin-top: var(--spacing-md);
    }
  `]
})
export class LoginComponent {
  private authService = inject(AuthService);
  private router = inject(Router);
  
  credentials = {
    username: '',
    password: ''
  };
  
  onSubmit(): void {
    this.authService.login(this.credentials).subscribe({
      next: () => this.router.navigate(['/entries']),
      error: err => console.error('Login failed:', err)
    });
  }
}