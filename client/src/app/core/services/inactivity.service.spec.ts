import { fakeAsync, tick } from "@angular/core/testing";
import { InactivityService } from "./inactivity.service";

describe("InactivityService", () => {
  let service: InactivityService;

  beforeEach(() => {
    service = new InactivityService();
  });

  afterEach(() => {
    service.stopTracking();
  });

  it("starts tracking with safe timeout/warning values", fakeAsync(() => {
    const warningStates: boolean[] = [];
    service.warningState$.subscribe((value) => warningStates.push(value));

    service.startTracking(0, 0);

    expect(service.getCountdownSeconds()).toBe(1);
    expect(warningStates[warningStates.length - 1]).toBeFalse();

    tick(999);
    expect(warningStates[warningStates.length - 1]).toBeFalse();

    tick(1);
    expect(warningStates[warningStates.length - 1]).toBeTrue();
  }));

  it("enters warning phase after delay", fakeAsync(() => {
    const warningStates: boolean[] = [];
    service.warningState$.subscribe((value) => warningStates.push(value));

    service.startTracking(5, 2);

    tick(2999);
    expect(warningStates[warningStates.length - 1]).toBeFalse();

    tick(1);
    expect(warningStates[warningStates.length - 1]).toBeTrue();
  }));

  it("emits countdown and expired event", fakeAsync(() => {
    const countdownValues: number[] = [];
    let expiredCount = 0;

    service.countdownSeconds$.subscribe((value) => countdownValues.push(value));
    service.expired$.subscribe(() => {
      expiredCount += 1;
    });

    service.startTracking(3, 2);

    tick(1000);
    tick(1000);
    tick(1000);

    expect(countdownValues).toContain(2);
    expect(countdownValues).toContain(1);
    expect(countdownValues[countdownValues.length - 1]).toBe(0);
    expect(expiredCount).toBe(1);
  }));

  it("stopTracking clears state and active timers", fakeAsync(() => {
    const warningStates: boolean[] = [];
    let expiredCount = 0;

    service.warningState$.subscribe((value) => warningStates.push(value));
    service.expired$.subscribe(() => {
      expiredCount += 1;
    });

    service.startTracking(3, 2);
    tick(1000);

    service.stopTracking();

    expect(warningStates[warningStates.length - 1]).toBeFalse();
    expect(service.getCountdownSeconds()).toBe(2);

    tick(5000);
    expect(expiredCount).toBe(0);
  }));
});
