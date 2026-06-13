import { Injectable, inject } from "@angular/core";
import { MatDialog } from "@angular/material/dialog";
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from "../../shared/components/confirm-dialog/confirm-dialog.component";

type DialogOptions = Omit<ConfirmDialogData, "showCancel">;

@Injectable({
  providedIn: "root",
})
export class AppDialogService {
  private readonly dialog = inject(MatDialog);

  confirm(options: DialogOptions): Promise<boolean> {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        ...options,
        showCancel: true,
      },
      disableClose: true,
      autoFocus: false,
      restoreFocus: true,
      width: "30rem",
      maxWidth: "calc(100vw - 2rem)",
    });

    return new Promise<boolean>((resolve) => {
      dialogRef.afterClosed().subscribe((result) => {
        resolve(result === true);
      });
    });
  }

  alert(options: DialogOptions): Promise<void> {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        ...options,
        showCancel: false,
      },
      disableClose: true,
      autoFocus: false,
      restoreFocus: true,
      width: "30rem",
      maxWidth: "calc(100vw - 2rem)",
    });

    return new Promise<void>((resolve) => {
      dialogRef.afterClosed().subscribe(() => {
        resolve();
      });
    });
  }
}
