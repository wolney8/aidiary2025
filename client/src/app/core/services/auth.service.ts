// Authentication service for JWT management
import { Injectable, inject } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable, BehaviorSubject, tap } from "rxjs";
import { Router } from "@angular/router";
import {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  AuthMessageResponse,
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
  private tokenKey = "openmynd_token";
  private legacyTokenKey = "ai_diary_token";
  private userKey = "openmynd_user";
  private legacyUserKey = "ai_diary_user";
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  private sessionExpiredSinceLastCheck = false;

  currentUser$ = this.currentUserSubject.asObservable();

  constructor() {
    this.migrateLegacySession();
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
          this.storeSession(response);
          this.currentUserSubject.next(response.user);
        }),
      );
  }

  register(data: RegisterRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/register`, data).pipe(
      tap((response) => {
        this.sessionExpiredSinceLastCheck = false;
        this.storeSession(response);
        this.currentUserSubject.next(response.user);
      }),
    );
  }

  requestEmailVerification(): Observable<AuthMessageResponse> {
    return this.http.post<AuthMessageResponse>(
      `${this.apiUrl}/auth/email/verification/request`,
      {},
    );
  }

  confirmEmailVerification(token: string): Observable<AuthMessageResponse> {
    return this.http.post<AuthMessageResponse>(
      `${this.apiUrl}/auth/email/verification/confirm`,
      { token },
    );
  }

  requestPasswordReset(email: string): Observable<AuthMessageResponse> {
    return this.http.post<AuthMessageResponse>(
      `${this.apiUrl}/auth/password-reset/request`,
      { email },
    );
  }

  confirmPasswordReset(token: string, password: string): Observable<AuthMessageResponse> {
    return this.http.post<AuthMessageResponse>(
      `${this.apiUrl}/auth/password-reset/confirm`,
      { token, password },
    );
  }

  getOAuthProviders(): Observable<OAuthProvidersResponse> {
    return this.http.get<OAuthProvidersResponse>(`${this.apiUrl}/oauth/providers`);
  }

  completeOAuthLogin(response: AuthResponse): void {
    this.sessionExpiredSinceLastCheck = false;
    this.storeSession(response);
    this.currentUserSubject.next(response.user);
  }

  clearLocalSession(): void {
    this.sessionExpiredSinceLastCheck = false;
    this.clearSession();
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

  logout(options: { reason?: string; replaceUrl?: boolean } = {}): void {
    this.clearSession();
    this.router.navigate(["/login"], {
      queryParams: options.reason ? { reason: options.reason } : undefined,
      replaceUrl: Boolean(options.replaceUrl),
    });
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

  handleOnboardingRequired(returnUrl = this.router.url || "/dashboard"): void {
    const safeReturnUrl =
      returnUrl.startsWith("/") &&
      !returnUrl.startsWith("//") &&
      !returnUrl.includes("://") &&
      !["/login", "/register", "/oauth/callback", "/onboarding"].includes(
        returnUrl.split("?")[0],
      )
        ? returnUrl
        : "/dashboard";

    this.router.navigate(["/onboarding"], {
      queryParams: { returnUrl: safeReturnUrl },
      replaceUrl: true,
    });
  }

  handleAccountRestricted(): void {
    if (this.router.url.split("?")[0] === "/account-restricted") {
      return;
    }
    this.router.navigate(["/account-restricted"], {
      replaceUrl: true,
    });
  }

  private clearSession(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.legacyTokenKey);
    localStorage.removeItem(this.userKey);
    localStorage.removeItem(this.legacyUserKey);
    this.currentUserSubject.next(null);
  }

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey) ?? localStorage.getItem(this.legacyTokenKey);
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
    localStorage.removeItem(this.legacyUserKey);
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

  private storeSession(response: AuthResponse): void {
    localStorage.setItem(this.tokenKey, response.token);
    localStorage.setItem(this.userKey, JSON.stringify(response.user));
    localStorage.removeItem(this.legacyTokenKey);
    localStorage.removeItem(this.legacyUserKey);
  }

  private migrateLegacySession(): void {
    const legacyToken = localStorage.getItem(this.legacyTokenKey);
    const legacyUser = localStorage.getItem(this.legacyUserKey);
    if (legacyToken && !localStorage.getItem(this.tokenKey)) {
      localStorage.setItem(this.tokenKey, legacyToken);
    }
    if (legacyUser && !localStorage.getItem(this.userKey)) {
      localStorage.setItem(this.userKey, legacyUser);
    }
    if (legacyToken || legacyUser) {
      localStorage.removeItem(this.legacyTokenKey);
      localStorage.removeItem(this.legacyUserKey);
    }
  }
}
