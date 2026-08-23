import { TestBed, fakeAsync, tick } from "@angular/core/testing";
import { Subscription, of, throwError } from "rxjs";
import { AppNotification, ImportJobService } from "./import-job.service";
import { ImportJobStatus, ImportService } from "./import.service";

interface ImportJobServiceInternals {
  publishJob(job: ImportJobStatus): void;
  startPolling(jobId: string): void;
}

describe("ImportJobService writing reminders", () => {
  let importService: jasmine.SpyObj<ImportService>;
  let service: ImportJobService;
  let internals: ImportJobServiceInternals;
  let notifications: AppNotification[];
  let subscription: Subscription;

  beforeEach(() => {
    localStorage.clear();
    notifications = [];
    importService = jasmine.createSpyObj<ImportService>("ImportService", ["getImportJob"]);
    importService.getImportJob.and.returnValue(
      of({
        id: "unused-job",
        status: "running",
        processed: 0,
        total: 0,
        percent: 0,
        message: "",
        created_at: "2026-07-26T10:00:00Z",
        updated_at: "2026-07-26T10:00:00Z",
      }),
    );

    TestBed.configureTestingModule({
      providers: [
        ImportJobService,
        { provide: ImportService, useValue: importService },
      ],
    });
    service = TestBed.inject(ImportJobService);
    internals = service as unknown as ImportJobServiceInternals;
    subscription = service.notifications$.subscribe((items) => {
      notifications = items;
    });
  });

  afterEach(() => {
    subscription.unsubscribe();
    localStorage.clear();
  });

  it("publishes writing reminders as unread start-entry notifications", () => {
    service.publishWritingReminder({
      id: "writing-reminder-7-2026-07-26",
      title: "Writing reminder",
      message: "No entries yet.",
      destination: "/entries/create?date=2026-07-26",
    });

    expect(notifications.length).toBe(1);
    expect(notifications[0]).toEqual(
      jasmine.objectContaining({
        id: "writing-reminder-7-2026-07-26",
        kind: "writing_reminder",
        status: "completed",
        title: "Writing reminder",
        message: "No entries yet.",
        unread: true,
        destination: "/entries/create?date=2026-07-26",
        actionLabel: "Start entry",
      }),
    );
  });

  it("does not duplicate an existing reminder notification", () => {
    const reminder = {
      id: "writing-reminder-7-2026-07-26",
      title: "Writing reminder",
      message: "No entries yet.",
    };

    service.publishWritingReminder(reminder);
    service.publishWritingReminder(reminder);

    expect(notifications.length).toBe(1);
  });

  it("does not republish a dismissed reminder for the same day", () => {
    const reminder = {
      id: "writing-reminder-7-2026-07-26",
      title: "Writing reminder",
      message: "No entries yet.",
    };

    service.publishWritingReminder(reminder);
    service.dismiss(reminder.id);
    service.publishWritingReminder(reminder);

    expect(notifications).toEqual([]);
  });

  it("clears completed reminder notifications while keeping running imports", () => {
    service.publishWritingReminder({
      id: "writing-reminder-7-2026-07-26",
      title: "Writing reminder",
      message: "No entries yet.",
    });
    internals.publishJob({
      id: "import-job-1",
      status: "running",
      processed: 4,
      total: 10,
      percent: 40,
      message: "Importing entries...",
      created_at: "2026-07-26T10:00:00Z",
      updated_at: "2026-07-26T10:01:00Z",
    });

    service.clearCompleted();

    expect(notifications.length).toBe(1);
    expect(notifications[0].kind).toBe("import");
  });

  it("stops polling and clears the stored job after repeated server failures", fakeAsync(() => {
    importService.getImportJob.and.returnValue(
      throwError(() => ({ status: 500 })),
    );
    localStorage.setItem("openmynd_active_import_job", "stalled-import");
    internals.publishJob({
      id: "stalled-import",
      status: "running",
      processed: 0,
      total: 1173,
      percent: 0,
      message: "Import queued…",
      created_at: "2026-08-23T11:00:00Z",
      updated_at: "2026-08-23T11:00:00Z",
    });

    internals.startPolling("stalled-import");
    tick(1500);

    expect(localStorage.getItem("openmynd_active_import_job")).toBeNull();
    expect(notifications[0]).toEqual(
      jasmine.objectContaining({
        id: "stalled-import",
        status: "failed",
        title: "Import failed",
      }),
    );
  }));
});
