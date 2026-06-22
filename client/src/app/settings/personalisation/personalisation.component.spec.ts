import { ComponentFixture, TestBed } from "@angular/core/testing";
import { of } from "rxjs";
import { ProfileService } from "../../core/services/profile.service";
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

    await TestBed.configureTestingModule({
      imports: [PersonalisationComponent],
      providers: [{ provide: ProfileService, useValue: profileServiceStub }],
    }).compileComponents();

    fixture = TestBed.createComponent(PersonalisationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it("defaults attachment AI context to off when the profile value is undefined", () => {
    expect(component.settings?.allow_ai_attachment_context).toBeFalse();
  });
});
