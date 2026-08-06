import { TestBed } from "@angular/core/testing";
import { ThemeService } from "./theme.service";

describe("ThemeService", () => {
  let matchesDark = false;
  let changeListener: ((event: MediaQueryListEvent) => void) | undefined;

  beforeEach(() => {
    localStorage.removeItem("openmynd_theme_mode");
    localStorage.removeItem("openmynd_theme_preset");
    localStorage.removeItem("ai_diary_theme_mode");
    localStorage.removeItem("ai_diary_theme_preset");
    document.documentElement.removeAttribute("data-theme");
    document.documentElement.removeAttribute("data-theme-preset");

    const mediaQuery = {
      get matches() {
        return matchesDark;
      },
      media: "(prefers-color-scheme: dark)",
      onchange: null,
      addEventListener: jasmine
        .createSpy("addEventListener")
        .and.callFake(
          (_eventName: string, listener: (event: MediaQueryListEvent) => void) => {
            changeListener = listener;
          },
        ),
      removeEventListener: jasmine.createSpy("removeEventListener"),
      addListener: jasmine.createSpy("addListener"),
      removeListener: jasmine.createSpy("removeListener"),
      dispatchEvent: jasmine.createSpy("dispatchEvent"),
    } as unknown as MediaQueryList;

    spyOn(window, "matchMedia").and.returnValue(mediaQuery);
    matchesDark = false;
    changeListener = undefined;
    TestBed.configureTestingModule({});
  });

  afterEach(() => {
    localStorage.removeItem("openmynd_theme_mode");
    localStorage.removeItem("openmynd_theme_preset");
    localStorage.removeItem("ai_diary_theme_mode");
    localStorage.removeItem("ai_diary_theme_preset");
  });

  it("uses auto mode by default and follows system theme changes", () => {
    const service = TestBed.inject(ThemeService);

    expect(service.preference()).toBe("auto");
    expect(service.mode()).toBe("light");

    changeListener?.({ matches: true } as MediaQueryListEvent);

    expect(service.mode()).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("persists explicit mode and preset choices", () => {
    const service = TestBed.inject(ThemeService);

    service.setPreference("dark");
    service.setPreset("forest");

    expect(service.preference()).toBe("dark");
    expect(service.preset()).toBe("forest");
    expect(localStorage.getItem("openmynd_theme_mode")).toBe("dark");
    expect(localStorage.getItem("openmynd_theme_preset")).toBe("forest");
    expect(document.documentElement.getAttribute("data-theme-preset")).toBe(
      "forest",
    );
  });

  it("restores valid stored choices", () => {
    localStorage.setItem("openmynd_theme_mode", "dark");
    localStorage.setItem("openmynd_theme_preset", "ocean");

    const service = TestBed.inject(ThemeService);

    expect(service.preference()).toBe("dark");
    expect(service.mode()).toBe("dark");
    expect(service.preset()).toBe("ocean");
  });
});
