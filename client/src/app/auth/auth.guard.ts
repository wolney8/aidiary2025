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
import { AuthService } from "../core/services/auth.service";

function requireAuthenticated(returnUrl: string): boolean | UrlTree {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  const queryParams: Record<string, string> = {
    returnUrl: returnUrl || "/entries",
  };
  if (authService.consumeSessionExpiredFlag()) {
    queryParams["reason"] = "session-expired";
  }

  return router.createUrlTree(["/login"], { queryParams });
}

export const authGuard: CanActivateFn = (
  _route: ActivatedRouteSnapshot,
  state: RouterStateSnapshot,
): boolean | UrlTree => {
  return requireAuthenticated(state.url || "/entries");
};

export const authMatchGuard: CanMatchFn = (
  _route,
  segments: UrlSegment[],
): boolean | UrlTree => {
  const segmentPath = segments.map((segment) => segment.path).join("/");
  return requireAuthenticated(segmentPath ? `/${segmentPath}` : "/entries");
};
