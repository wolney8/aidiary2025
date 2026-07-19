import { ComponentFixture, TestBed } from "@angular/core/testing";
import { of } from "rxjs";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { ProfileService } from "../../core/services/profile.service";
import { PublicHolidaysService } from "../../core/services/public-holidays.service";
import { User } from "../../core/models/user.model";
import { PersonalisationComponent } from "./personalisation.component";

describe("PersonalisationComponent", () => {
  let fixture: ComponentFixture<PersonalisationComponent>;
  let component: PersonalisationComponent;
  let updateProfileSpy: jasmine.Spy;
  let confirmSpy: jasmine.Spy;

  beforeEach(async () => {
    updateProfileSpy = jasmine.createSpy("updateProfile").and.returnValue(
      of({
        message: "Customisation saved.",
        user: {
          id: 1,
          username: "tester",
        } satisfies User,
      }),
    );
    const profileServiceStub: Pick<ProfileService, "getProfile" | "updateProfile"> = {
      getProfile: () =>
        of({
          id: 1,
          username: "tester",
          display_name: "Alex",
          custom_guidance: "Help me stay grounded",
          dailydiary_api_key: "legacy-key",
          chatgpt_daily_diary_coachname: "Legacy coach",
        } satisfies User),
      updateProfile: updateProfileSpy,
    };
    const publicHolidaysServiceStub: Pick<
      PublicHolidaysService,
      "getAvailableCountries"
    > = {
      getAvailableCountries: () => of([]),
    };
    confirmSpy = jasmine.createSpy("confirm").and.resolveTo(true);
    const appDialogServiceStub: Pick<AppDialogService, "confirm"> = {
      confirm: confirmSpy,
    };

    await TestBed.configureTestingModule({
      imports: [PersonalisationComponent],
      providers: [
        { provide: ProfileService, useValue: profileServiceStub },
        {
          provide: PublicHolidaysService,
          useValue: publicHolidaysServiceStub,
        },
        { provide: AppDialogService, useValue: appDialogServiceStub },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PersonalisationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("defaults attachment AI context to off when the profile value is undefined", () => {
    expect(component.settings?.allow_ai_attachment_context).toBeFalse();
  });

  it("shows the custom guidance counter", () => {
    expect(component.getCustomGuidanceLength()).toBe(22);
  });

  it("summarises the current AI cost profile from model and verbosity", () => {
    component.settings = {
      ...(component.settings as User),
      ai_model: "gpt-4.1",
      ai_verbosity: "detailed",
    };

    expect(component.getCurrentAiCostSummary()).toContain("higher-cost model");
    expect(component.getCurrentAiCostSummary()).toContain("higher-depth responses");
    expect(component.getCurrentModelHint()).toContain("costs more per run");
    expect(component.getCurrentVerbosityHint()).toContain("Pushes for fuller responses");
  });

  it("saves only Customisation-owned fields", () => {
    component.settings = {
      ...(component.settings as User),
      ai_tone: "empathetic",
    };

    component.saveSettings();

    const payload = updateProfileSpy.calls.mostRecent().args[0] as Partial<User>;
    expect(payload.ai_tone).toBe("empathetic");
    expect(payload.display_name).toBeUndefined();
    expect(payload.dailydiary_api_key).toBeUndefined();
    expect(payload.chatgpt_daily_diary_coachname).toBeUndefined();
    expect(component.successMessage).toBe("Customisation saved.");
  });

  it("guards navigation when settings have unsaved changes", async () => {
    component.settings = {
      ...(component.settings as User),
      timezone: "Europe/London",
    };

    await expectAsync(Promise.resolve(component.canDeactivate())).toBeResolvedTo(true);
    expect(confirmSpy).toHaveBeenCalled();
  });
});
