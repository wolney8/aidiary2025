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
  OAuthProvider,
  OAuthProvidersResponse,
} from "../models/user.model";
import { environment } from "../../../environments/environment";

@Injectable({
  providedIn: "root",
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private apiUrl = environment.apiBaseUrl;
  private tokenKey = "ai_diary_token";
  private userKey = "ai_diary_user";
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  private sessionExpiredSinceLastCheck = false;

  currentUser$ = this.currentUserSubject.asObservable();

  constructor() {
    const storedUser = localStorage.getItem(this.userKey);
    if (storedUser) {
      try {
        this.currentUserSubject.next(JSON.parse(storedUser));
      } catch {
        this.clearSession();
      }
    }
  }

  login(credentials: LoginRequest): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.apiUrl}/login`, credentials)
      .pipe(
        tap((response) => {
          this.sessionExpiredSinceLastCheck = false;
          localStorage.setItem(this.tokenKey, response.token);
          localStorage.setItem(this.userKey, JSON.stringify(response.user));
          this.currentUserSubject.next(response.user);
        }),
      );
  }

  register(data: RegisterRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/register`, data).pipe(
      tap((response) => {
        this.sessionExpiredSinceLastCheck = false;
        localStorage.setItem(this.tokenKey, response.token);
        localStorage.setItem(this.userKey, JSON.stringify(response.user));
        this.currentUserSubject.next(response.user);
      }),
    );
  }

  getOAuthProviders(): Observable<OAuthProvidersResponse> {
    return this.http.get<OAuthProvidersResponse>(`${this.apiUrl}/oauth/providers`);
  }

  completeOAuthLogin(response: AuthResponse): void {
    this.sessionExpiredSinceLastCheck = false;
    localStorage.setItem(this.tokenKey, response.token);
    localStorage.setItem(this.userKey, JSON.stringify(response.user));
    this.currentUserSubject.next(response.user);
  }

  getOAuthStartUrl(provider: OAuthProvider, returnUrl = "/dashboard"): string {
    if (!provider.start_url) {
      return "";
    }
    const apiRoot = this.apiUrl.replace(/\/api\/?$/, "");
    const url = new URL(provider.start_url, `${apiRoot}/`);
    url.searchParams.set("returnUrl", returnUrl);
    return url.toString();
  }

  logout(): void {
    this.clearSession();
    this.router.navigate(["/login"]);
  }

  handleSessionExpired(): void {
    this.sessionExpiredSinceLastCheck = true;
    this.clearSession();

    const currentUrl = this.router.url;
    const currentPath = currentUrl.split("?")[0];
    if (currentPath === "/login" || currentPath === "/register") {
      return;
    }

    this.router.navigate(["/login"], {
      queryParams: {
        reason: "session-expired",
        returnUrl: currentUrl || "/dashboard",
      },
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
    const token = this.getToken();
    if (!token) {
      return false;
    }

    if (this.isTokenExpiredOrInvalid(token)) {
      this.sessionExpiredSinceLastCheck = true;
      this.clearSession();
      return false;
    }

    return true;
  }

  consumeSessionExpiredFlag(): boolean {
    const wasExpired = this.sessionExpiredSinceLastCheck;
    this.sessionExpiredSinceLastCheck = false;
    return wasExpired;
  }

  syncCurrentUser(user: User): void {
    localStorage.setItem(this.userKey, JSON.stringify(user));
    this.currentUserSubject.next(user);
  }

  getCurrentUser(): User | null {
    return this.currentUserSubject.value;
  }

  private isTokenExpiredOrInvalid(token: string): boolean {
    try {
      const segments = token.split(".");
      if (segments.length !== 3) {
        return true;
      }

      const base64Url = segments[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
      const payload = JSON.parse(atob(padded)) as { exp?: unknown };

      return (
        typeof payload.exp !== "number" || payload.exp * 1000 <= Date.now()
      );
    } catch {
      return true;
    }
  }
}
