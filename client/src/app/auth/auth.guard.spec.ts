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
  };

  beforeEach(() => {
    isAuthenticated = false;

    authServiceMock = {
      isAuthenticated: () => isAuthenticated,
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
});
