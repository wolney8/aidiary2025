import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../environments/environment";
import { AnnouncementService } from "./announcement.service";
import { AuthService } from "./auth.service";

describe("AnnouncementService", () => {
  let service: AnnouncementService;
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
          },
        },
      ],
    });
    service = TestBed.inject(AnnouncementService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it("reuses an in-flight announcement refresh for the same cookie-auth user", () => {
    service.refresh().subscribe();
    service.refresh().subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/announcements/active`,
    );
    expect(request.request.method).toBe("GET");
    request.flush({ announcements: [] });
  });

  it("does not reuse cached announcements across cookie-auth users", () => {
    service.refresh().subscribe();
    httpTesting.expectOne(`${environment.apiBaseUrl}/announcements/active`).flush({
      announcements: [
        {
          id: 1,
          title: "User one",
          message: "Only for user one",
          severity: "info",
          placement: "bell",
          dismissible: true,
          unread: true,
          targets: [],
        },
      ],
    });

    service.refresh().subscribe();
    httpTesting.expectNone(`${environment.apiBaseUrl}/announcements/active`);

    currentUserId = 2;
    service.refresh().subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/announcements/active`,
    );
    expect(request.request.method).toBe("GET");
    request.flush({ announcements: [] });
  });
});
