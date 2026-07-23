import { Injectable, inject } from "@angular/core";
import { BehaviorSubject, Observable, Subscription, of, timer } from "rxjs";
import { catchError, switchMap, tap } from "rxjs/operators";
import { ImportJobStatus, ImportService } from "./import.service";

const ACTIVE_IMPORT_JOB_KEY = "ai_diary_active_import_job";
const NOTIFICATIONS_KEY = "ai_diary_notifications";
const DISMISSED_NOTIFICATIONS_KEY = "ai_diary_dismissed_notifications";

export interface AppNotification {
  id: string;
  kind: "import" | "writing_reminder";
  status: ImportJobStatus["status"];
  title: string;
  message: string;
  processed: number;
  total: number;
  percent: number;
  unread: boolean;
  isDelayed: boolean;
  createdAt: string;
  destination: string;
  actionLabel?: string;
}

@Injectable({ providedIn: "root" })
export class ImportJobService {
  private readonly importService = inject(ImportService);
  private readonly jobSubject = new BehaviorSubject<ImportJobStatus | null>(null);
  private readonly notificationsSubject = new BehaviorSubject<AppNotification[]>(
    this.restoreNotifications(),
  );
  private pollSubscription: Subscription | null = null;
  private consecutivePollErrors = 0;

  readonly job$ = this.jobSubject.asObservable();
  readonly notifications$ = this.notificationsSubject.asObservable();

  constructor() {
    const savedJobId = localStorage.getItem(ACTIVE_IMPORT_JOB_KEY);
    if (savedJobId) this.startPolling(savedJobId);
  }

  start(
    importSessionId: string,
    acceptedDuplicateRowIds: string[],
    selectedRowIds: string[],
    entryTypeOverrides: Record<string, "daily" | "dream">,
  ): Observable<ImportJobStatus> {
    return this.importService
      .startImportJob(
        importSessionId,
        acceptedDuplicateRowIds,
        selectedRowIds,
        entryTypeOverrides,
      )
      .pipe(
        tap((job) => {
          localStorage.setItem(ACTIVE_IMPORT_JOB_KEY, job.id);
          this.publishJob(job);
          this.startPolling(job.id);
        }),
      );
  }

  markRead(notificationId: string): void {
    this.updateNotifications((notifications) =>
      notifications.map((notification) =>
        notification.id === notificationId
          ? { ...notification, unread: false }
          : notification,
      ),
    );
  }

  dismiss(notificationId: string): void {
    const notification = this.notificationsSubject.value.find(
      (item) => item.id === notificationId,
    );
    if (notification?.status === "queued" || notification?.status === "running") return;
    if (notification?.kind === "writing_reminder") {
      this.rememberDismissedNotification(notificationId);
    }

    this.updateNotifications((notifications) =>
      notifications.filter((item) => item.id !== notificationId),
    );
    if (this.jobSubject.value?.id === notificationId) {
      this.clearCurrentJob();
    }
  }

  clearCompleted(): void {
    this.notificationsSubject.value
      .filter((notification) => notification.kind === "writing_reminder")
      .forEach((notification) => this.rememberDismissedNotification(notification.id));
    this.updateNotifications((notifications) =>
      notifications.filter(
        (notification) =>
          notification.status === "queued" || notification.status === "running",
      ),
    );
    const current = this.jobSubject.value;
    if (current && (current.status === "completed" || current.status === "failed")) {
      this.clearCurrentJob();
    }
  }

  publishWritingReminder(options: {
    id: string;
    title: string;
    message: string;
    destination?: string;
  }): void {
    const existingNotification = this.notificationsSubject.value.find(
      (notification) => notification.id === options.id,
    );
    if (existingNotification || this.isDismissedNotification(options.id)) {
      return;
    }
    const now = new Date().toISOString();
    const notification: AppNotification = {
      id: options.id,
      kind: "writing_reminder",
      status: "completed",
      title: options.title,
      message: options.message,
      processed: 0,
      total: 0,
      percent: 0,
      unread: true,
      isDelayed: false,
      createdAt: now,
      destination: options.destination || "/entries/create",
      actionLabel: "Start entry",
    };
    this.updateNotifications((notifications) => [
      notification,
      ...notifications,
    ]);
  }

