import { ComponentFixture, TestBed } from "@angular/core/testing";
import { of } from "rxjs";
import { ImportService } from "../../core/services/import.service";
import { ExportComponent } from "./export.component";

describe("ExportComponent", () => {
  let fixture: ComponentFixture<ExportComponent>;
  let component: ExportComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ExportComponent],
      providers: [{
        provide: ImportService,
        useValue: {
          getBulkDeleteReadiness: () => of({ has_entries: false, total_entries: 0 }),
        },
      }],
    }).compileComponents();

    fixture = TestBed.createComponent(ExportComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("renders stable export controls and an inclusive default scope", () => {
    const host = fixture.nativeElement as HTMLElement;

    expect(host.querySelector("[data-testid='export-download-selected']")).not.toBeNull();
    expect(host.querySelector("[data-testid='export-download-all']")).not.toBeNull();
    expect(component.getExportScopeLabel()).toBe(
      "Daily, Dreams, Important Days, Thought Records selected",
    );
  });

  it("updates the scope summary when a record type is excluded", () => {
    component.onIncludeDreamsChange(false);

    expect(component.getExportScopeLabel()).toBe(
      "Daily, Important Days, Thought Records selected",
    );
  });
});
