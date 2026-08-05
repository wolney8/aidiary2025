import { TestBed } from "@angular/core/testing";
import {
  ActivatedRouteSnapshot,
  provideRouter,
  Route,
  Router,
  RouterStateSnapshot,
  UrlSegment,
  UrlTree,
} from "@angular/router";
import { authGuard, authMatchGuard } from "./auth.guard";
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

  it("blocks route matching for protected lazy routes when logged out", () => {
    isAuthenticated = false;

    const result = TestBed.runInInjectionContext(() =>
      authMatchGuard(
        { path: "settings" } as Route,
        [new UrlSegment("settings", {}), new UrlSegment("import", {})],
      ),
    );

    expect(result instanceof UrlTree).toBeTrue();
    const redirectUrl = router.serializeUrl(result as UrlTree);
    expect(redirectUrl).toBe("/login?returnUrl=%2Fsettings%2Fimport");
  });

  it("uses dashboard as the protected-route fallback return target", () => {
    isAuthenticated = false;

    const result = TestBed.runInInjectionContext(() =>
      authMatchGuard({ path: "" } as Route, []),
    );

    expect(result instanceof UrlTree).toBeTrue();
    const redirectUrl = router.serializeUrl(result as UrlTree);
    expect(redirectUrl).toBe("/login?returnUrl=%2Fdashboard");
  });

  it("allows route matching when authenticated", () => {
    isAuthenticated = true;

    const result = TestBed.runInInjectionContext(() =>
      authMatchGuard({ path: "entries" } as Route, [
        new UrlSegment("entries", {}),
      ]),
    );

    expect(result).toBeTrue();
  });
});
