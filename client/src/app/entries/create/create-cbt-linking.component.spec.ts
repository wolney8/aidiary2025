import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router, convertToParamMap } from "@angular/router";
import { of } from "rxjs";
import { CbtWorksheet } from "../../core/models/cbt.model";
import { AnalysisService } from "../../core/services/analysis.service";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { AuthService } from "../../core/services/auth.service";
import { CbtService } from "../../core/services/cbt.service";
import { EntriesService } from "../../core/services/entries.service";
import { ImportantDaysService } from "../../core/services/important-days.service";
import { CreateComponent } from "./create.component";

describe("CreateComponent thought record linking", () => {
  let fixture: ComponentFixture<CreateComponent>;
  let component: CreateComponent;
  let router: jasmine.SpyObj<Router>;
  let entriesService: jasmine.SpyObj<EntriesService>;
  let cbtService: jasmine.SpyObj<CbtService>;

  beforeEach(async () => {
    router = jasmine.createSpyObj<Router>("Router", ["navigate"]);
    router.navigate.and.resolveTo(true);
    entriesService = jasmine.createSpyObj<EntriesService>("EntriesService", [
      "createDailyEntry",
    ]);
    cbtService = jasmine.createSpyObj<CbtService>("CbtService", [
      "createWorksheet",
      "listWorksheets",
    ]);
    cbtService.listWorksheets.and.returnValue(of([]));

    TestBed.configureTestingModule({
      imports: [CreateComponent],
      providers: [
        { provide: Router, useValue: router },
        { provide: EntriesService, useValue: entriesService },
        { provide: CbtService, useValue: cbtService },
        {
          provide: ImportantDaysService,
          useValue: jasmine.createSpyObj("ImportantDaysService", [
            "createImportantDay",
          ]),
        },
        { provide: AnalysisService, useValue: {} },
        {
          provide: AuthService,
          useValue: { getCurrentUser: () => null },
        },
        {
          provide: AppDialogService,
          useValue: {
            confirm: jasmine.createSpy().and.resolveTo(true),
            alert: jasmine.createSpy().and.resolveTo(undefined),
          },
        },
        {
          provide: ActivatedRoute,
          useValue: {
            queryParamMap: of(convertToParamMap({})),
            snapshot: {
              paramMap: convertToParamMap({}),
              queryParams: {},
            },
          },
        },
      ],
    });
    TestBed.overrideComponent(CreateComponent, {
      set: { template: "", styles: [] },
    });
    await TestBed.compileComponents();

    fixture = TestBed.createComponent(CreateComponent);
    component = fixture.componentInstance;
  });

  it("saves a new entry before starting its linked thought record", async () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.entryTitle = "Difficult conversation";
    component.content = "I felt anxious after a difficult conversation.";
    entriesService.createDailyEntry.and.returnValue(
      of({ id: 57, entry_date: "2026-05-30" }),
    );
    cbtService.createWorksheet.and.returnValue(
      of({ id: 14 } as CbtWorksheet),
    );

    component.saveAndStartThoughtRecord();
    await new Promise<void>((resolve) => window.setTimeout(resolve));

    expect(entriesService.createDailyEntry).toHaveBeenCalledTimes(1);
    expect(cbtService.createWorksheet).toHaveBeenCalledWith({
      title: "Reflection: Difficult conversation",
      record_date: "2026-05-30",
      linked_entry_type: "daily",
      linked_entry_id: 57,
    });
    expect(router.navigate).toHaveBeenCalledWith(["/cbt", 14], {
      queryParams: {
        returnEntryId: 57,
        returnEntryType: "daily",
      },
    });
  });
});
