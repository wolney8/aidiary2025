import {
  HttpErrorResponse,
  HttpRequest,
  HttpResponse,
} from "@angular/common/http";
import { TestBed } from "@angular/core/testing";
import { of, throwError } from "rxjs";
import { authInterceptor, readCookie } from "./auth.interceptor";
import { AuthService } from "../services/auth.service";

describe("authInterceptor", () => {
  let authServiceMock: {
    handleSessionExpired: () => void;
    handleOnboardingRequired: () => void;
  };

  beforeEach(() => {
    document.cookie
      .split(";")
      .forEach((cookie) => {
        const name = cookie.split("=")[0]?.trim();
        if (name) {
          document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
        }
      });
    authServiceMock = {
      handleSessionExpired: jasmine.createSpy("handleSessionExpired"),
      handleOnboardingRequired: jasmine.createSpy("handleOnboardingRequired"),
    };

    TestBed.configureTestingModule({
      providers: [{ provide: AuthService, useValue: authServiceMock }],
    });
  });

  it("calls handleSessionExpired for 401 responses on protected requests", () => {
    const request = new HttpRequest("GET", "/api/entries");
    const unauthorized = new HttpErrorResponse({ status: 401 });

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, () => throwError(() => unauthorized)).subscribe({
        error: () => undefined,
      });
    });

    expect(authServiceMock.handleSessionExpired).toHaveBeenCalled();
  });

  it("does not call handleSessionExpired for 401 responses on login endpoint", () => {
    const request = new HttpRequest("GET", "/api/login");
    const unauthorized = new HttpErrorResponse({ status: 401 });

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, () => throwError(() => unauthorized)).subscribe({
        error: () => undefined,
      });
    });

    expect(authServiceMock.handleSessionExpired).not.toHaveBeenCalled();
  });

  it("does not call handleSessionExpired for non-401 errors", () => {
    const request = new HttpRequest("GET", "/api/entries");
    const forbidden = new HttpErrorResponse({ status: 403 });

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, () => throwError(() => forbidden)).subscribe({
        error: () => undefined,
      });
    });

    expect(authServiceMock.handleSessionExpired).not.toHaveBeenCalled();
  });

  it("routes incomplete users to onboarding when the API requires setup", () => {
    const request = new HttpRequest("GET", "/api/dashboard/overview");
    const onboardingRequired = new HttpErrorResponse({
      status: 403,
      error: { code: "onboarding_required" },
    });

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, () => throwError(() => onboardingRequired)).subscribe({
        error: () => undefined,
      });
    });

    expect(authServiceMock.handleOnboardingRequired).toHaveBeenCalled();
    expect(authServiceMock.handleSessionExpired).not.toHaveBeenCalled();
  });

  it("passes through successful responses", () => {
    const request = new HttpRequest("GET", "/api/entries");
    const successful = new HttpResponse({ status: 200, body: { ok: true } });
    let responseStatus: number | undefined;

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, () => of(successful)).subscribe((response) => {
        if (response instanceof HttpResponse) {
          responseStatus = response.status;
        }
      });
    });

    expect(responseStatus).toBe(200);
    expect(authServiceMock.handleSessionExpired).not.toHaveBeenCalled();
  });

  it("adds credentials to API requests", () => {
    const request = new HttpRequest("GET", "/api/entries");
    let forwarded: HttpRequest<unknown> | undefined;

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, (nextRequest) => {
        forwarded = nextRequest;
        return of(new HttpResponse({ status: 200 }));
      }).subscribe();
    });

    expect(forwarded?.withCredentials).toBeTrue();
  });

  it("adds a CSRF header for unsafe API requests when the CSRF cookie exists", () => {
    document.cookie = "csrf_access_token=test-csrf-token; path=/";
    const request = new HttpRequest("POST", "/api/entries", {});
    let forwarded: HttpRequest<unknown> | undefined;

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, (nextRequest) => {
        forwarded = nextRequest;
        return of(new HttpResponse({ status: 200 }));
      }).subscribe();
    });

    expect(readCookie("csrf_access_token")).toBe("test-csrf-token");
    expect(forwarded?.headers.get("X-CSRF-TOKEN")).toBe("test-csrf-token");
  });

  it("does not add a CSRF header for safe API requests", () => {
    document.cookie = "csrf_access_token=test-csrf-token; path=/";
    const request = new HttpRequest("GET", "/api/entries");
    let forwarded: HttpRequest<unknown> | undefined;

    TestBed.runInInjectionContext(() => {
      authInterceptor(request, (nextRequest) => {
        forwarded = nextRequest;
        return of(new HttpResponse({ status: 200 }));
      }).subscribe();
    });

    expect(forwarded?.headers.has("X-CSRF-TOKEN")).toBeFalse();
  });
});
