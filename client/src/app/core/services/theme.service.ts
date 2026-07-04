import { DOCUMENT } from "@angular/common";
import { Injectable, computed, inject, signal } from "@angular/core";

export type ThemeMode = "light" | "dark";

@Injectable({
  providedIn: "root",
})
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly storageKey = "ai_diary_theme_mode";
  private readonly modeSignal = signal<ThemeMode>("light");

  readonly mode = computed(() => this.modeSignal());
  readonly isDark = computed(() => this.modeSignal() === "dark");

  constructor() {
    const initialMode = this.resolveInitialMode();
    this.applyTheme(initialMode);
  }

  toggleTheme(): void {
    this.applyTheme(this.modeSignal() === "dark" ? "light" : "dark");
  }

  setTheme(mode: ThemeMode): void {
    this.applyTheme(mode);
  }

  private resolveInitialMode(): ThemeMode {
    const storedMode = this.readStoredMode();
    if (storedMode) {
      return storedMode;
    }

    if (typeof window !== "undefined" && "matchMedia" in window) {
      return window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light";
    }

    return "light";
  }

  private readStoredMode(): ThemeMode | null {
    if (typeof localStorage === "undefined") {
      return null;
    }

    const storedValue = localStorage.getItem(this.storageKey);
    return storedValue === "dark" || storedValue === "light"
      ? storedValue
      : null;
  }

  private applyTheme(mode: ThemeMode): void {
    this.modeSignal.set(mode);

    const root = this.document?.documentElement;
    if (root) {
      root.setAttribute("data-theme", mode);
      root.style.colorScheme = mode;
    }

    if (typeof localStorage !== "undefined") {
      localStorage.setItem(this.storageKey, mode);
    }
  }
}
