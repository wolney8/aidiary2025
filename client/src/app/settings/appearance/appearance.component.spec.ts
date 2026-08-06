import { ComponentFixture, TestBed } from "@angular/core/testing";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { AppearanceComponent } from "./appearance.component";
import { ThemeService } from "../../core/services/theme.service";

describe("AppearanceComponent", () => {
  let fixture: ComponentFixture<AppearanceComponent>;
  let component: AppearanceComponent;
  let themeService: ThemeService;

  beforeEach(async () => {
    localStorage.removeItem("openmynd_theme_mode");
    localStorage.removeItem("openmynd_theme_preset");
    localStorage.removeItem("ai_diary_theme_mode");
    localStorage.removeItem("ai_diary_theme_preset");

    await TestBed.configureTestingModule({
      imports: [AppearanceComponent, NoopAnimationsModule],
    }).compileComponents();

    fixture = TestBed.createComponent(AppearanceComponent);
    component = fixture.componentInstance;
    themeService = TestBed.inject(ThemeService);
    fixture.detectChanges();
  });

  afterEach(() => {
    localStorage.removeItem("openmynd_theme_mode");
    localStorage.removeItem("openmynd_theme_preset");
    localStorage.removeItem("ai_diary_theme_mode");
    localStorage.removeItem("ai_diary_theme_preset");
  });

  it("renders mode and preset choices", () => {
    const element = fixture.nativeElement as HTMLElement;

    expect(element.querySelector('[data-testid="appearance-mode-auto"]')).toBeTruthy();
    expect(element.querySelector('[data-testid="appearance-mode-light"]')).toBeTruthy();
    expect(element.querySelector('[data-testid="appearance-mode-dark"]')).toBeTruthy();
    expect(element.querySelector('[data-testid="appearance-preset-default"]')).toBeTruthy();
    expect(element.querySelector('[data-testid="appearance-preset-ocean"]')).toBeTruthy();
    expect(element.querySelector('[data-testid="appearance-preset-forest"]')).toBeTruthy();
  });

  it("applies appearance changes immediately", () => {
    component.setPreference("dark");
    component.setPreset("ocean");
    fixture.detectChanges();

    expect(themeService.mode()).toBe("dark");
    expect(themeService.preset()).toBe("ocean");
    expect(component.getCurrentThemeSummary()).toBe("Ocean · Dark");
  });
});
