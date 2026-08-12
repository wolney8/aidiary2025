import type {
  HttpInterceptorFn,
  HttpErrorResponse,
} from "@angular/common/http";
import { inject } from "@angular/core";
import { catchError, throwError } from "rxjs";
import { AuthService } from "../services/auth.service";
import { environment } from "../../../environments/environment";

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const isAuthRequest = /\/(login|register)(\?|$)/.test(req.url);
  const isApiRequest =
    req.url.startsWith(environment.apiBaseUrl) ||
    req.url.startsWith(environment.apiFallbackBaseUrl) ||
    req.url.startsWith("/api/");
  const request = isApiRequest && !req.withCredentials
    ? req.clone({ withCredentials: true })
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
