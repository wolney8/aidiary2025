import { ComponentFixture, TestBed } from "@angular/core/testing";
import { Location } from "@angular/common";
import { By } from "@angular/platform-browser";
import { provideNoopAnimations } from "@angular/platform-browser/animations";
import { provideRouter, Router } from "@angular/router";
import { SettingsComponent } from "./settings.component";

describe("SettingsComponent", () => {
  let fixture: ComponentFixture<SettingsComponent>;
  let component: SettingsComponent;
  let router: Router;
  let location: Location;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [provideNoopAnimations(), provideRouter([])],
    }).compileComponents();

    fixture = TestBed.createComponent(SettingsComponent);
    component = fixture.componentInstance;
    router = TestBed.inject(Router);
    location = TestBed.inject(Location);
    spyOn(component, "isLandingPage").and.returnValue(true);
    fixture.detectChanges();
  });

  it("shows a landing card link to API Keys", () => {
    const apiKeysLink = fixture.debugElement.query(
      By.css('a[routerLink="/settings/api-keys"]'),
    );

    expect(apiKeysLink).toBeTruthy();
  });

  it("shows a landing card link to AI Coach", () => {
    const aiCoachLink = fixture.debugElement.query(
      By.css('a[routerLink="/settings/ai-coach"]'),
    );

    expect(aiCoachLink).toBeTruthy();
  });

  it("shows a back button on child pages", () => {
    spyOnProperty(router, "url", "get").and.returnValue("/settings/import");
    (component.isLandingPage as jasmine.Spy).and.returnValue(false);

    fixture.detectChanges();

    const backButton = fixture.debugElement.query(By.css("button.header-back"));
    const breadcrumb = fixture.debugElement.query(By.css("app-breadcrumb"));

    expect(backButton).toBeTruthy();
    expect(backButton.nativeElement.textContent).toContain("Back");
    expect(breadcrumb).toBeNull();
  });

  it("uses browser history when available", () => {
    spyOn<any>(component, "canGoBack").and.returnValue(true);
    const backSpy = spyOn(location, "back");
    const navigateSpy = spyOn(router, "navigateByUrl");

    component.goBack();

    expect(backSpy).toHaveBeenCalled();
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it("falls back to settings when browser history is unavailable", () => {
    spyOn<any>(component, "canGoBack").and.returnValue(false);
    const backSpy = spyOn(location, "back");
    const navigateSpy = spyOn(router, "navigateByUrl").and.resolveTo(true);

    component.goBack();

    expect(backSpy).not.toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith("/settings");
  });
});
