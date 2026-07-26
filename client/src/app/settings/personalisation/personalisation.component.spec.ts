import { TestBed } from "@angular/core/testing";
import { of } from "rxjs";
import { AppDialogService } from "../../core/services/app-dialog.service";
import { ProfileService } from "../../core/services/profile.service";
import { PublicHolidaysService } from "../../core/services/public-holidays.service";
import { User } from "../../core/models/user.model";
import { PersonalisationComponent } from "./personalisation.component";

describe("PersonalisationComponent", () => {
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
      providers: [
        { provide: ProfileService, useValue: profileServiceStub },
        {
          provide: PublicHolidaysService,
          useValue: publicHolidaysServiceStub,
        },
        { provide: AppDialogService, useValue: appDialogServiceStub },
      ],
    }).compileComponents();

    component = TestBed.runInInjectionContext(() => new PersonalisationComponent());
    component.ngOnInit();
  });

  it("defaults attachment AI context to off when the profile value is undefined", () => {
    expect(component.settings?.allow_ai_attachment_context).toBeFalse();
  });

  it("defaults On this day resurfacing to off", () => {
    expect(component.settings?.show_on_this_day).toBeFalse();
  });

  it("shows the custom guidance counter", () => {
    expect(component.getCustomGuidanceLength()).toBe(21);
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
      show_on_this_day: true,
    };

    component.saveSettings();

    const payload = updateProfileSpy.calls.mostRecent().args[0] as Partial<User>;
    expect(payload.ai_tone).toBe("empathetic");
    expect(payload.show_on_this_day).toBeTrue();
    expect(payload.display_name).toBeUndefined();
    expect(payload.dailydiary_api_key).toBeUndefined();
    expect(payload.chatgpt_daily_diary_coachname).toBeUndefined();
    expect(component.successMessage).toBe("Customisation saved.");
  });

  it("normalises writing reminder and rhythm settings into the save payload", () => {
    component.settings = {
      ...(component.settings as User),
      writing_reminders_enabled: true,
      writing_reminder_days: "friday,monday,funday",
      writing_reminder_time: "18:30",
      writing_reminder_silence_days: 5,
      writing_reminder_entry_types: "thought-record,daily,gratitude",
      writing_rhythm_progress_enabled: true,
      writing_rhythm_weekly_goal: 6,
    };

    component.saveSettings();

    const payload = updateProfileSpy.calls.mostRecent().args[0] as Partial<User>;
    expect(payload.writing_reminders_enabled).toBeTrue();
    expect(payload.writing_reminder_days).toBe("monday,friday");
    expect(payload.writing_reminder_time).toBe("18:30");
    expect(payload.writing_reminder_silence_days).toBe(5);
    expect(payload.writing_reminder_entry_types).toBe("daily,thought_record");
    expect(payload.writing_rhythm_progress_enabled).toBeTrue();
    expect(payload.writing_rhythm_weekly_goal).toBe(6);
  });

  it("blocks writing reminders when no counted record types are selected", () => {
    component.settings = {
      ...(component.settings as User),
      writing_reminders_enabled: true,
      writing_reminder_days: "monday",
      writing_reminder_time: "19:00",
      writing_reminder_silence_days: 3,
      writing_reminder_entry_types: "",
    };
    updateProfileSpy.calls.reset();

    component.saveSettings();

    expect(component.errorMessage).toBe("Choose at least one record type to count as writing.");
    expect(updateProfileSpy).not.toHaveBeenCalled();
  });

  it("blocks invalid writing rhythm goals before saving", () => {
    component.settings = {
      ...(component.settings as User),
      writing_rhythm_progress_enabled: true,
      writing_rhythm_weekly_goal: 22,
    };
    updateProfileSpy.calls.reset();

    component.saveSettings();

    expect(component.errorMessage).toBe("Weekly writing goal must be between 1 and 21.");
    expect(updateProfileSpy).not.toHaveBeenCalled();
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
