import { Component } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { Location } from "@angular/common";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { Router, provideRouter } from "@angular/router";
import { of } from "rxjs";
import { ProfileService } from "../core/services/profile.service";
import { User } from "../core/models/user.model";
import { ProfileComponent } from "./profile.component";

@Component({
  template: "",
  standalone: true,
})
class DummyEntriesComponent {}

describe("ProfileComponent", () => {
  let fixture: ComponentFixture<ProfileComponent>;
  let component: ProfileComponent;
  let location: Location;
  let router: Router;

  const profileServiceStub: Pick<
    ProfileService,
    "getProfile" | "updateProfile"
  > = {
    getProfile: () =>
      of({
        id: 1,
        username: "tester",
      } satisfies User),
    updateProfile: () => of({ message: "ok" }),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ProfileComponent, NoopAnimationsModule],
      providers: [
        {
          provide: ProfileService,
          useValue: profileServiceStub,
        },
        provideRouter([
          {
            path: "entries",
            component: DummyEntriesComponent,
          },
        ]),
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(ProfileComponent);
    component = fixture.componentInstance;
    location = TestBed.inject(Location);
    router = TestBed.inject(Router);
    fixture.detectChanges();
  });

  it("renders a back button", () => {
    const host = fixture.nativeElement as HTMLElement;
    const backButton = host.querySelector("button.header-back");

    expect(backButton)
      .withContext("profile page should render a top back button")
      .not.toBeNull();
    expect(backButton?.textContent).toContain("Back");
  });

  it("uses browser history when available", () => {
    spyOn<any>(component, "canGoBack").and.returnValue(true);
    const backSpy = spyOn(location, "back");
    const navigateSpy = spyOn(router, "navigateByUrl");

    component.goBack();

    expect(backSpy).toHaveBeenCalled();
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it("falls back to entries when browser history is unavailable", () => {
    spyOn<any>(component, "canGoBack").and.returnValue(false);
    const backSpy = spyOn(location, "back");
    const navigateSpy = spyOn(router, "navigateByUrl").and.resolveTo(true);

    component.goBack();

    expect(backSpy).not.toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith("/entries");
  });
});
