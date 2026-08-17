import { DOCUMENT } from "@angular/common";
import { Injectable, computed, inject, signal } from "@angular/core";

export type ThemeMode = "light" | "dark";
export type ThemePreference = "auto" | ThemeMode;
export type ThemePreset = "default" | "ocean" | "forest";

const THEME_PREFERENCES = new Set<ThemePreference>(["auto", "light", "dark"]);
const THEME_PRESETS = new Set<ThemePreset>(["default", "ocean", "forest"]);

@Injectable({
  providedIn: "root",
})
export class ThemeService {
  private readonly document = inject(DOCUMENT);
  private readonly modeStorageKey = "openmynd_theme_mode";
  private readonly legacyModeStorageKey = "ai_diary_theme_mode";
  private readonly presetStorageKey = "openmynd_theme_preset";
  private readonly legacyPresetStorageKey = "ai_diary_theme_preset";
  private storageScope: string | null = null;
  private readonly preferenceSignal = signal<ThemePreference>("auto");
  private readonly resolvedModeSignal = signal<ThemeMode>("light");
  private readonly presetSignal = signal<ThemePreset>("default");
  private readonly systemThemeQuery = this.createSystemThemeQuery();

  readonly preference = computed(() => this.preferenceSignal());
  readonly mode = computed(() => this.resolvedModeSignal());
  readonly preset = computed(() => this.presetSignal());
  readonly isDark = computed(() => this.resolvedModeSignal() === "dark");

  constructor() {
    this.systemThemeQuery?.addEventListener("change", this.handleSystemThemeChange);
    this.applyPreset(this.readStoredPreset(), false);
    this.applyPreference(this.readStoredPreference(), false);
  }

  toggleTheme(): void {
    this.setPreference(this.isDark() ? "light" : "dark");
  }

  setTheme(mode: ThemeMode): void {
    this.setPreference(mode);
  }

  setPreference(preference: ThemePreference): void {
    this.applyPreference(preference, true);
  }

  setPreset(preset: ThemePreset): void {
    this.applyPreset(preset, true);
  }

  setUserScope(scope: string | number | null | undefined): void {
    const nextScope = scope === null || scope === undefined ? null : String(scope);
    if (this.storageScope === nextScope) {
      return;
    }

    this.storageScope = nextScope;
    this.applyPreset(this.readStoredPreset(), false);
    this.applyPreference(this.readStoredPreference(), false);
  }

  private readonly handleSystemThemeChange = (event: MediaQueryListEvent): void => {
    if (this.preferenceSignal() === "auto") {
      this.applyResolvedMode(event.matches ? "dark" : "light");
    }
  };

  private createSystemThemeQuery(): MediaQueryList | null {
    if (typeof window === "undefined" || !("matchMedia" in window)) {
      return null;
    }
    return window.matchMedia("(prefers-color-scheme: dark)");
  }

  private readStoredPreference(): ThemePreference {
    if (typeof localStorage === "undefined") {
      return "auto";
    }

    const storedValue = localStorage.getItem(this.scopedModeStorageKey());
    if (storedValue && THEME_PREFERENCES.has(storedValue as ThemePreference)) {
      return storedValue as ThemePreference;
    }

    if (!this.storageScope) {
      const legacyValue = localStorage.getItem(this.legacyModeStorageKey);
      if (legacyValue && THEME_PREFERENCES.has(legacyValue as ThemePreference)) {
        localStorage.setItem(this.modeStorageKey, legacyValue);
        localStorage.removeItem(this.legacyModeStorageKey);
        return legacyValue as ThemePreference;
      }
    }
    return "auto";
  }

  private readStoredPreset(): ThemePreset {
    if (typeof localStorage === "undefined") {
      return "default";
    }

    const storedValue = localStorage.getItem(this.scopedPresetStorageKey());
    if (storedValue && THEME_PRESETS.has(storedValue as ThemePreset)) {
      return storedValue as ThemePreset;
    }

    if (!this.storageScope) {
      const legacyValue = localStorage.getItem(this.legacyPresetStorageKey);
      if (legacyValue && THEME_PRESETS.has(legacyValue as ThemePreset)) {
        localStorage.setItem(this.presetStorageKey, legacyValue);
        localStorage.removeItem(this.legacyPresetStorageKey);
        return legacyValue as ThemePreset;
      }
    }
    return "default";
  }

  private applyPreference(
    preference: ThemePreference,
    persist: boolean,
  ): void {
    this.preferenceSignal.set(preference);
    const resolvedMode =
      preference === "auto"
        ? this.systemThemeQuery?.matches
          ? "dark"
          : "light"
        : preference;
    this.applyResolvedMode(resolvedMode);

    if (persist && typeof localStorage !== "undefined") {
      localStorage.setItem(this.scopedModeStorageKey(), preference);
      localStorage.removeItem(this.legacyModeStorageKey);
    }
  }

  private applyPreset(preset: ThemePreset, persist: boolean): void {
    this.presetSignal.set(preset);
    this.document?.documentElement.setAttribute("data-theme-preset", preset);

    if (persist && typeof localStorage !== "undefined") {
      localStorage.setItem(this.scopedPresetStorageKey(), preset);
      localStorage.removeItem(this.legacyPresetStorageKey);
    }
  }

  private scopedModeStorageKey(): string {
    return this.storageScope
      ? `${this.modeStorageKey}:${this.storageScope}`
      : this.modeStorageKey;
  }

  private scopedPresetStorageKey(): string {
    return this.storageScope
      ? `${this.presetStorageKey}:${this.storageScope}`
      : this.presetStorageKey;
  }

  private applyResolvedMode(mode: ThemeMode): void {
    this.resolvedModeSignal.set(mode);

    const root = this.document?.documentElement;
    if (root) {
      root.setAttribute("data-theme", mode);
      root.style.colorScheme = mode;
    }
  }
}
