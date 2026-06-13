// Authentication service for JWT management
import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable, BehaviorSubject, tap } from "rxjs";
import { Router } from "@angular/router";
import {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  User,
} from "../models/user.model";

@Injectable({
  providedIn: "root",
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private apiUrl = "http://localhost:5001/api";
  private tokenKey = "ai_diary_token";
  private userKey = "ai_diary_user";
  private currentUserSubject = new BehaviorSubject<User | null>(null);

  currentUser$ = this.currentUserSubject.asObservable();

  constructor() {
    const storedUser = localStorage.getItem(this.userKey);
    if (storedUser) {
      this.currentUserSubject.next(JSON.parse(storedUser));
    }
  }

  login(credentials: LoginRequest): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.apiUrl}/login`, credentials)
      .pipe(
        tap((response) => {
          localStorage.setItem(this.tokenKey, response.token);
          localStorage.setItem(this.userKey, JSON.stringify(response.user));
          this.currentUserSubject.next(response.user);
        }),
      );
  }

  register(data: RegisterRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/register`, data).pipe(
      tap((response) => {
        localStorage.setItem(this.tokenKey, response.token);
        localStorage.setItem(this.userKey, JSON.stringify(response.user));
        this.currentUserSubject.next(response.user);
      }),
    );
  }

  logout(): void {
    this.clearSession();
    this.router.navigate(["/login"]);
  }

  handleSessionExpired(): void {
    this.clearSession();

    const currentPath = this.router.url.split("?")[0];
    if (currentPath === "/login" || currentPath === "/register") {
      return;
    }

    this.router.navigate(["/login"], {
      queryParams: { reason: "session-expired" },
      replaceUrl: true,
    });
  }

  private clearSession(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
    this.currentUserSubject.next(null);
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  syncCurrentUser(user: User): void {
    localStorage.setItem(this.userKey, JSON.stringify(user));
    this.currentUserSubject.next(user);
  }

  getCurrentUser(): User | null {
    return this.currentUserSubject.value;
  }
}
