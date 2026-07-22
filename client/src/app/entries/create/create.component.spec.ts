import { HttpErrorResponse } from "@angular/common/http";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router, convertToParamMap } from "@angular/router";
import { of, throwError } from "rxjs";
import { CreateComponent } from "./create.component";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { AuthService } from "../../core/services/auth.service";
import { EntriesService } from "../../core/services/entries.service";
import { AnalysisService } from "../../core/services/analysis.service";
import { CbtService } from "../../core/services/cbt.service";
import { ImportantDaysService } from "../../core/services/important-days.service";
import {
  DailyAnalysisResponse,
  DailyEntry,
  DreamAnalysisResponse,
  DreamEntry,
} from "../../core/models/entry.model";
import { CbtWorksheet } from "../../core/models/cbt.model";

describe("CreateComponent save reliability", () => {
  let fixture: ComponentFixture<CreateComponent>;
  let component: CreateComponent;
  let routerMock: jasmine.SpyObj<Router>;
  let appDialogMock: jasmine.SpyObj<AppDialogService>;
  let authServiceMock: jasmine.SpyObj<AuthService>;
  let entriesServiceMock: jasmine.SpyObj<EntriesService>;
  let analysisServiceMock: jasmine.SpyObj<AnalysisService>;
  let cbtServiceMock: jasmine.SpyObj<CbtService>;
  let importantDaysServiceMock: jasmine.SpyObj<ImportantDaysService>;

  beforeEach(async () => {
    routerMock = jasmine.createSpyObj<Router>("Router", ["navigate"]);
    appDialogMock = jasmine.createSpyObj<AppDialogService>("AppDialogService", [
      "confirm",
      "alert",
    ]);
    appDialogMock.confirm.and.resolveTo(true);
    appDialogMock.alert.and.resolveTo();
    authServiceMock = jasmine.createSpyObj<AuthService>("AuthService", [
      "getCurrentUser",
    ]);
    authServiceMock.getCurrentUser.and.returnValue(null);

    entriesServiceMock = jasmine.createSpyObj<EntriesService>(
      "EntriesService",
      [
        "createDailyEntry",
        "updateDailyEntry",
        "createDreamEntry",
        "updateDreamEntry",
        "getDailyEntry",
        "getDreamEntry",
        "uploadDailyAttachment",
        "uploadDreamAttachment",
      ],
    );

    analysisServiceMock = jasmine.createSpyObj<AnalysisService>(
      "AnalysisService",
      ["analyseText"],
    );
    cbtServiceMock = jasmine.createSpyObj<CbtService>("CbtService", [
      "listWorksheets",
      "createWorksheet",
      "completeWorksheet",
      "analyseWorksheet",
    ]);
    cbtServiceMock.listWorksheets.and.returnValue(of([]));
    cbtServiceMock.completeWorksheet.and.callFake((id: number) =>
      of({ id } as CbtWorksheet),
    );
    cbtServiceMock.analyseWorksheet.and.callFake((id: number) =>
      of({ id } as CbtWorksheet),
    );
    importantDaysServiceMock = jasmine.createSpyObj<ImportantDaysService>(
      "ImportantDaysService",
      ["createImportantDay", "uploadImportantDayImage"],
    );
    importantDaysServiceMock.uploadImportantDayImage.and.returnValue(
      of({ id: 7, image_url: "/media/important-day.jpg" }),
    );

    await TestBed.configureTestingModule({
      imports: [CreateComponent],
      providers: [
        { provide: Router, useValue: routerMock },
        { provide: AppDialogService, useValue: appDialogMock },
        { provide: AuthService, useValue: authServiceMock },
        { provide: EntriesService, useValue: entriesServiceMock },
        { provide: AnalysisService, useValue: analysisServiceMock },
        { provide: CbtService, useValue: cbtServiceMock },
        { provide: ImportantDaysService, useValue: importantDaysServiceMock },
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
    }).compileComponents();

    fixture = TestBed.createComponent(CreateComponent);
    component = fixture.componentInstance;
  });

  it("navigates after successful daily save even when analysis request fails", () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "A full daily entry";
    component.selectedMood = "thoughtful";
    component.selectedAIStyle = "reflective";
    component.isEditing = true;
    component.editingId = 42;

    const updatedDailyEntry: DailyEntry = {
      id: 42,
      entry_date: "2026-05-30",
    };

    entriesServiceMock.updateDailyEntry.and.returnValue(of(updatedDailyEntry));
    analysisServiceMock.analyseText.and.returnValue(
      throwError(() => new Error("analysis failed")),
    );

    component.saveAndAnalyse();

    expect(entriesServiceMock.updateDailyEntry).toHaveBeenCalledTimes(1);
    expect(entriesServiceMock.updateDailyEntry).toHaveBeenCalledWith(
      42,
      jasmine.objectContaining({
        entry_date: "2026-05-30",
        mood: "thoughtful",
        ai_style: "reflective",
      }),
    );
    expect(analysisServiceMock.analyseText).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 42], {
      queryParams: undefined,
    });
    expect(component.errorMessage).toBe("");
    expect(component.isSaving).toBeFalse();
  });

  it("navigates after successful daily save even when analysis save-back fails", () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "A full daily entry";
    component.isEditing = true;
    component.editingId = 123;

    const updatedDailyEntry: DailyEntry = {
      id: 123,
      entry_date: "2026-05-30",
    };

    const dailyAnalysis: DailyAnalysisResponse = {
      ai_response: "analysis",
      tags: "daily,reflection",
      daily_people_names: "",
      daily_places: "",
    };

    entriesServiceMock.updateDailyEntry.and.returnValues(
      of(updatedDailyEntry),
      throwError(() => new Error("save analysis failed")),
    );
    analysisServiceMock.analyseText.and.returnValue(of(dailyAnalysis));

    component.saveAndAnalyse();

    expect(entriesServiceMock.updateDailyEntry).toHaveBeenCalledTimes(2);
    expect(analysisServiceMock.analyseText).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 123], {
      queryParams: { analysisWarning: "ai-save-failed" },
    });
    expect(component.errorMessage).toBe("");
    expect(component.isSaving).toBeFalse();
  });

  it("navigates after successful dream save even when analysis save-back fails", () => {
    component.selectedType = "dream";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.dreamPlot = "I was flying above the sea.";
    component.selectedMood = "peaceful";
    component.selectedAIStyle = "creative";
    component.isEditing = true;
    component.editingId = 99;

    const updatedDreamEntry: DreamEntry = {
      id: 99,
      entry_date: "2026-05-30",
      plot: component.dreamPlot,
    };

    const dreamAnalysis: DreamAnalysisResponse = {
      summary: "summary",
      interpretation: "interpretation",
      image_prompt: "image prompt",
      tags: "dream,flight",
      dream_people_names: "",
      dream_places: "sea",
    };

    entriesServiceMock.updateDreamEntry.and.returnValues(
      of(updatedDreamEntry),
      throwError(() => new Error("save analysis failed")),
    );
    analysisServiceMock.analyseText.and.returnValue(of(dreamAnalysis));

    component.saveAndAnalyse();

    expect(entriesServiceMock.updateDreamEntry).toHaveBeenCalledTimes(2);
    expect(entriesServiceMock.updateDreamEntry).toHaveBeenCalledWith(
      99,
      jasmine.objectContaining({
        entry_date: "2026-05-30",
        mood: "peaceful",
        ai_style: "creative",
      }),
    );
    expect(analysisServiceMock.analyseText).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 99], {
      queryParams: { analysisWarning: "ai-save-failed" },
    });
    expect(component.errorMessage).toBe("");
    expect(component.isSaving).toBeFalse();
  });

  it("keeps primary save failure blocking with no navigation and an error", () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "A full daily entry";
    component.isEditing = true;
    component.editingId = 7;

    entriesServiceMock.updateDailyEntry.and.returnValue(
      throwError(() => new Error("primary save failed")),
    );

    component.saveAndAnalyse();

    expect(analysisServiceMock.analyseText).not.toHaveBeenCalled();
    expect(routerMock.navigate).not.toHaveBeenCalled();
    expect(component.errorMessage).toBe("Failed to update your daily entry.");
    expect(component.isSaving).toBeFalse();
  });

  it("normalises legacy AI style values to current selector options", () => {
    expect(component["normaliseAIStyleValue"]("professional-clinical")).toBe(
      "clinical",
    );
    expect(component["normaliseAIStyleValue"]("Reflective & Deep")).toBe(
      "reflective",
    );
    expect(component["normaliseAIStyleValue"]("creative_symbolic")).toBe(
      "creative",
    );
    expect(component["normaliseAIStyleValue"]("minimal")).toBe("brief");
    expect(component["normaliseAIStyleValue"]("unknown-style")).toBe(
      "friendly",
    );
  });

  it("runs analysis for create flow when AI toggle is enabled", () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "Created daily entry";
    component.leaveItToAI = true;
    component.isEditing = false;

    const createdDailyEntry: DailyEntry = {
      id: 55,
      entry_date: "2026-05-30",
    };
    const dailyAnalysis: DailyAnalysisResponse = {
      ai_response: "analysis",
      tags: "daily,reflection",
      daily_people_names: "",
      daily_places: "",
    };

    entriesServiceMock.createDailyEntry.and.returnValue(of(createdDailyEntry));
    analysisServiceMock.analyseText.and.returnValue(of(dailyAnalysis));
    entriesServiceMock.updateDailyEntry.and.returnValue(of(createdDailyEntry));

    component.saveAndAnalyse();

    expect(entriesServiceMock.createDailyEntry).toHaveBeenCalledTimes(1);
    expect(analysisServiceMock.analyseText).toHaveBeenCalledTimes(1);
    expect(entriesServiceMock.updateDailyEntry).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 55], {
      queryParams: undefined,
    });
  });

  it("reveals attachments after create flow saves pending files", () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "Created daily entry with attachments";
    component.leaveItToAI = true;
    component.isEditing = false;
    (component as any).pendingAttachments = [
      {
        file: new File(["attachment"], "notes.pdf", {
          type: "application/pdf",
        }),
        previewUrl: null,
        kind: "pdf",
      },
    ];

    const createdDailyEntry: DailyEntry = {
      id: 56,
      entry_date: "2026-05-30",
    };
    const dailyAnalysis: DailyAnalysisResponse = {
      ai_response: "analysis",
      tags: "daily,reflection",
      daily_people_names: "",
      daily_places: "",
    };

    entriesServiceMock.createDailyEntry.and.returnValue(of(createdDailyEntry));
    entriesServiceMock.uploadDailyAttachment.and.returnValue(
      of({
        entry_id: 56,
        entry_type: "daily",
        attachment: {
          id: 1,
          original_filename: "notes.pdf",
          mime_type: "application/pdf",
          file_size_bytes: 10,
          sort_order: 0,
          created_at: "",
          derived_text: "",
          derived_text_source: "",
          derived_text_updated_at: "",
          has_derived_text: false,
          url: "http://localhost/media/notes.pdf",
          is_image: false,
          is_audio: false,
          is_pdf: true,
          asset_role: "attachment",
        },
      }),
    );
    analysisServiceMock.analyseText.and.returnValue(of(dailyAnalysis));
    entriesServiceMock.updateDailyEntry.and.returnValue(of(createdDailyEntry));

    component.saveAndAnalyse();

    expect(entriesServiceMock.uploadDailyAttachment).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 56], {
      queryParams: { showAttachments: "1" },
    });
  });

  it("defaults attachment AI context to off when the user setting is undefined", () => {
    authServiceMock.getCurrentUser.and.returnValue({
      id: 1,
      username: "tester",
    } as any);

    (component as any).applyAttachmentContextDefault();

    expect(component.allowAiAttachmentContext).toBeFalse();
  });

  it("uses app dialog confirmation before leaving with unsaved changes", async () => {
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "Unsaved content";
    appDialogMock.confirm.and.resolveTo(false);

    const result = await component.canDeactivate();

    expect(result).toBeFalse();
    expect(appDialogMock.confirm).toHaveBeenCalledWith(
      jasmine.objectContaining({
        title: "Discard this entry?",
        confirmText: "Discard changes",
        variant: "danger",
      }),
    );
  });

  it("uses app dialog confirmation before switching entry type with filled fields", async () => {
    component.selectedType = "daily";
    (component as any).previousSelectedType = "daily";
    component.content = "Daily only content";
    appDialogMock.confirm.and.resolveTo(false);

    await component.onTypeChange({ value: "dream" } as any);

    expect(component.selectedType).toBe("daily");
    expect(appDialogMock.confirm).toHaveBeenCalledWith(
      jasmine.objectContaining({
        title: "Switch entry type?",
        confirmText: "Switch type",
      }),
    );
  });

  it("creates an important day inside the new-entry workflow", async () => {
    component.selectedType = "important-day";
    component.entryDate = new Date(2026, 6, 3);
    component.importantDayLabel = "Health check";
    importantDaysServiceMock.createImportantDay.and.returnValue(
      of({ id: 7 } as any),
    );

    await component.saveEmbeddedWorkflow();

    expect(importantDaysServiceMock.createImportantDay).toHaveBeenCalledWith(
      jasmine.objectContaining({
        label: "Health check",
        starts_on: "2026-07-03",
        original_year: 2026,
      }),
    );
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries"], {
      queryParams: jasmine.objectContaining({
        display: "calendar",
        month: 7,
        year: 2026,
      }),
    });
  });

  it("creates a thought record inside the new-entry workflow", async () => {
    component.selectedType = "thought-record";
    component.entryDate = new Date(2026, 6, 3);
    component.thoughtRecordTitle = "Appointment worry";
    component.thoughtRecordSituation = "I felt tense before the appointment.";
    component.thoughtRecordUnhelpfulThoughts = "Something bad will happen.";
    cbtServiceMock.createWorksheet.and.returnValue(
      of({ id: 8 } as CbtWorksheet),
    );

    await component.saveEmbeddedWorkflow();

    expect(cbtServiceMock.createWorksheet).toHaveBeenCalledWith(
      jasmine.objectContaining({
        title: "Appointment worry",
        record_date: "2026-07-03",
        situation: "I felt tense before the appointment.",
        unhelpful_thoughts: "Something bad will happen.",
      }),
    );
  });

  it("adds a warning query param when analysis fails with 429 rate-limit", () => {
    component.selectedType = "daily";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.content = "Created daily entry";
    component.leaveItToAI = true;
    component.isEditing = false;

    const createdDailyEntry: DailyEntry = {
      id: 88,
      entry_date: "2026-05-30",
    };

    entriesServiceMock.createDailyEntry.and.returnValue(of(createdDailyEntry));
    analysisServiceMock.analyseText.and.returnValue(
      throwError(
        () =>
          new HttpErrorResponse({
            status: 429,
            error: { error: "insufficient_quota" },
          }),
      ),
    );

    component.saveAndAnalyse();

    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 88], {
      queryParams: { analysisWarning: "ai-rate-limit" },
    });
  });

  it("blocks saving when the selected date is in the future", () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);

    component.selectedType = "daily";
    component.entryDate = tomorrow;
    component.content = "A future daily entry";

    component.saveAsDraft();

    expect(entriesServiceMock.createDailyEntry).not.toHaveBeenCalled();
    expect(entriesServiceMock.updateDailyEntry).not.toHaveBeenCalled();
    expect(component.errorMessage).toBe(
      "Entries cannot be created or moved to a future date.",
    );
    expect(component.isSaving).toBeFalse();
  });

  it("blocks saving when a future date is typed into the date field", () => {
    component.selectedType = "daily";
    component.entryDate = "2999-01-01";
    component.content = "A manually typed future daily entry";

    component.saveAsDraft();

    expect(entriesServiceMock.createDailyEntry).not.toHaveBeenCalled();
    expect(component.errorMessage).toBe(
      "Entries cannot be created or moved to a future date.",
    );
  });

  it("shows a human-readable UK date label for the selected date", () => {
    component.entryDate = new Date(2026, 4, 1);

    expect(component.getReadableEntryDateLabel()).toBe("Friday 1st May 2026");
  });

  it("locks the form controls while saving", () => {
    component.isSaving = true;
    fixture.detectChanges();

    const formShell = fixture.nativeElement.querySelector(
      ".entry-form-shell",
    ) as HTMLFieldSetElement | null;

    expect(formShell?.disabled).toBeTrue();
  });

  it("uses tab to commit chip input text without moving on when text is present", () => {
    const preventDefault = jasmine.createSpy("preventDefault");
    const input = document.createElement("input");
    input.value = "Katie";

    component.handleChipInputTab(
      {
        shiftKey: false,
        target: input,
        preventDefault,
      } as unknown as KeyboardEvent,
      component.peopleNames,
    );

    expect(component.peopleNames).toEqual(["Katie"]);
    expect(input.value).toBe("");
    expect(preventDefault).toHaveBeenCalled();
  });

  it("allows normal tab navigation when a chip input is empty", () => {
    const preventDefault = jasmine.createSpy("preventDefault");
    const input = document.createElement("input");
    input.value = "   ";

    component.handleChipInputTab(
      {
        shiftKey: false,
        target: input,
        preventDefault,
      } as unknown as KeyboardEvent,
      component.tags,
    );

    expect(component.tags).toEqual([]);
    expect(preventDefault).not.toHaveBeenCalled();
  });

  it("uses the correct ordinal suffixes for teen dates", () => {
    component.entryDate = new Date(2026, 5, 13);

    expect(component.getReadableEntryDateLabel()).toBe(
      "Saturday 13th June 2026",
    );
  });
});
