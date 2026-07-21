import { ComponentFixture, TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router } from "@angular/router";
import { MatDialog } from "@angular/material/dialog";
import { of, throwError } from "rxjs";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { CbtService } from "../../core/services/cbt.service";
import { EntriesService } from "../../core/services/entries.service";
import { DetailComponent } from "./detail.component";

describe("DetailComponent entry routing", () => {
  let fixture: ComponentFixture<DetailComponent>;
  let getDailyEntry: jasmine.Spy;
  let getDreamEntry: jasmine.Spy;
  let openDialog: jasmine.Spy;
  let entryType: string | null;

  beforeEach(async () => {
    entryType = "dream";
    getDailyEntry = jasmine.createSpy("getDailyEntry");
    openDialog = jasmine.createSpy("open");
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
        {
          provide: MatDialog,
          useValue: { open: openDialog },
        },
        {
          provide: CbtService,
          useValue: {
            listWorksheets: jasmine
              .createSpy("listWorksheets")
              .and.returnValue(of([])),
            createWorksheet: jasmine.createSpy("createWorksheet"),
          },
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

  it("opens image attachments together in the entry gallery", () => {
    const component = createComponent();
    component.entry = {
      id: 7,
      attachments: [
        {
          id: 1,
          original_filename: "one.jpg",
          url: "/media/one.jpg",
          is_image: true,
        },
        {
          id: 2,
          original_filename: "notes.pdf",
          url: "/media/notes.pdf",
          is_pdf: true,
        },
        {
          id: 3,
          original_filename: "two.jpg",
          url: "/media/two.jpg",
          is_image: true,
        },
      ],
    };

    component.openAttachmentImageGallery(component.entry.attachments[2]);

    expect(openDialog).toHaveBeenCalled();
    const config = openDialog.calls.mostRecent().args[1];
    expect(config.data.initialImageId).toBe(3);
    expect(config.data.images.map((image: { id: number }) => image.id)).toEqual([
      1,
      3,
    ]);
  });
});
