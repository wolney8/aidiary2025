import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";
import { BillingService } from "./billing.service";

describe("BillingService", () => {
  let service: BillingService;
  let httpTesting: HttpTestingController;
  let currentUserId = 1;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: {
            getToken: () => null,
            getCurrentUser: () => ({ id: currentUserId, username: "tester" }),
            isAuthenticated: () => true,
          },
        },
      ],
    });
    service = TestBed.inject(BillingService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it("reuses an in-flight billing status request for the same cookie-auth user", () => {
    service.getStatus().subscribe();
    service.getStatus().subscribe();

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/billing/status`);
    expect(request.request.method).toBe("GET");
    request.flush({ entitlement: { tier: "free" }, plans: [], usage: {} });
  });

  it("does not reuse a billing status response across cookie-auth users", () => {
    service.getStatus().subscribe();
    httpTesting
      .expectOne(`${environment.apiBaseUrl}/billing/status`)
      .flush({ entitlement: { tier: "free" }, plans: [], usage: {} });

    currentUserId = 2;
    service.getStatus().subscribe();

    const request = httpTesting.expectOne(`${environment.apiBaseUrl}/billing/status`);
    expect(request.request.method).toBe("GET");
    request.flush({ entitlement: { tier: "free" }, plans: [], usage: {} });
  });
});
