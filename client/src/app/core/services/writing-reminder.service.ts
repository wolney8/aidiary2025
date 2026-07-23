import { Injectable, OnDestroy, inject } from "@angular/core";
import { forkJoin, merge, of, Subject, timer } from "rxjs";
import { catchError, switchMap, takeUntil, withLatestFrom } from "rxjs/operators";
import { AuthService } from "./auth.service";
import { CbtService } from "./cbt.service";
import { EntriesService } from "./entries.service";
import { ImportJobService } from "./import-job.service";
import { DailyEntry, DreamEntry } from "../models/entry.model";
import { CbtWorksheet } from "../models/cbt.model";
import { User } from "../models/user.model";

const CHECK_INTERVAL_MS = 10 * 60 * 1000;
const WEEKDAYS = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
];

@Injectable({ providedIn: "root" })
export class WritingReminderService implements OnDestroy {
  private readonly authService = inject(AuthService);
  private readonly cbtService = inject(CbtService);
  private readonly entriesService = inject(EntriesService);
  private readonly notificationService = inject(ImportJobService);
  private readonly destroy$ = new Subject<void>();
  private started = false;

  start(): void {
    if (this.started) {
      return;
    }
    this.started = true;

    merge(timer(2000, CHECK_INTERVAL_MS), this.authService.currentUser$)
      .pipe(
        withLatestFrom(this.authService.currentUser$),
        switchMap(([, user]) => this.evaluateForUser(user)),
        takeUntil(this.destroy$),
      )
      .subscribe();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  private evaluateForUser(user: User | null) {
    if (!user || !this.shouldCheckReminderToday(user)) {
      return of(null);
    }

    const selectedTypes = this.getSelectedEntryTypes(user);

    return forkJoin({
      dailyEntries: selectedTypes.includes("daily")
        ? this.entriesService.getDailyEntries().pipe(catchError(() => of([])))
        : of([]),
      dreamEntries: selectedTypes.includes("dream")
        ? this.entriesService.getDreamEntries().pipe(catchError(() => of([])))
        : of([]),
      thoughtRecords: selectedTypes.includes("thought_record")
        ? this.cbtService.listWorksheets().pipe(catchError(() => of([])))
        : of([]),
    }).pipe(
      switchMap(({ dailyEntries, dreamEntries, thoughtRecords }) => {
        this.publishReminderIfDue(user, dailyEntries, dreamEntries, thoughtRecords);
        return of(null);
      }),
    );
  }

  private shouldCheckReminderToday(user: User): boolean {
    if (!user.writing_reminders_enabled) {
      return false;
    }

    const now = new Date();
    const selectedDays = String(user.writing_reminder_days || "")
      .split(",")
      .map((day) => day.trim().toLowerCase())
      .filter(Boolean);
    if (!selectedDays.includes(WEEKDAYS[now.getDay()])) {
      return false;
    }

    const reminderTime = String(user.writing_reminder_time || "19:00").trim();
    const [hour, minute] = reminderTime.split(":").map((part) => Number(part));
    if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
      return false;
    }

    const reminderDate = new Date(now);
    reminderDate.setHours(hour, minute, 0, 0);
    return now >= reminderDate;
  }

  private publishReminderIfDue(
    user: User,
    dailyEntries: DailyEntry[],
    dreamEntries: DreamEntry[],
    thoughtRecords: CbtWorksheet[],
  ): void {
    const todayKey = this.toDateKey(new Date());
    const notificationId = `writing-reminder-${user.id}-${todayKey}`;
    const records = [
      ...dailyEntries.map((entry) => this.toRecordDate(entry.entry_date)),
      ...dreamEntries.map((entry) => this.toRecordDate(entry.entry_date)),
      ...thoughtRecords.map((record) => this.toRecordDate(record.record_date)),
    ].filter((dateKey): dateKey is string => Boolean(dateKey));
    const latestEntryDate = this.getLatestRecordDate(records);
    const silenceDays = Math.min(
      Math.max(Number(user.writing_reminder_silence_days || 3), 1),
      30,
    );
    const daysSinceLastEntry = latestEntryDate
      ? this.getDateDifferenceInDays(latestEntryDate, todayKey)
      : null;

    if (daysSinceLastEntry !== null && daysSinceLastEntry < silenceDays) {
      return;
    }

    const weekCount = this.countRecordsSince(records, this.getStartOfWeekKey());
    const monthCount = this.countRecordsSince(records, this.getStartOfMonthKey());
    const quietCopy =
      daysSinceLastEntry === null
        ? "No entries yet."
        : `No entries in ${daysSinceLastEntry} day${daysSinceLastEntry === 1 ? "" : "s"}.`;

    this.notificationService.publishWritingReminder({
      id: notificationId,
      title: "Writing reminder",
      message: `${quietCopy} Counted records this week: ${weekCount}; this month: ${monthCount}.`,
      destination: `/entries/create?date=${todayKey}`,
    });
  }

  private getSelectedEntryTypes(user: User): string[] {
    const selectedTypes = String(user.writing_reminder_entry_types || "daily,dream")
      .split(",")
      .map((entryType) => entryType.trim().toLowerCase().replace("-", "_"))
      .filter(Boolean);
    return selectedTypes.length > 0 ? selectedTypes : ["daily", "dream"];
  }

  private getLatestRecordDate(recordDates: string[]): string | null {
    return [...recordDates].sort().at(-1) || null;
  }

  private countRecordsSince(recordDates: string[], startDateKey: string): number {
    return recordDates.filter((recordDate) => recordDate >= startDateKey).length;
  }

  private toRecordDate(value: string | undefined | null): string | null {
    const dateKey = String(value || "").slice(0, 10);
    return /^\d{4}-\d{2}-\d{2}$/.test(dateKey) ? dateKey : null;
  }

  private getDateDifferenceInDays(fromDateKey: string, toDateKey: string): number {
    const from = new Date(`${fromDateKey}T00:00:00`);
    const to = new Date(`${toDateKey}T00:00:00`);
    return Math.floor((to.getTime() - from.getTime()) / 86_400_000);
  }

  private getStartOfWeekKey(): string {
    const date = new Date();
    const offset = (date.getDay() + 6) % 7;
    date.setDate(date.getDate() - offset);
    return this.toDateKey(date);
  }

  private getStartOfMonthKey(): string {
    const date = new Date();
    date.setDate(1);
    return this.toDateKey(date);
  }

  private toDateKey(date: Date): string {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }
}
