// Application routing configuration
import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: '/login', pathMatch: 'full' },
  { path: 'login', loadComponent: () => import('./auth/login/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./auth/register/register.component').then(m => m.RegisterComponent) },
  {
    path: 'entries',
    canActivate: [() => import('./auth/auth.guard').then(m => m.authGuard)],
    loadComponent: () => import('./entries/list/list.component').then(m => m.ListComponent)
  },
  {
    path: 'entries/create',
    canActivate: [() => import('./auth/auth.guard').then(m => m.authGuard)],
    loadComponent: () => import('./entries/create/create.component').then(m => m.CreateComponent)
  },
  {
    path: 'entries/:id',
    canActivate: [() => import('./auth/auth.guard').then(m => m.authGuard)],
    loadComponent: () => import('./entries/detail/detail.component').then(m => m.DetailComponent)
  },
  {
    path: 'profile',
    canActivate: [() => import('./auth/auth.guard').then(m => m.authGuard)],
    loadComponent: () => import('./profile/profile.component').then(m => m.ProfileComponent)
  }
];
