import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatCardModule } from "@angular/material/card";
import { MatIconModule } from "@angular/material/icon";
import { MatRadioModule } from "@angular/material/radio";
import {
  ThemePreference,
  ThemePreset,
  ThemeService,
} from "../../core/services/theme.service";

interface ThemePreferenceOption {
  value: ThemePreference;
  label: string;
  icon: string;
}

interface ThemePresetOption {
  value: ThemePreset;
  label: string;
  description: string;
}

@Component({
  selector: "app-appearance",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonToggleModule,
    MatCardModule,
    MatIconModule,
    MatRadioModule,
  ],
  template: `
    <section
      class="appearance-settings"
      data-testid="appearance-settings"
      aria-labelledby="appearance-settings-heading"
    >
      <header class="appearance-header">
        <h2 id="appearance-settings-heading">Appearance</h2>
        <p>Choose the display mode and colour theme.</p>
      </header>

      <mat-card class="appearance-card">
        <mat-card-header>
          <mat-card-title>Display mode</mat-card-title>
          <mat-card-subtitle>
            Auto follows your device setting.
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <mat-button-toggle-group
            class="appearance-mode-toggle"
            [value]="preference()"
            (change)="setPreference($event.value)"
            aria-label="Display mode"
            data-testid="appearance-mode-toggle"
          >
            <mat-button-toggle
              *ngFor="let option of preferenceOptions"
              [value]="option.value"
              [attr.data-testid]="'appearance-mode-' + option.value"
            >
              <mat-icon aria-hidden="true">{{ option.icon }}</mat-icon>
              <span>{{ option.label }}</span>
            </mat-button-toggle>
          </mat-button-toggle-group>
        </mat-card-content>
      </mat-card>

      <mat-card class="appearance-card">
        <mat-card-header>
          <mat-card-title>Colour theme</mat-card-title>
          <mat-card-subtitle>
            Changes apply immediately and stay on this device.
          </mat-card-subtitle>
        </mat-card-header>
        <mat-card-content>
          <mat-radio-group
            class="appearance-preset-grid"
            [ngModel]="preset()"
            (ngModelChange)="setPreset($event)"
            aria-label="Colour theme"
            data-testid="appearance-preset-options"
          >
            <mat-radio-button
              *ngFor="let option of presetOptions"
              class="appearance-preset-option"
              [class.is-selected]="preset() === option.value"
              [value]="option.value"
              [attr.data-testid]="'appearance-preset-' + option.value"
            >
              <span class="appearance-preset-copy">
                <span
                  class="appearance-preset-swatches"
                  [class]="'appearance-preset-swatches preset-' + option.value"
                  aria-hidden="true"
                >
                  <span></span><span></span><span></span>
                </span>
                <strong>{{ option.label }}</strong>
                <span>{{ option.description }}</span>
              </span>
            </mat-radio-button>
          </mat-radio-group>
        </mat-card-content>
      </mat-card>

      <section
        class="appearance-preview"
        aria-labelledby="appearance-preview-heading"
        data-testid="appearance-preview"
      >
        <div class="appearance-preview-heading">
          <div>
            <h3 id="appearance-preview-heading">Preview</h3>
            <p aria-live="polite">{{ getCurrentThemeSummary() }}</p>
          </div>
          <span class="appearance-preview-chip">Selected</span>
        </div>
        <div class="appearance-preview-surface">
          <span class="appearance-preview-icon">
            <mat-icon aria-hidden="true">auto_stories</mat-icon>
          </span>
          <div>
            <strong>A moment worth remembering</strong>
            <p>Your theme keeps text and controls clear in either mode.</p>
          </div>
          <span class="appearance-preview-action">View entry</span>
        </div>
      </section>
    </section>
  `,
  styles: [
    `
      .appearance-settings {
        display: grid;
        gap: var(--spacing-md);
      }

      .appearance-header h2,
      .appearance-preview h3,
      .appearance-preview p,
      .appearance-preview-surface p {
        margin: 0;
      }

      .appearance-header h2 {
        margin-bottom: var(--spacing-xs);
      }

      .appearance-header p,
      .appearance-preview p,
      .appearance-preview-surface p {
        color: var(--colour-text-secondary);
      }

      .appearance-card,
      .appearance-preview {
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-lg);
        background: var(--colour-surface);
      }

      .appearance-card mat-card-content {
        padding-top: var(--spacing-sm);
      }

      .appearance-mode-toggle {
        display: inline-flex;
        max-width: 100%;
        border-radius: var(--radius-pill);
        overflow: hidden;
      }

      .appearance-mode-toggle mat-button-toggle {
        min-width: 7rem;
      }

      .appearance-mode-toggle mat-icon {
        margin-right: var(--spacing-xs);
        vertical-align: middle;
      }

      .appearance-mode-toggle .mat-button-toggle-checked {
        background: var(--colour-control-selected);
        color: var(--colour-control-selected-text);
      }

      .appearance-mode-toggle mat-button-toggle:focus-within {
        outline: var(--focus-outline);
        outline-offset: -2px;
      }

      .appearance-preset-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: var(--spacing-sm);
      }

      .appearance-preset-option {
        min-width: 0;
        padding: var(--spacing-sm);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .appearance-preset-option.is-selected {
        border-color: var(--colour-primary);
        box-shadow: inset 0 0 0 1px var(--colour-primary);
      }

      .appearance-preset-copy {
        display: grid;
        min-width: 0;
        gap: 0.35rem;
        padding: var(--spacing-xs) 0;
        white-space: normal;
      }

      .appearance-preset-copy > span:last-child {
        color: var(--colour-text-secondary);
        font-size: 0.9rem;
      }

      .appearance-preset-swatches {
        display: flex;
        gap: 0.35rem;
        margin-bottom: 0.2rem;
      }

      .appearance-preset-swatches span {
        width: 1.5rem;
        height: 1.5rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
      }

      .preset-default span:nth-child(1) { background: #5b21b6; }
      .preset-default span:nth-child(2) { background: #1d4ed8; }
      .preset-default span:nth-child(3) { background: #0ea5e9; }
      .preset-ocean span:nth-child(1) { background: #075985; }
      .preset-ocean span:nth-child(2) { background: #0369a1; }
      .preset-ocean span:nth-child(3) { background: #0891b2; }
      .preset-forest span:nth-child(1) { background: #14532d; }
      .preset-forest span:nth-child(2) { background: #166534; }
      .preset-forest span:nth-child(3) { background: #0f766e; }

      .appearance-preview {
        padding: var(--spacing-md);
      }

      .appearance-preview-heading,
      .appearance-preview-surface {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .appearance-preview-heading {
        justify-content: space-between;
        margin-bottom: var(--spacing-sm);
      }

      .appearance-preview-chip,
      .appearance-preview-action {
        flex: 0 0 auto;
        padding: 0.35rem 0.75rem;
        border-radius: var(--radius-pill);
        font-weight: 700;
      }

      .appearance-preview-chip {
        background: var(--colour-chip-bg);
        color: var(--colour-chip-text);
      }

      .appearance-preview-surface {
        padding: var(--spacing-sm);
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-md);
        background: var(--colour-surface-muted);
      }

      .appearance-preview-surface > div {
        min-width: 0;
        flex: 1;
      }

      .appearance-preview-icon {
        display: grid;
        width: 2.75rem;
        height: 2.75rem;
        flex: 0 0 2.75rem;
        place-items: center;
        border-radius: var(--radius-pill);
        background: var(--colour-info-bg);
        color: var(--colour-info-text);
      }

      .appearance-preview-action {
        background: var(--colour-primary);
        color: var(--colour-on-primary);
      }

      @media (max-width: 760px) {
        .appearance-preset-grid {
          grid-template-columns: 1fr;
        }

        .appearance-mode-toggle {
          display: flex;
          width: 100%;
        }

        .appearance-mode-toggle mat-button-toggle {
          min-width: 0;
          flex: 1;
        }

        .appearance-preview-surface {
          align-items: flex-start;
          flex-wrap: wrap;
        }

        .appearance-preview-action {
          margin-left: 3.75rem;
        }
      }
    `,
  ],
})
export class AppearanceComponent {
  private readonly themeService = inject(ThemeService);

