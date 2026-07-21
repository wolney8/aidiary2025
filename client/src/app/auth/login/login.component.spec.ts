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

  it("falls back to /entries for unsafe absolute returnUrl values", () => {
    queryParams = { returnUrl: "https://example.com/phishing" };
    component.credentials = { username: "user", password: "password" };

    component.onSubmit();

    expect(routerMock.navigateByUrl).toHaveBeenCalledWith("/entries", {
      replaceUrl: true,
    });
  });

  it("falls back to /entries when returnUrl is missing", () => {
    queryParams = {};
    component.credentials = { username: "user", password: "password" };

    component.onSubmit();

    expect(routerMock.navigateByUrl).toHaveBeenCalledWith("/entries", {
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

  it("exposes an accessible page heading and credential autocomplete hints", () => {
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector("h1");
    const username = fixture.nativeElement.querySelector('input[name="username"]');
    const password = fixture.nativeElement.querySelector('input[name="password"]');

    expect(heading?.textContent).toContain("Login to AI Diary");
    expect(username?.getAttribute("autocomplete")).toBe("username");
    expect(password?.getAttribute("autocomplete")).toBe("current-password");
  });

  it("announces validation failures as alerts", () => {
    fixture.detectChanges();

    component.onSubmit();
    fixture.detectChanges();

    const alert = fixture.nativeElement.querySelector('[role="alert"]');
    expect(alert?.textContent).toContain("Please enter both username and password");
  });
});
