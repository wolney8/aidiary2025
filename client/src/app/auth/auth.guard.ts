// Route guard to protect authenticated views
import { inject } from "@angular/core";
import {
  ActivatedRouteSnapshot,
  CanActivateFn,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from "@angular/router";
import { AuthService } from "../core/services/auth.service";

export const authGuard: CanActivateFn = (
  _route: ActivatedRouteSnapshot,
  state: RouterStateSnapshot,
): boolean | UrlTree => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  const queryParams: Record<string, string> = {
    returnUrl: state.url || "/entries",
  };
  if (authService.consumeSessionExpiredFlag()) {
    queryParams["reason"] = "session-expired";
  }

  return router.createUrlTree(["/login"], { queryParams });
};
