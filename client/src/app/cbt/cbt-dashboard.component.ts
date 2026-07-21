import { CommonModule } from "@angular/common";
import { Component, DestroyRef, OnInit, inject } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { Router, RouterLink } from "@angular/router";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import { MatChipsModule } from "@angular/material/chips";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { CbtWorksheet } from "../core/models/cbt.model";
import { AppDialogService } from "../core/services/app-dialog.service";
import { CbtService } from "../core/services/cbt.service";

@Component({
  selector: "app-cbt-dashboard",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatChipsModule,
    MatIconModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: "./cbt-dashboard.component.html",
  styleUrl: "./cbt-dashboard.component.css",
})
export class CbtDashboardComponent implements OnInit {
  private readonly cbtService = inject(CbtService);
  private readonly appDialog = inject(AppDialogService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  worksheets: CbtWorksheet[] = [];
  isLoading = true;
  isCreating = false;
  errorMessage = "";

  get drafts(): CbtWorksheet[] {
    return this.worksheets.filter((worksheet) => worksheet.status === "draft");
  }

  get completed(): CbtWorksheet[] {
    return this.worksheets.filter(
      (worksheet) => worksheet.status === "completed",
    );
  }

  get ratedCompleted(): CbtWorksheet[] {
    return this.completed.filter(
      (worksheet) =>
        worksheet.before_peak_intensity !== null &&
        worksheet.after_peak_intensity !== null,
    );
  }

  get lowerPeakRatingCount(): number {
    return this.ratedCompleted.filter(
      (worksheet) =>
        worksheet.after_peak_intensity! < worksheet.before_peak_intensity!,
    ).length;
  }

  get averagePeakRatingChange(): number | null {
    if (!this.ratedCompleted.length) return null;
    const totalChange = this.ratedCompleted.reduce(
      (total, worksheet) =>
        total +
        (worksheet.after_peak_intensity! - worksheet.before_peak_intensity!),
      0,
    );
    const averageChange = totalChange / this.ratedCompleted.length;
    return Math.sign(averageChange) * Math.round(Math.abs(averageChange));
  }

  ngOnInit(): void {
    this.loadWorksheets();
  }

  loadWorksheets(): void {
    this.isLoading = true;
    this.errorMessage = "";
    this.cbtService
      .listWorksheets()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (worksheets) => {
          this.worksheets = worksheets;
          this.isLoading = false;
        },
        error: () => {
          this.errorMessage = "Your thought records could not be loaded.";
          this.isLoading = false;
        },
      });
  }

  startThoughtRecord(): void {
    if (this.isCreating) return;
    this.isCreating = true;
    const now = new Date();
    const recordDate = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
    this.cbtService
      .createWorksheet({ record_date: recordDate })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (worksheet) => {
          this.isCreating = false;
          void this.router.navigate(["/cbt", worksheet.id]);
        },
        error: () => {
          this.isCreating = false;
          this.errorMessage = "A new thought record could not be started.";
        },
      });
  }

  async deleteWorksheet(worksheet: CbtWorksheet): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "Delete this thought record?",
      message: "This reflection will be permanently removed.",
      variant: "danger",
      confirmText: "Delete record",
      cancelText: "Keep record",
    });
    if (!confirmed) return;

    this.cbtService
      .deleteWorksheet(worksheet.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.worksheets = this.worksheets.filter(
            (candidate) => candidate.id !== worksheet.id,
          );
        },
        error: () => {
          void this.appDialog.alert({
            title: "Record not deleted",
            message: "The thought record could not be removed. Try again.",
            variant: "error",
            confirmText: "Close",
          });
        },
      });
  }

  editWorksheet(worksheet: CbtWorksheet): void {
    void this.router.navigate(["/cbt", worksheet.id], {
      queryParams: worksheet.status === "completed" ? { edit: true } : undefined,
    });
  }

  getWorksheetTitle(worksheet: CbtWorksheet): string {
    return worksheet.title || worksheet.situation || "Untitled thought record";
  }

  getProgressLabel(worksheet: CbtWorksheet): string {
    return worksheet.status === "completed"
      ? "Completed"
      : `Step ${worksheet.current_step} of 7`;
  }

  getIntensityLabel(worksheet: CbtWorksheet): string | null {
    if (
      worksheet.before_peak_intensity === null ||
      worksheet.after_peak_intensity === null
    ) {
      return null;
    }
    return `${worksheet.before_peak_intensity}% to ${worksheet.after_peak_intensity}%`;
  }

  getAveragePeakRatingChangeLabel(): string {
    const change = this.averagePeakRatingChange;
    if (change === null) return "Not available";
    if (change === 0) return "No change";
    return `${Math.abs(change)} point${Math.abs(change) === 1 ? "" : "s"} ${
      change < 0 ? "lower" : "higher"
    }`;
  }
}
