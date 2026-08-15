import { TestBed } from "@angular/core/testing";
import { HttpErrorResponse } from "@angular/common/http";
import {
  ActivatedRouteSnapshot,
  provideRouter,
  Route,
  Router,
  RouterStateSnapshot,
  UrlSegment,
  UrlTree,
} from "@angular/router";
import { firstValueFrom, isObservable, Observable, of, throwError } from "rxjs";
import { authGuard, authMatchGuard } from "./auth.guard";
import { AuthService } from "../core/services/auth.service";
import { ProfileService } from "../core/services/profile.service";

describe("authGuard", () => {
  let router: Router;
  let isAuthenticated = false;
  let authServiceMock: {
    isAuthenticated: () => boolean;
    consumeSessionExpiredFlag: () => boolean;
    getCurrentUser: () => { onboarding_completed?: boolean; account_status?: string } | null;
    clearLocalSession: () => void;
  };
  let profileServiceMock: {
    getProfile: () => Observable<{ onboarding_completed: boolean; account_status?: string }>;
  };
  let sessionExpired = false;

  beforeEach(() => {
    isAuthenticated = false;
    sessionExpired = false;

    authServiceMock = {
      isAuthenticated: () => isAuthenticated,
      consumeSessionExpiredFlag: () => sessionExpired,
      getCurrentUser: () => ({ onboarding_completed: true }),
      clearLocalSession: jasmine.createSpy("clearLocalSession"),
    };

    profileServiceMock = {
      getProfile: () => of({ onboarding_completed: true }),
    };

    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: authServiceMock },
        { provide: ProfileService, useValue: profileServiceMock },
      ],
    });

    router = TestBed.inject(Router);
  });

  async function resolveGuardResult(result: unknown): Promise<unknown> {
    if (isObservable(result)) {
      return firstValueFrom(result);
    }
    return result;
  }

  it("allows navigation when authenticated", async () => {
    isAuthenticated = true;

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/entries" } as RouterStateSnapshot,
      ),
    );

    await expectAsync(resolveGuardResult(result)).toBeResolvedTo(true);
  });

  it("redirects to login with encoded returnUrl when logged out", async () => {
    isAuthenticated = false;

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/entries?type=daily" } as RouterStateSnapshot,
      ),
    );

    const resolved = await resolveGuardResult(result);
    expect(resolved instanceof UrlTree).toBeTrue();
    const redirectUrl = router.serializeUrl(resolved as UrlTree);
    expect(redirectUrl).toBe("/login?returnUrl=%2Fentries%3Ftype%3Ddaily");
  });

  it("includes a friendly reason when the stored session expired", async () => {
    sessionExpired = true;

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/settings/personalisation" } as RouterStateSnapshot,
      ),
    );

    const resolved = await resolveGuardResult(result);
    const redirectUrl = router.serializeUrl(resolved as UrlTree);
    expect(redirectUrl).toContain("returnUrl=%2Fsettings%2Fpersonalisation");
    expect(redirectUrl).toContain("reason=session-expired");
  });

  it("blocks route matching for protected lazy routes when logged out", async () => {
    isAuthenticated = false;

    const result = TestBed.runInInjectionContext(() =>
      authMatchGuard(
        { path: "settings" } as Route,
        [new UrlSegment("settings", {}), new UrlSegment("import", {})],
      ),
    );

    const resolved = await resolveGuardResult(result);
    expect(resolved instanceof UrlTree).toBeTrue();
    const redirectUrl = router.serializeUrl(resolved as UrlTree);
    expect(redirectUrl).toBe("/login?returnUrl=%2Fsettings%2Fimport");
  });

  it("uses dashboard as the protected-route fallback return target", async () => {
    isAuthenticated = false;

    const result = TestBed.runInInjectionContext(() =>
      authMatchGuard({ path: "" } as Route, []),
    );

    const resolved = await resolveGuardResult(result);
    expect(resolved instanceof UrlTree).toBeTrue();
    const redirectUrl = router.serializeUrl(resolved as UrlTree);
    expect(redirectUrl).toBe("/login?returnUrl=%2Fdashboard");
  });

  it("allows route matching when authenticated", async () => {
    isAuthenticated = true;

    const result = TestBed.runInInjectionContext(() =>
      authMatchGuard({ path: "entries" } as Route, [
        new UrlSegment("entries", {}),
      ]),
    );

    await expectAsync(resolveGuardResult(result)).toBeResolvedTo(true);
  });

  it("redirects authenticated users with incomplete server onboarding to onboarding", async () => {
    isAuthenticated = true;
    profileServiceMock.getProfile = () => of({ onboarding_completed: false });

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/dashboard" } as RouterStateSnapshot,
      ),
    );

    const resolved = await resolveGuardResult(result);
    expect(resolved instanceof UrlTree).toBeTrue();
    expect(router.serializeUrl(resolved as UrlTree)).toBe(
      "/onboarding?returnUrl=%2Fdashboard",
    );
  });

  it("redirects restricted users to the limited account page", async () => {
    isAuthenticated = true;
    profileServiceMock.getProfile = () =>
      of({ onboarding_completed: true, account_status: "restricted" });

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/dashboard" } as RouterStateSnapshot,
      ),
    );

    const resolved = await resolveGuardResult(result);
    expect(resolved instanceof UrlTree).toBeTrue();
    expect(router.serializeUrl(resolved as UrlTree)).toBe("/account-restricted");
  });

  it("keeps the local session and explains database service failures", async () => {
    isAuthenticated = true;
    profileServiceMock.getProfile = () =>
      throwError(
        () =>
          new HttpErrorResponse({
            status: 503,
            error: {
              category: "database",
              code: "database_read_failed",
              error: "OpenMynd could not read from the database. Try again in a moment.",
            },
          }),
      );

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/dashboard" } as RouterStateSnapshot,
      ),
    );

    const resolved = await resolveGuardResult(result);
    expect(resolved instanceof UrlTree).toBeTrue();
    expect(router.serializeUrl(resolved as UrlTree)).toBe(
      "/login?reason=service-unavailable&returnUrl=%2Fdashboard",
    );
    expect(authServiceMock.clearLocalSession).not.toHaveBeenCalled();
  });

  it("allows restricted users to access the limited account page", async () => {
    isAuthenticated = true;
    authServiceMock.getCurrentUser = () => ({
      onboarding_completed: true,
      account_status: "restricted",
    });

    const result = TestBed.runInInjectionContext(() =>
      authGuard(
        {} as ActivatedRouteSnapshot,
        { url: "/account-restricted" } as RouterStateSnapshot,
      ),
    );

    await expectAsync(resolveGuardResult(result)).toBeResolvedTo(true);
  });
});
