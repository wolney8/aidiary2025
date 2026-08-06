// Route guard to protect authenticated views
import { inject } from "@angular/core";
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
          profile.onboarding_completed === false &&
          returnUrl.split("?")[0] !== "/onboarding"
        ) {
          return router.createUrlTree(["/onboarding"], {
            queryParams: { returnUrl },
          });
        }
        return true;
      }),
      catchError(() => {
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