  private startPolling(jobId: string): void {
    this.pollSubscription?.unsubscribe();
    this.consecutivePollErrors = 0;
    this.pollSubscription = timer(0, 750)
      .pipe(
        switchMap(() =>
          this.importService.getImportJob(jobId).pipe(
            catchError((error: Error & { status?: number }) => {
              this.consecutivePollErrors += 1;
              const current = this.jobSubject.value;
              if (current && (error.status === 401 || error.status === 404)) {
                return of({
                  ...current,
                  status: "failed" as const,
                  message: "Import progress is no longer available.",
                  error: "The server session ended before completion could be confirmed.",
                });
              }
              if (current && this.consecutivePollErrors >= 3) {
                this.publishJob({
                  ...current,
                  is_delayed: true,
                  message: "Progress is temporarily unavailable. The import may still be running.",
                });
              } else if (!current && this.consecutivePollErrors >= 3) {
                const now = new Date().toISOString();
                this.publishJob({
                  id: jobId,
                  status: "failed",
                  processed: 0,
                  total: 0,
                  percent: 0,
                  message: "The previous import status is no longer available.",
                  error: "The server may have restarted while the import was running.",
                  created_at: now,
                  updated_at: now,
                });
              }
              return of(null);
            }),
          ),
        ),
      )
      .subscribe((job) => {
        if (!job) return;
        this.consecutivePollErrors = 0;
        this.publishJob(job);
        if (job.status === "completed" || job.status === "failed") {
          this.pollSubscription?.unsubscribe();
          this.pollSubscription = null;
        }
      });
  }

  private publishJob(job: ImportJobStatus): void {
    const previousJob = this.jobSubject.value;
    this.jobSubject.next(job);
    const previousNotification = this.notificationsSubject.value.find(
      (notification) => notification.id === job.id,
    );
    const becameUnread =
      (job.status === "completed" || job.status === "failed") &&
      previousJob?.status !== job.status &&
      previousNotification?.status !== job.status;
    const notification: AppNotification = {
      id: job.id,
      kind: "import",
      status: job.status,
      title:
        job.status === "completed"
          ? "Import completed"
          : job.status === "failed"
            ? "Import failed"
            : "Import in progress",
      message: job.message,
      processed: job.processed,
      total: job.total,
      percent: job.percent,
      unread: becameUnread ? true : (previousNotification?.unread ?? false),
      isDelayed: job.is_delayed === true,
      createdAt: previousNotification?.createdAt ?? job.created_at,
      destination: "/settings/import",
      actionLabel: "Go to import",
    };
    this.updateNotifications((notifications) => [
      notification,
      ...notifications.filter((item) => item.id !== job.id),
    ]);
  }

  private updateNotifications(
    update: (notifications: AppNotification[]) => AppNotification[],
  ): void {
    const notifications = update(this.notificationsSubject.value).slice(0, 50);
    this.notificationsSubject.next(notifications);
    localStorage.setItem(NOTIFICATIONS_KEY, JSON.stringify(notifications));
  }

  private restoreNotifications(): AppNotification[] {
    try {
      const saved = JSON.parse(localStorage.getItem(NOTIFICATIONS_KEY) ?? "[]");
      if (!Array.isArray(saved)) {
        return [];
      }
      return saved.filter(
        (notification): notification is AppNotification =>
          typeof notification?.id === "string" &&
          typeof notification?.title === "string" &&
          typeof notification?.message === "string",
      );
    } catch {
      localStorage.removeItem(NOTIFICATIONS_KEY);
      return [];
    }
  }

  private isDismissedNotification(notificationId: string): boolean {
    try {
      const dismissed = JSON.parse(
        localStorage.getItem(DISMISSED_NOTIFICATIONS_KEY) ?? "[]",
      );
      return Array.isArray(dismissed) && dismissed.includes(notificationId);
    } catch {
      localStorage.removeItem(DISMISSED_NOTIFICATIONS_KEY);
      return false;
    }
  }

  private rememberDismissedNotification(notificationId: string): void {
    try {
      const dismissed = JSON.parse(
        localStorage.getItem(DISMISSED_NOTIFICATIONS_KEY) ?? "[]",
      );
      const dismissedIds = Array.isArray(dismissed) ? dismissed : [];
      localStorage.setItem(
        DISMISSED_NOTIFICATIONS_KEY,
        JSON.stringify([...new Set([notificationId, ...dismissedIds])].slice(0, 100)),
      );
    } catch {
      localStorage.setItem(
        DISMISSED_NOTIFICATIONS_KEY,
        JSON.stringify([notificationId]),
      );
    }
  }

  private clearCurrentJob(): void {
    this.pollSubscription?.unsubscribe();
    this.pollSubscription = null;
    localStorage.removeItem(ACTIVE_IMPORT_JOB_KEY);
    this.jobSubject.next(null);
  }
}
