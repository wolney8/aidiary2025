import { Injectable, OnDestroy } from "@angular/core";
import { BehaviorSubject, Subject } from "rxjs";

@Injectable({
  providedIn: "root",
})
export class InactivityService implements OnDestroy {
  private readonly authTokenStorageKey = "ai_diary_token";
  private readonly authUserStorageKey = "ai_diary_user";
  private readonly stayAliveSyncStorageKey = "ai_diary_inactivity_stay_alive";

  private readonly trackedEvents = [
    "mousemove",
    "mousedown",
    "keydown",
    "touchstart",
    "scroll",
  ] as const;

  private timeoutSeconds = 900;
  private warningSeconds = 60;
  private trackingEnabled = false;

  private warningTimeoutId?: ReturnType<typeof setTimeout>;
  private countdownIntervalId?: ReturnType<typeof setInterval>;

  private warningStateSubject = new BehaviorSubject<boolean>(false);
  private countdownSecondsSubject = new BehaviorSubject<number>(
    this.warningSeconds,
  );
  private expiredSubject = new Subject<void>();

  readonly warningState$ = this.warningStateSubject.asObservable();
  readonly countdownSeconds$ = this.countdownSecondsSubject.asObservable();
  readonly expired$ = this.expiredSubject.asObservable();

  startTracking(timeoutSeconds: number, warningSeconds: number): void {
    const safeWarningSeconds = Math.max(1, Math.floor(warningSeconds));
    const safeTimeoutSeconds = Math.max(
      Math.floor(timeoutSeconds),
      safeWarningSeconds + 1,
    );

    this.timeoutSeconds = safeTimeoutSeconds;
    this.warningSeconds = safeWarningSeconds;

    if (!this.trackingEnabled) {
      this.trackingEnabled = true;
      this.attachListeners();
    }

    this.resetTimer(false);
  }

  stopTracking(): void {
    if (!this.trackingEnabled) {
      return;
    }

    this.trackingEnabled = false;
    this.detachListeners();
    this.clearTimers();
    this.warningStateSubject.next(false);
    this.countdownSecondsSubject.next(this.warningSeconds);
  }

  resetTimer(shouldSyncAcrossTabs = false): void {
    if (!this.trackingEnabled) {
      return;
    }

    if (shouldSyncAcrossTabs) {
      this.publishStayAliveSync();
    }

    this.clearTimers();
    this.warningStateSubject.next(false);
    this.countdownSecondsSubject.next(this.warningSeconds);

    const warningDelayMs = Math.max(
      (this.timeoutSeconds - this.warningSeconds) * 1000,
      1,
    );

    this.warningTimeoutId = setTimeout(() => {
      this.startWarningPhase();
    }, warningDelayMs);
  }

  getCountdownSeconds(): number {
    return this.countdownSecondsSubject.value;
  }

  ngOnDestroy(): void {
    this.stopTracking();
  }

  private startWarningPhase(): void {
    if (!this.trackingEnabled) {
      return;
    }

    let remainingSeconds = this.warningSeconds;
    this.warningStateSubject.next(true);
    this.countdownSecondsSubject.next(remainingSeconds);

    this.countdownIntervalId = setInterval(() => {
      remainingSeconds -= 1;
      this.countdownSecondsSubject.next(Math.max(remainingSeconds, 0));

      if (remainingSeconds <= 0) {
        this.clearTimers();
        this.warningStateSubject.next(false);
        this.expiredSubject.next();
      }
    }, 1000);
  }

  private onUserActivity = (): void => {
    if (!this.trackingEnabled || this.warningStateSubject.value) {
      return;
    }

    this.resetTimer(false);
  };

  private onStorageEvent = (event: StorageEvent): void => {
    if (!this.trackingEnabled) {
      return;
    }

    if (this.isRemoteLogoutEvent(event)) {
      this.stopTracking();
      this.expiredSubject.next();
      return;
    }

    if (this.isStayAliveSyncEvent(event)) {
      this.resetTimer(false);
    }
  };

  private attachListeners(): void {
    for (const eventName of this.trackedEvents) {
      window.addEventListener(eventName, this.onUserActivity, {
        passive: true,
      });
    }

    window.addEventListener("storage", this.onStorageEvent);
  }

  private detachListeners(): void {
    for (const eventName of this.trackedEvents) {
      window.removeEventListener(eventName, this.onUserActivity);
    }

    window.removeEventListener("storage", this.onStorageEvent);
  }

  private publishStayAliveSync(): void {
    localStorage.setItem(
      this.stayAliveSyncStorageKey,
      `${Date.now()}-${Math.random()}`,
    );
  }

  private isRemoteLogoutEvent(event: StorageEvent): boolean {
    return (
      (event.key === this.authTokenStorageKey ||
        event.key === this.authUserStorageKey) &&
      event.newValue === null &&
      event.oldValue !== null
    );
  }

  private isStayAliveSyncEvent(event: StorageEvent): boolean {
    return event.key === this.stayAliveSyncStorageKey && !!event.newValue;
  }

  private clearTimers(): void {
    if (this.warningTimeoutId) {
      clearTimeout(this.warningTimeoutId);
      this.warningTimeoutId = undefined;
    }

    if (this.countdownIntervalId) {
      clearInterval(this.countdownIntervalId);
      this.countdownIntervalId = undefined;
    }
  }
}
