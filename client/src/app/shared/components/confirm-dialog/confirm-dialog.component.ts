import { Component, computed, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

export type ConfirmDialogVariant = "warning" | "danger" | "error" | "info";

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  showCancel?: boolean;
  variant?: ConfirmDialogVariant;
}

@Component({
  selector: "app-confirm-dialog",
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <div class="confirm-dialog" [class.is-destructive]="isDestructive()">
      <div class="dialog-header">
        <div
          class="dialog-icon"
          [class.warning]="variant() === 'warning'"
          [class.danger]="variant() === 'danger'"
          [class.error]="variant() === 'error'"
          [class.info]="variant() === 'info'"
          aria-hidden="true"
        >
          <mat-icon>{{ iconName() }}</mat-icon>
        </div>
        <div class="dialog-copy">
          <h2 mat-dialog-title>{{ data.title }}</h2>
          <p class="dialog-message">{{ data.message }}</p>
        </div>
      </div>

      <mat-dialog-actions align="end">
        <button
          *ngIf="showCancel()"
          mat-stroked-button
          type="button"
          class="cancel-button"
          (click)="close(false)"
        >
          {{ data.cancelText || "Cancel" }}
        </button>
        <button
          mat-flat-button
          type="button"
          [class.destructive-button]="isDestructive()"
          [class.info-button]="!isDestructive()"
          (click)="close(true)"
        >
          {{ confirmLabel() }}
        </button>
      </mat-dialog-actions>
    </div>
  `,
  styles: [
    `
      .confirm-dialog {
        width: min(30rem, 100%);
        color: var(--colour-text-primary, #1f1f1f);
      }

      .dialog-header {
        display: flex;
        align-items: flex-start;
        gap: 1rem;
        padding: 1.35rem 1.35rem 0.35rem;
      }

      .dialog-icon {
        width: 2.6rem;
        height: 2.6rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .dialog-icon mat-icon {
        width: 1.35rem;
        height: 1.35rem;
        font-size: 1.35rem;
      }

      .dialog-icon.warning {
        background: rgba(194, 102, 26, 0.12);
        color: #a35518;
      }

      .dialog-icon.danger,
      .dialog-icon.error {
        background: rgba(179, 38, 30, 0.12);
        color: #b3261e;
      }

      .dialog-icon.info {
        background: rgba(25, 118, 210, 0.12);
        color: #1565c0;
      }

      .dialog-copy {
        min-width: 0;
      }

      h2[mat-dialog-title] {
        margin: 0;
        font-size: 1.05rem;
        line-height: 1.3;
      }

      .dialog-message {
        margin: 0.45rem 0 0;
        color: var(--colour-text-secondary, #5f6368);
        line-height: 1.5;
        white-space: pre-line;
      }

      mat-dialog-actions {
        padding: 1rem 1.35rem 1.35rem;
        gap: 0.75rem;
      }

      .cancel-button {
        border-color: var(--colour-border, #d7dbe2);
        color: var(--colour-text-secondary, #5f6368);
      }

      .destructive-button {
        background: #b3261e;
        color: #fff;
      }

      .destructive-button:hover {
        background: #8f2019;
      }

      .info-button {
        background: var(--colour-primary, #6750a4);
        color: #fff;
      }
    `,
  ],
})
export class ConfirmDialogComponent {
  readonly data = inject<ConfirmDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(
    MatDialogRef<ConfirmDialogComponent, boolean>,
  );

  readonly variant = computed<ConfirmDialogVariant>(
    () => this.data.variant || "warning",
  );
  readonly showCancel = computed<boolean>(() => this.data.showCancel !== false);
  readonly isDestructive = computed<boolean>(
    () => this.variant() === "danger" || this.variant() === "error",
  );
  readonly iconName = computed(() => {
    switch (this.variant()) {
      case "danger":
        return "delete_forever";
      case "error":
        return "error";
      case "info":
        return "info";
      default:
        return "warning";
    }
  });
  readonly confirmLabel = computed(() => {
    if (this.data.confirmText?.trim()) {
      return this.data.confirmText.trim();
    }
    return this.showCancel() ? "Confirm" : "OK";
  });

  close(result: boolean): void {
    this.dialogRef.close(result);
  }
}
