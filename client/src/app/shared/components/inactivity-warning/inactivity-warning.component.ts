import { CommonModule } from "@angular/common";
import { Component, Inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";

export type InactivityWarningResult = "stay" | "logout";

@Component({
  selector: "app-inactivity-warning",
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Still there?</h2>
    <mat-dialog-content>
      <p>Your session is about to expire due to inactivity.</p>
      <p>
        You will be logged out in
        <strong>{{ countdownSeconds }}</strong>
        seconds.
      </p>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button type="button" (click)="logout()">
        Log out
      </button>
      <button mat-flat-button color="primary" type="button" (click)="stay()">
        Stay logged in
      </button>
    </mat-dialog-actions>
  `,
})
export class InactivityWarningComponent {
  countdownSeconds = 0;

  constructor(
    private dialogRef: MatDialogRef<
      InactivityWarningComponent,
      InactivityWarningResult
    >,
    @Inject(MAT_DIALOG_DATA)
    data: { countdownSeconds?: number } | null,
  ) {
    this.countdownSeconds = data?.countdownSeconds ?? 0;
  }

  stay(): void {
    this.dialogRef.close("stay");
  }

  logout(): void {
    this.dialogRef.close("logout");
  }
}
