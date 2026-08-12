import type {
  HttpInterceptorFn,
  HttpErrorResponse,
} from "@angular/common/http";
import { inject } from "@angular/core";
import { catchError, throwError } from "rxjs";
import { AuthService } from "../services/auth.service";
import { environment } from "../../../environments/environment";

const CSRF_COOKIE_NAME = "csrf_access_token";
const CSRF_HEADER_NAME = "X-CSRF-TOKEN";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function readCookie(name: string): string | null {
  if (typeof document === "undefined" || !document.cookie) {
    return null;
  }
  const prefix = `${encodeURIComponent(name)}=`;
  const match = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : null;
}

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const isAuthRequest = /\/(login|register)(\?|$)/.test(req.url);
  const isApiRequest =
    req.url.startsWith(environment.apiBaseUrl) ||
    req.url.startsWith(environment.apiFallbackBaseUrl) ||
    req.url.startsWith("/api/");
  const csrfToken =
    isApiRequest && UNSAFE_METHODS.has(req.method.toUpperCase())
      ? readCookie(CSRF_COOKIE_NAME)
      : null;
  const request = isApiRequest
    ? req.clone({
        withCredentials: true,
        setHeaders: csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {},
      })
    : req;

  return next(request).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !isAuthRequest) {
        authService.handleSessionExpired();
      }
      if (
        error.status === 403 &&
        !isAuthRequest &&
        error.error?.code === "onboarding_required"
      ) {
        authService.handleOnboardingRequired();
      }
      if (
        error.status === 403 &&
        !isAuthRequest &&
        error.error?.code === "account_restricted"
      ) {
        authService.handleAccountRestricted();
      }

      return throwError(() => error);
    }),
  );
};
