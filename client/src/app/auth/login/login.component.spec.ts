import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, convertToParamMap, Router } from "@angular/router";
import { of } from "rxjs";
import { LoginComponent } from "./login.component";
import { AuthService } from "../../core/services/auth.service";

describe("LoginComponent returnUrl navigation", () => {
  let fixture: ComponentFixture<LoginComponent>;
  let component: LoginComponent;
  let queryParams: Record<string, string>;
  let authServiceMock: {
    login: (...args: unknown[]) => unknown;
    getOAuthProviders: () => unknown;
    getOAuthStartUrl: (...args: unknown[]) => string;
    clearLocalSession: () => void;
  };
  let routerMock: {
    navigateByUrl: (...args: unknown[]) => unknown;
    events: ReturnType<typeof of>;
    createUrlTree: (...args: unknown[]) => object;
    serializeUrl: (...args: unknown[]) => string;
  };

  beforeEach(async () => {
    queryParams = {};

    authServiceMock = {
      login: jasmine.createSpy("login").and.returnValue(
        of({
          token: "token",
          user: {
            id: 1,
            username: "tester",
            first_name: "Test",
            last_name: "User",
            email: "test@example.com",
          },
        }),
      ),
      getOAuthProviders: jasmine.createSpy("getOAuthProviders").and.returnValue(
        of({
          providers: [
            {
              id: "google",
              label: "Google",
              enabled: true,
              configured: true,
              status: "enabled",
              start_url: "/api/oauth/google/start",
            },
            {
              id: "microsoft",
              label: "Microsoft",
              enabled: false,
              configured: false,
              status: "not_configured",
              start_url: null,
            },
          ],
        }),
      ),
      getOAuthStartUrl: jasmine
        .createSpy("getOAuthStartUrl")
        .and.returnValue("/api/oauth/google/start?returnUrl=%2Fdashboard"),
      clearLocalSession: jasmine.createSpy("clearLocalSession"),
    };

    routerMock = {
      navigateByUrl: jasmine.createSpy("navigateByUrl"),
      events: of(),
      createUrlTree: jasmine.createSpy("createUrlTree").and.returnValue({}),
      serializeUrl: jasmine.createSpy("serializeUrl").and.returnValue("/register"),
    };

    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: Router, useValue: routerMock },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              get queryParamMap() {
                return convertToParamMap(queryParams);
              },
            },
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
  });

  it("navigates to returnUrl when it is a safe local path", () => {
    queryParams = { returnUrl: "/settings" };
    component.credentials = { username: "user", password: "password" };

    component.onSubmit();

    expect(routerMock.navigateByUrl).toHaveBeenCalledWith("/settings", {
      replaceUrl: true,
    });
  });

  it("falls back to /dashboard for unsafe absolute returnUrl values", () => {
    queryParams = { returnUrl: "https://example.com/phishing" };
    component.credentials = { username: "user", password: "password" };

    component.onSubmit();

    expect(routerMock.navigateByUrl).toHaveBeenCalledWith("/dashboard", {
      replaceUrl: true,
    });
  });

  it("falls back to /dashboard when returnUrl is missing", () => {
    queryParams = {};
    component.credentials = { username: "user", password: "password" };

    component.onSubmit();

    expect(routerMock.navigateByUrl).toHaveBeenCalledWith("/dashboard", {
      replaceUrl: true,
    });
  });

  it("shows session-expired message when reason query param is present", () => {
    queryParams = { reason: "session-expired" };

    fixture.detectChanges();

    expect(component.sessionInfoMessage).toBe(
      "Your session has expired. Please log in again to continue.",
    );
  });

  it("does not show session-expired message when reason query param is absent", () => {
    queryParams = {};

    fixture.detectChanges();

    expect(component.sessionInfoMessage).toBe("");
  });

  it("shows an account-deleted message after account deletion", () => {
    queryParams = { reason: "account-deleted" };

    fixture.detectChanges();

    expect(component.sessionInfoMessage).toBe("Your account has been deleted.");
  });

  it("exposes an accessible page heading and credential autocomplete hints", () => {
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector("h1");
    const username = fixture.nativeElement.querySelector('input[name="username"]');
    const password = fixture.nativeElement.querySelector('input[name="password"]');

    expect(heading?.textContent).toContain("Log in to OpenMynd");
    expect(username?.getAttribute("autocomplete")).toBe("username");
    expect(password?.getAttribute("autocomplete")).toBe("current-password");
  });

  it("renders the Google sign-in action and hides unsupported providers", () => {
    fixture.detectChanges();

    const googleButton = fixture.nativeElement.querySelector(
      '[data-testid="login-google-oauth"]',
    ) as HTMLButtonElement | null;
    const microsoftButton = fixture.nativeElement.querySelector(
      '[data-testid="login-microsoft-oauth"]',
    ) as HTMLButtonElement | null;

    expect(microsoftButton).toBeNull();
    expect(googleButton?.textContent).toContain("Continue with Google");
    expect(googleButton?.getAttribute("href")).toContain("/api/oauth/google/start");
    expect(googleButton?.querySelector("svg.oauth-mark--google")).not.toBeNull();
  });

  it("announces validation failures as alerts", () => {
    fixture.detectChanges();

    component.onSubmit();
    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("Please enter both username and password");
  });
});
