import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter, Router } from "@angular/router";
import { of } from "rxjs";
import { CbtWorksheet } from "../core/models/cbt.model";
import { AppDialogService } from "../core/services/app-dialog.service";
import { CbtService } from "../core/services/cbt.service";
import { CbtDashboardComponent } from "./cbt-dashboard.component";

function worksheet(
  overrides: Partial<CbtWorksheet> = {},
): CbtWorksheet {
  return {
    id: 1,
    worksheet_type: "thought_record",
    title: "Difficult meeting",
    status: "completed",
    current_step: 7,
    record_date: "2026-07-21",
    linked_entry_type: null,
    linked_entry_id: null,
    situation: "A meeting felt difficult.",
    feelings_before: [{ label: "Anxious", intensity: 80 }],
    unhelpful_thoughts: "I assumed I had failed.",
    evidence_for: "The meeting was tense.",
    evidence_against: "The feedback was constructive.",
    balanced_thought: "One difficult meeting does not define my work.",
    feelings_after: [{ label: "Anxious", intensity: 45 }],
    next_step: "Review the feedback tomorrow.",
    ai_response: "",
    ai_responded_at: null,
    ai_response_outdated: false,
    before_peak_intensity: 80,
    after_peak_intensity: 45,
    intensity_change: -35,
    created_at: "2026-07-21 09:00:00",
    updated_at: "2026-07-21 09:30:00",
    completed_at: "2026-07-21 09:30:00",
    ...overrides,
  };
}

describe("CbtDashboardComponent", () => {
  let fixture: ComponentFixture<CbtDashboardComponent>;
  let component: CbtDashboardComponent;
  let router: Router;
  let cbtService: {
    listWorksheets: jasmine.Spy;
    createWorksheet: jasmine.Spy;
    deleteWorksheet: jasmine.Spy;
  };

  beforeEach(async () => {
    cbtService = {
      listWorksheets: jasmine.createSpy().and.returnValue(of([])),
      createWorksheet: jasmine
        .createSpy()
        .and.returnValue(of(worksheet({ id: 9, status: "draft" }))),
      deleteWorksheet: jasmine.createSpy().and.returnValue(of({})),
    };

    await TestBed.configureTestingModule({
      imports: [CbtDashboardComponent],
      providers: [
        provideRouter([]),
        provideNoopAnimations(),
        { provide: CbtService, useValue: cbtService },
        {
          provide: AppDialogService,
          useValue: {
            confirm: jasmine.createSpy().and.resolveTo(true),
            alert: jasmine.createSpy().and.resolveTo(undefined),
          },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(CbtDashboardComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  it("summarises outcomes, handles missing ratings, and starts a new record", () => {
    component.worksheets = [
      worksheet(),
      worksheet({
        id: 2,
        before_peak_intensity: 60,
        after_peak_intensity: 70,
        intensity_change: 10,
      }),
      worksheet({ id: 3, status: "draft", completed_at: null }),
    ];

    expect(component.completed.length).toBe(2);
    expect(component.ratedCompleted.length).toBe(2);
    expect(component.lowerPeakRatingCount).toBe(1);
    expect(component.averagePeakRatingChange).toBe(-13);
    expect(component.getAveragePeakRatingChangeLabel()).toBe("13 points lower");

    fixture.detectChanges();
    const overview = fixture.nativeElement.querySelector(
      '[data-testid="cbt-reflection-overview"]',
    ) as HTMLElement;
    expect(overview).not.toBeNull();
    expect(overview.textContent).toContain("Reflection overview");
    expect(overview.textContent).toContain("13 points lower");

    component.worksheets = [
      worksheet({
        before_peak_intensity: null,
        after_peak_intensity: null,
        intensity_change: null,
      }),
    ];

    expect(component.ratedCompleted).toEqual([]);
    expect(component.getAveragePeakRatingChangeLabel()).toBe("Not available");

    const navigate = spyOn(router, "navigate").and.resolveTo(true);

    component.startThoughtRecord();

    expect(cbtService.createWorksheet).toHaveBeenCalledWith(
      jasmine.objectContaining({
        record_date: jasmine.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      }),
    );
    expect(navigate).toHaveBeenCalledWith(["/cbt", 9]);
  });
});
