// Application routing configuration
import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: '/entries', pathMatch: 'full' },
  { path: 'login', loadComponent: () => import('./auth/login/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./auth/register/register.component').then(m => m.RegisterComponent) },
  { path: 'entries', loadComponent: () => import('./entries/list/list.component').then(m => m.ListComponent) },
  { path: 'entries/create', loadComponent: () => import('./entries/create/create.component').then(m => m.CreateComponent) },
  { path: 'entries/:id', loadComponent: () => import('./entries/detail/detail.component').then(m => m.DetailComponent) },
  { path: 'profile', loadComponent: () => import('./profile/profile.component').then(m => m.ProfileComponent) }
];