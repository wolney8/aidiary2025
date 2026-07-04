import { Component } from "@angular/core";
import { ComponentFixture, TestBed } from "@angular/core/testing";
import { Location } from "@angular/common";
import { NoopAnimationsModule } from "@angular/platform-browser/animations";
import { Router, provideRouter } from "@angular/router";
import { of } from "rxjs";
import { AppDialogService } from "../core/services/app-dialog.service";
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
  let appDialogServiceMock: jasmine.SpyObj<AppDialogService>;
  let updateProfileSpy: jasmine.Spy;

  const profileServiceStub: Pick<ProfileService, "getProfile" | "updateProfile"> = {
    getProfile: () =>
      of({
        id: 1,
        username: "tester",
        first_name: "Alex",
        last_name: "Taylor",
        age: 31,
        display_name: "Alex",
        pronouns: "they/them",
        gender: "non-binary",
        ai_model: "gpt-4.1-mini",
        ai_focus: "reflective",
        custom_guidance: "Keep me grounded",
      } satisfies User),
    updateProfile: () =>
      of({
        message: "ok",
        user: {
          id: 1,
          username: "tester",
        } satisfies User,
      }),
  };

  beforeEach(async () => {
    appDialogServiceMock = jasmine.createSpyObj<AppDialogService>(
      "AppDialogService",
      ["confirm"],
    );
    appDialogServiceMock.confirm.and.resolveTo(true);

    await TestBed.configureTestingModule({
      imports: [ProfileComponent, NoopAnimationsModule],
      providers: [
        {
          provide: ProfileService,
          useValue: profileServiceStub,
        },
        {
          provide: AppDialogService,
          useValue: appDialogServiceMock,
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
    updateProfileSpy = spyOn(profileServiceStub, "updateProfile").and.callThrough();
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

  it("renders account and identity fields", () => {
    const host = fixture.nativeElement as HTMLElement;
    const title = host.querySelector(".account-heading");

    expect(title?.textContent).toContain("Account and identity");
    expect(host.textContent).toContain("Display Name");
    expect(host.textContent).toContain("Pronouns");
    expect(host.textContent).toContain("Gender");
  });

  it("shows the display name counter", () => {
    expect(component.getDisplayNameLength()).toBe(4);
  });

  it("tracks pending changes after the profile is edited", () => {
    expect(component.hasPendingChanges()).toBeFalse();

    component.profile!.display_name = "Alec";

    expect(component.hasPendingChanges()).toBeTrue();
  });

  it("uses the app dialog when navigating away with unsaved profile changes", async () => {
    component.profile!.display_name = "Alec";

    const result = await component.canDeactivate();

    expect(result).toBeTrue();
    expect(appDialogServiceMock.confirm).toHaveBeenCalledWith(
      jasmine.objectContaining({
        title: "Discard Profile changes?",
      }),
    );
  });

  it("submits only profile-owned fields", () => {
    component.profile!.display_name = "Alec";
    component.onSubmit();

    expect(updateProfileSpy).toHaveBeenCalledWith({
      first_name: "Alex",
      last_name: "Taylor",
      age: 31,
      display_name: "Alec",
      pronouns: "they/them",
      gender: "non-binary",
    });
  });

  it("omits age when it is unset", () => {
    component.profile!.age = undefined;
    component.onSubmit();

    expect(updateProfileSpy).toHaveBeenCalledWith({
      first_name: "Alex",
      last_name: "Taylor",
      age: undefined,
      display_name: "Alex",
      pronouns: "they/them",
      gender: "non-binary",
    });
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
