import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";
import { CbtService } from "./cbt.service";

describe("CbtService", () => {
  let service: CbtService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: AuthService,
          useValue: {
            getToken: () => "test-token",
            isAuthenticated: () => true,
          },
        },
      ],
    });
    service = TestBed.inject(CbtService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpTesting.verify());

  it("loads worksheets linked to an entry", () => {
    service
      .listWorksheets({ linkedEntryType: "daily", linkedEntryId: 42 })
      .subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/cbt/worksheets?linked_entry_type=daily&linked_entry_id=42`,
    );
    expect(request.request.method).toBe("GET");
    expect(request.request.headers.get("Authorization")).toBe(
      "Bearer test-token",
    );
    request.flush([]);
  });

  it("creates a linked thought record", () => {
    service
      .createWorksheet({
        title: "Linked reflection",
        linked_entry_type: "dream",
        linked_entry_id: 7,
      })
      .subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/cbt/worksheets`,
    );
    expect(request.request.method).toBe("POST");
    expect(request.request.body).toEqual({
      title: "Linked reflection",
      linked_entry_type: "dream",
      linked_entry_id: 7,
    });
    request.flush({});
  });

  it("uses the completion endpoint without changing the response contract", () => {
    service.completeWorksheet(9).subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/cbt/worksheets/9/complete`,
    );
    expect(request.request.method).toBe("POST");
    expect(request.request.body).toEqual({});
    request.flush({});
  });

  it("revises a completed worksheet without reopening it as a draft", () => {
    service.reviseWorksheet(9, { title: "Revised" }).subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/cbt/worksheets/9/revise`,
    );
    expect(request.request.method).toBe("PUT");
    expect(request.request.body).toEqual({ title: "Revised" });
    request.flush({});
  });

  it("requests an AI response for a completed worksheet", () => {
    service.analyseWorksheet(9).subscribe();

    const request = httpTesting.expectOne(
      `${environment.apiBaseUrl}/cbt/worksheets/9/analyse`,
    );
    expect(request.request.method).toBe("POST");
    expect(request.request.body).toEqual({});
    request.flush({});
  });
});
