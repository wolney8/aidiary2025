import {
  HttpErrorResponse,
  HttpRequest,
  HttpResponse,
} from "@angular/common/http";
import { TestBed } from "@angular/core/testing";
import { of, throwError } from "rxjs";
import { authInterceptor } from "./auth.interceptor";
import { AuthService } from "../services/auth.service";

describe("authInterceptor", () => {
  let authServiceMock: {
    handleSessionExpired: () => void;
  };

  beforeEach(() => {
    authServiceMock = {
      handleSessionExpired: jasmine.createSpy("handleSessionExpired"),
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
});
