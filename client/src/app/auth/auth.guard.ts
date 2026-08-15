// Route guard to protect authenticated views
import { inject } from "@angular/core";
import {
  HttpErrorResponse,
} from "@angular/common/http";
import {
  ActivatedRouteSnapshot,
  CanActivateFn,
  CanMatchFn,
  Router,
  RouterStateSnapshot,
  UrlTree,
  UrlSegment,
} from "@angular/router";
import { Observable, catchError, map, of } from "rxjs";
import { AuthService } from "../core/services/auth.service";
import { ProfileService } from "../core/services/profile.service";

function loginRedirect(router: Router, authService: AuthService, returnUrl: string): UrlTree {
  const queryParams: Record<string, string> = {
    returnUrl: returnUrl || "/dashboard",
  };
  if (authService.consumeSessionExpiredFlag()) {
    queryParams["reason"] = "session-expired";
  }

  return router.createUrlTree(["/login"], { queryParams });
}

function serviceUnavailableRedirect(router: Router, returnUrl: string): UrlTree {
  return router.createUrlTree(["/login"], {
    queryParams: {
      reason: "service-unavailable",
      returnUrl: returnUrl || "/dashboard",
    },
  });
}

function isDatabaseServiceFailure(error: unknown): boolean {
  return (
    error instanceof HttpErrorResponse &&
    error.status >= 500 &&
    (error.error?.category === "database" ||
      error.error?.category === "connection" ||
      error.error?.category === "storage_or_quota" ||
      String(error.error?.code || "").startsWith("database_"))
  );
}

function requireAuthenticated(
  returnUrl: string,
  validateServerProfile = true,
): boolean | UrlTree | Observable<boolean | UrlTree> {
  const authService = inject(AuthService);
  const profileService = inject(ProfileService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    const currentUser = authService.getCurrentUser();
    if (
      currentUser?.account_status === "restricted" &&
      returnUrl.split("?")[0] !== "/account-restricted"
    ) {
      return router.createUrlTree(["/account-restricted"]);
    }

    if (
      currentUser?.onboarding_completed === false &&
      returnUrl.split("?")[0] !== "/onboarding"
    ) {
      return router.createUrlTree(["/onboarding"], {
        queryParams: { returnUrl },
      });
    }

    if (!validateServerProfile) {
      return true;
    }

    return profileService.getProfile().pipe(
      map((profile) => {
        if (
          profile.account_status === "restricted" &&
          returnUrl.split("?")[0] !== "/account-restricted"
        ) {
          return router.createUrlTree(["/account-restricted"]);
        }
        if (
          profile.onboarding_completed === false &&
          returnUrl.split("?")[0] !== "/onboarding"
        ) {
          return router.createUrlTree(["/onboarding"], {
            queryParams: { returnUrl },
          });
        }
        return true;
      }),
      catchError((error) => {
        if (isDatabaseServiceFailure(error)) {
          return of(serviceUnavailableRedirect(router, returnUrl));
        }
        authService.clearLocalSession();
        return of(loginRedirect(router, authService, returnUrl));
      }),
    );
  }

  return loginRedirect(router, authService, returnUrl);
}

export const authGuard: CanActivateFn = (
  _route: ActivatedRouteSnapshot,
  state: RouterStateSnapshot,
): boolean | UrlTree | Observable<boolean | UrlTree> => {
  return requireAuthenticated(state.url || "/dashboard");
};

export const authMatchGuard: CanMatchFn = (
  _route,
  segments: UrlSegment[],
): boolean | UrlTree | Observable<boolean | UrlTree> => {
  const segmentPath = segments.map((segment) => segment.path).join("/");
  return requireAuthenticated(segmentPath ? `/${segmentPath}` : "/dashboard", false);
};
