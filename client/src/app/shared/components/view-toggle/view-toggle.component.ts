// Pill toggle for All/Daily/Dreams
import { Component, Output, EventEmitter, Input } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-view-toggle",
  standalone: true,
  imports: [CommonModule, MatButtonToggleModule, MatIconModule],
  template: `
    <mat-button-toggle-group
      class="view-toggle"
      [class.emphasise-daily]="emphasiseActiveFilter && selectedView === 'daily'"
      [class.emphasise-dreams]="emphasiseActiveFilter && selectedView === 'dreams'"
      [value]="selectedView"
      (change)="onViewChange($event.value)"
      aria-label="Filter entry type"
      [hideSingleSelectionIndicator]="true"
    >
      <mat-button-toggle value="all">
        <mat-icon>apps</mat-icon>
        ALL ENTRIES
      </mat-button-toggle>
      <mat-button-toggle value="daily">
        <mat-icon>book</mat-icon>
        DAILY
      </mat-button-toggle>
      <mat-button-toggle value="dreams">
        <mat-icon>nights_stay</mat-icon>
        DREAMS
      </mat-button-toggle>
    </mat-button-toggle-group>
  `,
  styles: [
    `
      .view-toggle {
        margin: var(--spacing-md) 0;
      }

      .view-toggle .mat-button-toggle {
        border-color: var(--colour-border);
        color: var(--colour-text-secondary);
        transition: all 0.2s ease;
      }

      .view-toggle .mat-button-toggle:hover {
        background: var(--colour-surface-muted);
      }

      .view-toggle .mat-button-toggle-checked {
        background: var(--colour-primary);
        color: #ffffff;
      }

      .view-toggle .mat-button-toggle-checked:hover {
        background: var(--colour-primary-hover);
      }

      .view-toggle.emphasise-daily .mat-button-toggle-checked {
        background: linear-gradient(180deg, #1d4ed8 0%, #2563eb 100%);
        box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.45);
        animation: activeFilterPulseBlue 2.2s ease-in-out infinite;
      }

      .view-toggle.emphasise-dreams .mat-button-toggle-checked {
        background: linear-gradient(180deg, #6d28d9 0%, #7c3aed 100%);
        box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.4);
        animation: activeFilterPulsePurple 2.2s ease-in-out infinite;
      }

      .view-toggle .mat-button-toggle .mat-icon {
        margin-right: var(--spacing-xs);
      }

      @keyframes activeFilterPulseBlue {
        0%,
        100% {
          box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.16);
          transform: translateY(0);
        }
        50% {
          box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.08);
          transform: translateY(-1px);
        }
      }

      @keyframes activeFilterPulsePurple {
        0%,
        100% {
          box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.15);
          transform: translateY(0);
        }
        50% {
          box-shadow: 0 0 0 6px rgba(124, 58, 237, 0.08);
          transform: translateY(-1px);
        }
      }
    `,
  ],
})
export class ViewToggleComponent {
  @Input() set value(view: string) {
    if (view === "all" || view === "daily" || view === "dreams") {
      this.selectedView = view;
    }
  }
  @Input() emphasiseActiveFilter = false;
  @Output() viewChange = new EventEmitter<string>();
  selectedView = "all";

  onViewChange(view: string): void {
    this.selectedView = view;
    this.viewChange.emit(view);
  }
}
