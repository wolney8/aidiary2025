import { ComponentFixture, TestBed } from "@angular/core/testing";
import { Router } from "@angular/router";
import { OAuthCallbackComponent } from "./oauth-callback.component";
import { AuthService } from "../../core/services/auth.service";
import { User } from "../../core/models/user.model";

describe("OAuthCallbackComponent", () => {
  let fixture: ComponentFixture<OAuthCallbackComponent>;
  let authServiceMock: {
    completeOAuthLogin: jasmine.Spy;
  };
  let routerMock: {
    navigateByUrl: jasmine.Spy;
  };

  beforeEach(async () => {
    authServiceMock = {
      completeOAuthLogin: jasmine.createSpy("completeOAuthLogin"),
    };
    routerMock = {
      navigateByUrl: jasmine.createSpy("navigateByUrl"),
    };

    await TestBed.configureTestingModule({
      imports: [OAuthCallbackComponent],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: Router, useValue: routerMock },
      ],
    }).compileComponents();
  });

  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("routes onboarding-required OAuth users to onboarding before dashboard", () => {
    setCallbackFragment({
      token: "oauth-token",
      user: {
        id: 1,
        username: "google-user",
        onboarding_completed: false,
      },
      returnUrl: "/settings/account",
      onboardingRequired: "true",
    });

    fixture = TestBed.createComponent(OAuthCallbackComponent);
    fixture.detectChanges();

    expect(authServiceMock.completeOAuthLogin).toHaveBeenCalled();
    expect(routerMock.navigateByUrl).toHaveBeenCalledWith(
      "/onboarding?returnUrl=%2Fdashboard",
      { replaceUrl: true },
    );
  });

  it("routes completed OAuth users to the safe return URL", () => {
    setCallbackFragment({
      token: "oauth-token",
      user: {
        id: 1,
        username: "google-user",
        onboarding_completed: true,
      },
      returnUrl: "/entries?display=calendar",
      onboardingRequired: "false",
    });

    fixture = TestBed.createComponent(OAuthCallbackComponent);
    fixture.detectChanges();

    expect(authServiceMock.completeOAuthLogin).toHaveBeenCalled();
    expect(routerMock.navigateByUrl).toHaveBeenCalledWith(
      "/entries?display=calendar",
      { replaceUrl: true },
    );
  });

  function setCallbackFragment(args: {
    token: string;
    user: User;
    returnUrl: string;
    onboardingRequired: "true" | "false";
  }): void {
    const encodedUser = btoa(JSON.stringify(args.user))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
    const fragment = new URLSearchParams({
      token: args.token,
      user: encodedUser,
      returnUrl: args.returnUrl,
      onboardingRequired: args.onboardingRequired,
    });
    window.history.pushState({}, "", `/oauth/callback#${fragment.toString()}`);
  }
});
