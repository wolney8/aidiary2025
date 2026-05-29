import { TestBed } from "@angular/core/testing";
import { HttpClient } from "@angular/common/http";
import { Router } from "@angular/router";
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
        { provide: HttpClient, useValue: { post: jasmine.createSpy("post") } },
        { provide: Router, useValue: routerMock },
      ],
    });

    service = TestBed.inject(AuthService);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("logout clears session and keeps manual logout behaviour", () => {
    localStorage.setItem("ai_diary_token", "token");
    localStorage.setItem(
      "ai_diary_user",
      JSON.stringify({ id: 1, username: "tester" }),
    );

    service.logout();

    expect(localStorage.getItem("ai_diary_token")).toBeNull();
    expect(localStorage.getItem("ai_diary_user")).toBeNull();
    expect(routerMock.navigate).toHaveBeenCalledWith(["/login"]);
  });

  it("handleSessionExpired redirects to login with expiry reason on protected pages", () => {
    localStorage.setItem("ai_diary_token", "token");
    localStorage.setItem(
      "ai_diary_user",
      JSON.stringify({ id: 1, username: "tester" }),
    );
    routerMock.url = "/entries";

    service.handleSessionExpired();

    expect(localStorage.getItem("ai_diary_token")).toBeNull();
    expect(localStorage.getItem("ai_diary_user")).toBeNull();
    expect(routerMock.navigate).toHaveBeenCalledWith(["/login"], {
      queryParams: { reason: "session-expired" },
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
});
