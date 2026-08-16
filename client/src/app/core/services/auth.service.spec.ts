import { TestBed } from "@angular/core/testing";
import { HttpClient } from "@angular/common/http";
import { Router } from "@angular/router";
import { of } from "rxjs";
import { AuthService } from "./auth.service";

describe("AuthService session handling", () => {
  let service: AuthService;
  let routerMock: {
    url: string;
    navigate: (...args: unknown[]) => unknown;
  };

  beforeEach(() => {
    localStorage.clear();

    routerMock = {
      url: "/entries",
      navigate: jasmine.createSpy("navigate"),
    };

    TestBed.configureTestingModule({
      providers: [
        AuthService,
        {
          provide: HttpClient,
          useValue: { post: jasmine.createSpy("post").and.returnValue(of({})) },
        },
        { provide: Router, useValue: routerMock },
      ],
    });

    service = TestBed.inject(AuthService);
  });

  afterEach(() => {
    localStorage.clear();
  });

  function createToken(expirySeconds: number): string {
    const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
    const payload = btoa(JSON.stringify({ exp: expirySeconds }));
    return `${header}.${payload}.signature`;
  }

  it("logout clears session and keeps manual logout behaviour", () => {
    localStorage.setItem("openmynd_token", "token");
    localStorage.setItem(
      "openmynd_user",
      JSON.stringify({ id: 1, username: "tester" }),
    );

    service.logout();

    expect(localStorage.getItem("openmynd_token")).toBeNull();
    expect(localStorage.getItem("openmynd_user")).toBeNull();
    expect(routerMock.navigate).toHaveBeenCalledWith(["/login"], {
      queryParams: undefined,
      replaceUrl: false,
    });
  });

  it("handleSessionExpired redirects to login with expiry reason on protected pages", () => {
    localStorage.setItem("openmynd_token", "token");
    localStorage.setItem(
      "openmynd_user",
      JSON.stringify({ id: 1, username: "tester" }),
    );
    routerMock.url = "/entries";

    service.handleSessionExpired();

    expect(localStorage.getItem("openmynd_token")).toBeNull();
    expect(localStorage.getItem("openmynd_user")).toBeNull();
    expect(routerMock.navigate).toHaveBeenCalledWith(["/login"], {
      queryParams: {
        reason: "session-expired",
        returnUrl: "/entries",
      },
      replaceUrl: true,
    });
  });

  it("handleSessionExpired does not redirect again when already on login", () => {
    routerMock.url = "/login?returnUrl=%2Fentries";

    service.handleSessionExpired();

    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it("handleSessionExpired does not redirect again when already on register", () => {
    routerMock.url = "/register";

    service.handleSessionExpired();

    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it("accepts a structurally valid unexpired JWT", () => {
    localStorage.setItem(
      "openmynd_token",
      createToken(Math.floor(Date.now() / 1000) + 60),
    );

    expect(service.isAuthenticated()).toBeTrue();
  });

  it("clears an expired JWT before protected navigation", () => {
    localStorage.setItem(
      "openmynd_token",
      createToken(Math.floor(Date.now() / 1000) - 60),
    );
    localStorage.setItem(
      "openmynd_user",
      JSON.stringify({ id: 1, username: "tester" }),
    );

    expect(service.isAuthenticated()).toBeFalse();
    expect(service.consumeSessionExpiredFlag()).toBeTrue();
    expect(service.consumeSessionExpiredFlag()).toBeFalse();
    expect(localStorage.getItem("openmynd_token")).toBeNull();
    expect(localStorage.getItem("openmynd_user")).toBeNull();
  });

  it("rejects malformed token data", () => {
    localStorage.setItem("openmynd_token", "not-a-jwt");

    expect(service.isAuthenticated()).toBeFalse();
    expect(localStorage.getItem("openmynd_token")).toBeNull();
  });

  it("does not sync a late user response after the token has been cleared", () => {
    service.syncCurrentUser({ id: 1, username: "late-response" });

    expect(localStorage.getItem("openmynd_user")).toBeNull();
  });

  it("syncs the current user while a token is still present", () => {
    localStorage.setItem("openmynd_token", "token");

    service.syncCurrentUser({ id: 1, username: "active-user" });

    expect(localStorage.getItem("openmynd_user")).toContain("active-user");
  });

  it("does not persist bearer tokens when cookie-only auth is enabled", () => {
    (service as unknown as { cookieOnlyAuth: boolean }).cookieOnlyAuth = true;

    service.completeOAuthLogin({
      token: createToken(Math.floor(Date.now() / 1000) + 60),
      user: { id: 1, username: "cookie-user" },
    });

    expect(localStorage.getItem("openmynd_token")).toBeNull();
    expect(localStorage.getItem("openmynd_user")).toContain("cookie-user");
    expect(service.getToken()).toBeNull();
    expect(service.isAuthenticated()).toBeTrue();
  });

  it("builds OAuth start URLs when the API base is relative", () => {
    (service as unknown as { apiUrl: string }).apiUrl = "/api";

    const url = service.getOAuthStartUrl(
      {
        id: "google",
        label: "Google",
        enabled: true,
        configured: true,
        status: "enabled",
        start_url: "/api/oauth/google/start",
      },
      "/dashboard",
    );

    expect(url).toBe(`${window.location.origin}/api/oauth/google/start?returnUrl=%2Fdashboard`);
  });

  it("builds OAuth start URLs when the API base is absolute", () => {
    (service as unknown as { apiUrl: string }).apiUrl = "http://localhost:5001/api";

    const url = service.getOAuthStartUrl(
      {
        id: "google",
        label: "Google",
        enabled: true,
        configured: true,
        status: "enabled",
        start_url: "/api/oauth/google/start",
      },
      "/entries",
    );

    expect(url).toBe("http://localhost:5001/api/oauth/google/start?returnUrl=%2Fentries");
  });
});
