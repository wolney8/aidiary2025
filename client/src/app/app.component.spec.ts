import { ComponentFixture, TestBed } from "@angular/core/testing";
import { BehaviorSubject, Subject } from "rxjs";
import { MatDialog, MatDialogRef } from "@angular/material/dialog";
import { AppComponent } from "./app.component";
import { AuthService } from "./core/services/auth.service";
import { InactivityService } from "./core/services/inactivity.service";
import {
  InactivityWarningComponent,
  InactivityWarningResult,
} from "./shared/components/inactivity-warning/inactivity-warning.component";
import { User } from "./core/models/user.model";

describe("AppComponent inactivity integration", () => {
  let fixture: ComponentFixture<AppComponent>;
  let warningStateSubject: Subject<boolean>;
  let countdownSubject: Subject<number>;
  let expiredSubject: Subject<void>;
  let currentUserSubject: BehaviorSubject<User | null>;
  let authServiceMock: {
    currentUser$: Subject<User | null>;
    isAuthenticated: any;
    logout: any;
  };
  let inactivityServiceMock: {
    warningState$: Subject<boolean>;
    countdownSeconds$: Subject<number>;
    expired$: Subject<void>;
    startTracking: any;
    stopTracking: any;
    resetTimer: any;
    getCountdownSeconds: any;
  };
  let dialogMock: {
    open: any;
  };

  beforeEach(async () => {
    warningStateSubject = new Subject<boolean>();
    countdownSubject = new Subject<number>();
    expiredSubject = new Subject<void>();
    currentUserSubject = new BehaviorSubject<User | null>(null);

    authServiceMock = {
      currentUser$: currentUserSubject,
      isAuthenticated: jasmine
        .createSpy("isAuthenticated")
        .and.returnValue(false),
      logout: jasmine.createSpy("logout"),
    };

    inactivityServiceMock = {
      warningState$: warningStateSubject,
      countdownSeconds$: countdownSubject,
      expired$: expiredSubject,
      startTracking: jasmine.createSpy("startTracking"),
      stopTracking: jasmine.createSpy("stopTracking"),
      resetTimer: jasmine.createSpy("resetTimer"),
      getCountdownSeconds: jasmine
        .createSpy("getCountdownSeconds")
        .and.returnValue(60),
    };

    dialogMock = {
      open: jasmine.createSpy("open"),
    };

    TestBed.overrideComponent(AppComponent, {
      set: {
        template: "",
        imports: [],
      },
    });

    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        { provide: AuthService, useValue: authServiceMock },
        { provide: InactivityService, useValue: inactivityServiceMock },
        { provide: MatDialog, useValue: dialogMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
  });

  it("opens one warning dialog when warningState is true", () => {
    const closeResult$ = new Subject<InactivityWarningResult | undefined>();
    const dialogRef = {
      componentInstance: { countdownSeconds: 0 },
      afterClosed: () => closeResult$.asObservable(),
      close: jasmine.createSpy("close"),
    } as unknown as MatDialogRef<
      InactivityWarningComponent,
      InactivityWarningResult
    >;

    dialogMock.open.and.returnValue(dialogRef);

    warningStateSubject.next(true);
    warningStateSubject.next(true);

    expect(dialogMock.open).toHaveBeenCalledTimes(1);
  });

  it("sets isAuthenticated false when user is null", () => {
    authServiceMock.isAuthenticated.and.returnValue(true);

    currentUserSubject.next(null);

    expect(fixture.componentInstance.isAuthenticated).toBeFalse();
  });

  it("sets isAuthenticated true when user exists and isAuthenticated() true", () => {
    const user: User = { id: 1, username: "tester" };
    authServiceMock.isAuthenticated.and.returnValue(true);

    currentUserSubject.next(user);

    expect(fixture.componentInstance.isAuthenticated).toBeTrue();
  });

  it("does not set true when user exists but isAuthenticated() false", () => {
    const user: User = { id: 1, username: "tester" };
    authServiceMock.isAuthenticated.and.returnValue(false);

    currentUserSubject.next(user);

    expect(fixture.componentInstance.isAuthenticated).toBeFalse();
  });

  it("stay action resets timer", () => {
    const closeResult$ = new Subject<InactivityWarningResult | undefined>();
    const dialogRef = {
      componentInstance: { countdownSeconds: 0 },
      afterClosed: () => closeResult$.asObservable(),
      close: jasmine.createSpy("close"),
    } as unknown as MatDialogRef<
      InactivityWarningComponent,
      InactivityWarningResult
    >;

    dialogMock.open.and.returnValue(dialogRef);

    warningStateSubject.next(true);
    closeResult$.next("stay");

    expect(inactivityServiceMock.resetTimer).toHaveBeenCalledWith(true);
  });

  it("logout action calls AuthService.logout", () => {
    const closeResult$ = new Subject<InactivityWarningResult | undefined>();
    const dialogRef = {
      componentInstance: { countdownSeconds: 0 },
      afterClosed: () => closeResult$.asObservable(),
      close: jasmine.createSpy("close"),
    } as unknown as MatDialogRef<
      InactivityWarningComponent,
      InactivityWarningResult
    >;

    dialogMock.open.and.returnValue(dialogRef);

    warningStateSubject.next(true);
    closeResult$.next("logout");

    expect(authServiceMock.logout).toHaveBeenCalled();
  });
});
