import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router, convertToParamMap } from "@angular/router";
import { of, throwError } from "rxjs";
import { CreateComponent } from "./create.component";
import { EntriesService } from "../../core/services/entries.service";
import { AnalysisService } from "../../core/services/analysis.service";
import {
  DailyAnalysisResponse,
  DailyEntry,
  DreamAnalysisResponse,
  DreamEntry,
} from "../../core/models/entry.model";

describe("CreateComponent save reliability", () => {
  let fixture: ComponentFixture<CreateComponent>;
  let component: CreateComponent;
  let routerMock: jasmine.SpyObj<Router>;
  let entriesServiceMock: jasmine.SpyObj<EntriesService>;
  let analysisServiceMock: jasmine.SpyObj<AnalysisService>;

  beforeEach(async () => {
    routerMock = jasmine.createSpyObj<Router>("Router", ["navigate"]);

    entriesServiceMock = jasmine.createSpyObj<EntriesService>(
      "EntriesService",
      [
        "createDailyEntry",
        "updateDailyEntry",
        "createDreamEntry",
        "updateDreamEntry",
        "getDailyEntry",
        "getDreamEntry",
      ],
    );

    analysisServiceMock = jasmine.createSpyObj<AnalysisService>(
      "AnalysisService",
      ["analyseText"],
    );

    await TestBed.configureTestingModule({
      imports: [CreateComponent],
      providers: [
        { provide: Router, useValue: routerMock },
        { provide: EntriesService, useValue: entriesServiceMock },
        { provide: AnalysisService, useValue: analysisServiceMock },
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
    expect(analysisServiceMock.analyseText).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 42]);
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
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 123]);
    expect(component.errorMessage).toBe("");
    expect(component.isSaving).toBeFalse();
  });

  it("navigates after successful dream save even when analysis save-back fails", () => {
    component.selectedType = "dream";
    component.entryDate = new Date("2026-05-30T10:00:00.000Z");
    component.dreamPlot = "I was flying above the sea.";
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
    expect(analysisServiceMock.analyseText).toHaveBeenCalledTimes(1);
    expect(routerMock.navigate).toHaveBeenCalledWith(["/entries", 99]);
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
});
