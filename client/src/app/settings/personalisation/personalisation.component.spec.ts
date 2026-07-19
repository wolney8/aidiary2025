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

  beforeEach(async () => {
    const profileServiceStub: Pick<ProfileService, "getProfile" | "updateProfile"> = {
      getProfile: () =>
        of({
          id: 1,
          username: "tester",
          display_name: "Alex",
          custom_guidance: "Help me stay grounded",
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
    const publicHolidaysServiceStub: Pick<
      PublicHolidaysService,
      "getAvailableCountries"
    > = {
      getAvailableCountries: () => of([]),
    };
    const appDialogServiceStub: Pick<AppDialogService, "confirm"> = {
      confirm: async () => true,
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
});
