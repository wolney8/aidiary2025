import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router } from "@angular/router";
import { of, throwError } from "rxjs";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { EntriesService } from "../../core/services/entries.service";
import { DetailComponent } from "./detail.component";

describe("DetailComponent entry routing", () => {
  let fixture: ComponentFixture<DetailComponent>;
  let getDailyEntry: jasmine.Spy;
  let getDreamEntry: jasmine.Spy;
  let entryType: string | null;

  beforeEach(async () => {
    entryType = "dream";
    getDailyEntry = jasmine.createSpy("getDailyEntry");
    getDreamEntry = jasmine
      .createSpy("getDreamEntry")
      .and.returnValue(of({ id: 7, title: "Dream" }));

    TestBed.overrideComponent(DetailComponent, {
      set: { template: "", imports: [] },
    });

    await TestBed.configureTestingModule({
      imports: [DetailComponent],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: {
              paramMap: { get: () => "7" },
              queryParamMap: {
                get: (key: string) => (key === "entryType" ? entryType : null),
              },
              queryParams: {},
            },
          },
        },
        {
          provide: Router,
          useValue: { navigate: jasmine.createSpy("navigate") },
        },
        {
          provide: EntriesService,
          useValue: { getDailyEntry, getDreamEntry },
        },
        {
          provide: AppDialogService,
          useValue: { confirm: jasmine.createSpy("confirm") },
        },
      ],
    }).compileComponents();
  });

  function createComponent(): DetailComponent {
    fixture = TestBed.createComponent(DetailComponent);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  it("loads the requested dream type without probing the daily table", () => {
    const component = createComponent();

    expect(getDreamEntry).toHaveBeenCalledOnceWith(7);
    expect(getDailyEntry).not.toHaveBeenCalled();
    expect(component.entryType).toBe("dream");
    expect(component.isLoadingEntry).toBeFalse();
  });

  it("keeps backward-compatible daily-to-dream fallback for old links", () => {
    entryType = null;
    getDailyEntry.and.returnValue(throwError(() => ({ status: 404 })));

    const component = createComponent();

    expect(getDailyEntry).toHaveBeenCalledOnceWith(7);
    expect(getDreamEntry).toHaveBeenCalledOnceWith(7);
    expect(component.entryType).toBe("dream");
  });

  it("shows an error instead of a blank page when the requested entry fails", () => {
    getDreamEntry.and.returnValue(throwError(() => ({ status: 404 })));

    const component = createComponent();

    expect(component.entry).toBeNull();
    expect(component.isLoadingEntry).toBeFalse();
    expect(component.loadErrorMessage).toContain("could not be found");
  });
});
