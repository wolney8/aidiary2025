import { ComponentFixture, TestBed } from "@angular/core/testing";
import { MAT_DIALOG_DATA, MatDialogRef } from "@angular/material/dialog";
import { InactivityWarningComponent } from "./inactivity-warning.component";

describe("InactivityWarningComponent", () => {
  let fixture: ComponentFixture<InactivityWarningComponent>;
  let component: InactivityWarningComponent;
  let dialogRefSpy: any;

  beforeEach(async () => {
    dialogRefSpy = jasmine.createSpyObj("MatDialogRef", ["close"]);

    await TestBed.configureTestingModule({
      imports: [InactivityWarningComponent],
      providers: [
        { provide: MatDialogRef, useValue: dialogRefSpy },
        { provide: MAT_DIALOG_DATA, useValue: { countdownSeconds: 42 } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(InactivityWarningComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("renders countdown from injected data", () => {
    expect(component.countdownSeconds).toBe(42);
    expect(fixture.nativeElement.textContent).toContain("42");
  });

  it("stay() closes dialog with 'stay'", () => {
    component.stay();

    expect(dialogRefSpy.close).toHaveBeenCalledWith("stay");
  });

  it("logout() closes dialog with 'logout'", () => {
    component.logout();

    expect(dialogRefSpy.close).toHaveBeenCalledWith("logout");
  });
});
