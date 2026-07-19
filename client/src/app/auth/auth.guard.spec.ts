import { TestBed } from "@angular/core/testing";
import {
  ActivatedRouteSnapshot,
  provideRouter,
  Router,
  RouterStateSnapshot,
  UrlTree,
} from "@angular/router";
import { authGuard } from "./auth.guard";
import { AuthService } from "../core/services/auth.service";

describe("authGuard", () => {
  let router: Router;
  let isAuthenticated = false;
  let authServiceMock: {
    isAuthenticated: () => boolean;
    consumeSessionExpiredFlag: () => boolean;
  };
  let sessionExpired = false;

  beforeEach(() => {
    isAuthenticated = false;
    sessionExpired = false;

    authServiceMock = {
      isAuthenticated: () => isAuthenticated,
      consumeSessionExpiredFlag: () => sessionExpired,
    };

    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authServiceMock },
      ],
    });

    router = TestBed.inject(Router);
  });

  it("allows navigation when authenticated", () => {
    isAuthenticated = true;

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/entries" } as RouterStateSnapshot,
      ),
    );

    expect(result).toBeTrue();
  });

  it("redirects to login with encoded returnUrl when logged out", () => {
    isAuthenticated = false;

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/entries?type=daily" } as RouterStateSnapshot,
      ),
    );

    expect(result instanceof UrlTree).toBeTrue();
    const redirectUrl = router.serializeUrl(result as UrlTree);
    expect(redirectUrl).toBe("/login?returnUrl=%2Fentries%3Ftype%3Ddaily");
  });

  it("includes a friendly reason when the stored session expired", () => {
    sessionExpired = true;

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/settings/personalisation" } as RouterStateSnapshot,
      ),
    );

    const redirectUrl = router.serializeUrl(result as UrlTree);
    expect(redirectUrl).toContain("returnUrl=%2Fsettings%2Fpersonalisation");
    expect(redirectUrl).toContain("reason=session-expired");
  });
});
