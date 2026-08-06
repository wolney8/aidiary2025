import { ComponentFixture, TestBed } from "@angular/core/testing";
import { provideRouter } from "@angular/router";
import { SettingsComponent } from "./settings.component";

describe("SettingsComponent", () => {
  let fixture: ComponentFixture<SettingsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(SettingsComponent);
    fixture.detectChanges();
  });

  it("renders the supported Settings section links", () => {
    const compiled = fixture.nativeElement as HTMLElement;

    expect(compiled.querySelector("[data-testid='settings-nav-appearance']")).toBeTruthy();
    expect(
      compiled.querySelector("[data-testid='settings-nav-customisation']"),
    ).toBeTruthy();
    expect(compiled.querySelector("[data-testid='settings-nav-import']")).toBeTruthy();
    expect(compiled.querySelector("[data-testid='settings-nav-export']")).toBeTruthy();
    expect(compiled.querySelector("[data-testid='settings-nav-account']")).toBeNull();
  });

  it("keeps Important Days outside the Settings section navigation", () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const settingsLinks = Array.from(
      compiled.querySelectorAll<HTMLAnchorElement>(".settings-nav a"),
    );

    expect(settingsLinks.some((link) => link.href.includes("/important-days"))).toBeFalse();
  });
});
