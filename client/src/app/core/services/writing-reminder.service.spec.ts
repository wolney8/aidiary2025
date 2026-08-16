import { TestBed } from "@angular/core/testing";
import { BehaviorSubject, of } from "rxjs";
import { CbtService } from "./cbt.service";
import { EntriesService } from "./entries.service";
import { ImportJobService } from "./import-job.service";
import { AuthService } from "./auth.service";
import { User } from "../models/user.model";
import { WritingReminderService } from "./writing-reminder.service";
import { DailyEntry, DreamEntry } from "../models/entry.model";
import { CbtWorksheet } from "../models/cbt.model";

interface WritingReminderInternals {
  evaluateForUser(user: User | null): unknown;
  shouldCheckReminderToday(user: User): boolean;
  getSelectedEntryTypes(user: User): string[];
  publishReminderIfDue(
    user: User,
    dailyEntries: DailyEntry[],
    dreamEntries: DreamEntry[],
    thoughtRecords: CbtWorksheet[],
  ): void;
}

describe("WritingReminderService", () => {
  let currentUserSubject: BehaviorSubject<User | null>;
  let entriesService: jasmine.SpyObj<EntriesService>;
  let cbtService: jasmine.SpyObj<CbtService>;
  let notificationService: jasmine.SpyObj<ImportJobService>;
  let service: WritingReminderService;
  let internals: WritingReminderInternals;

  const reminderUser: User = {
    id: 7,
    username: "tester",
    writing_reminders_enabled: true,
    writing_reminder_days: "sunday",
    writing_reminder_time: "19:00",
    writing_reminder_silence_days: 3,
    writing_reminder_entry_types: "daily,dream",
  };

  beforeEach(() => {
    jasmine.clock().install();
    jasmine.clock().mockDate(new Date("2026-07-26T20:00:00"));
    currentUserSubject = new BehaviorSubject<User | null>(null);
    entriesService = jasmine.createSpyObj<EntriesService>("EntriesService", [
      "getDailyEntries",
      "getDreamEntries",
    ]);
    cbtService = jasmine.createSpyObj<CbtService>("CbtService", ["listWorksheets"]);
    notificationService = jasmine.createSpyObj<ImportJobService>("ImportJobService", [
      "publishWritingReminder",
    ]);
    entriesService.getDailyEntries.and.returnValue(of([]));
    entriesService.getDreamEntries.and.returnValue(of([]));
    cbtService.listWorksheets.and.returnValue(of([]));

    TestBed.configureTestingModule({
      providers: [
        WritingReminderService,
        {
          provide: AuthService,
          useValue: { currentUser$: currentUserSubject.asObservable() },
        },
        { provide: EntriesService, useValue: entriesService },
        { provide: CbtService, useValue: cbtService },
        { provide: ImportJobService, useValue: notificationService },
      ],
    });
    service = TestBed.inject(WritingReminderService);
    internals = service as unknown as WritingReminderInternals;
  });

  afterEach(() => {
    service.ngOnDestroy();
    jasmine.clock().uninstall();
  });

  it("detects when the configured reminder day and time are due", () => {
    expect(internals.shouldCheckReminderToday(reminderUser)).toBeTrue();

    jasmine.clock().mockDate(new Date("2026-07-26T18:59:00"));

    expect(internals.shouldCheckReminderToday(reminderUser)).toBeFalse();
  });

  it("normalises selected record types for reminder checks", () => {
    expect(
      internals.getSelectedEntryTypes({
        ...reminderUser,
        writing_reminder_entry_types: "thought-record,daily",
      }),
    ).toEqual(["thought_record", "daily"]);
    expect(
      internals.getSelectedEntryTypes({
        ...reminderUser,
        writing_reminder_entry_types: "",
      }),
    ).toEqual(["daily", "dream"]);
  });

  it("publishes a writing reminder after the chosen quiet gap", () => {
    internals.publishReminderIfDue(reminderUser, [], [], []);

    expect(notificationService.publishWritingReminder).toHaveBeenCalledWith(
      jasmine.objectContaining({
        id: "writing-reminder-7-2026-07-26",
        title: "Writing reminder",
        message: "No entries yet. Counted records this week: 0; this month: 0.",
        destination: "/entries/create?date=2026-07-26",
      }),
    );
  });

  it("does not publish when a selected record type was used inside the quiet gap", () => {
    internals.publishReminderIfDue(
      reminderUser,
      [{ entry_date: "2026-07-25" } as DailyEntry],
      [],
      [],
    );

    expect(notificationService.publishWritingReminder).not.toHaveBeenCalled();
  });

  it("counts thought records when the user selects them as writing", () => {
    internals.publishReminderIfDue(
      {
        ...reminderUser,
        writing_reminder_entry_types: "thought-record",
      },
      [],
      [],
      [{ record_date: "2026-07-10" } as CbtWorksheet],
    );

    expect(notificationService.publishWritingReminder).toHaveBeenCalledWith(
      jasmine.objectContaining({
        message: "No entries in 16 days. Counted records this week: 0; this month: 1.",
      }),
    );
  });

  it("does not refetch records repeatedly for the same due reminder settings", () => {
    (internals.evaluateForUser(reminderUser) as { subscribe: () => void }).subscribe();
    (internals.evaluateForUser(reminderUser) as { subscribe: () => void }).subscribe();

    expect(entriesService.getDailyEntries).toHaveBeenCalledTimes(1);
    expect(entriesService.getDreamEntries).toHaveBeenCalledTimes(1);
  });
});