  readonly preference = this.themeService.preference;
  readonly mode = this.themeService.mode;
  readonly preset = this.themeService.preset;
  readonly preferenceOptions: ThemePreferenceOption[] = [
    { value: "auto", label: "Auto", icon: "brightness_auto" },
    { value: "light", label: "Light", icon: "light_mode" },
    { value: "dark", label: "Dark", icon: "dark_mode" },
  ];
  readonly presetOptions: ThemePresetOption[] = [
    {
      value: "default",
      label: "Default",
      description: "Violet, blue, and sky accents.",
    },
    {
      value: "ocean",
      label: "Ocean",
      description: "Deep blue with teal accents.",
    },
    {
      value: "forest",
      label: "Forest",
      description: "Grounded green and teal accents.",
    },
  ];

  setPreference(preference: ThemePreference): void {
    this.themeService.setPreference(preference);
  }

  setPreset(preset: ThemePreset): void {
    this.themeService.setPreset(preset);
  }

  getCurrentThemeSummary(): string {
    const preset = this.presetOptions.find(
      (option) => option.value === this.preset(),
    );
    const mode = this.preference() === "auto"
      ? `Auto (${this.mode()})`
      : this.mode() === "dark"
        ? "Dark"
        : "Light";
    return `${preset?.label || "Default"} · ${mode}`;
  }
}
