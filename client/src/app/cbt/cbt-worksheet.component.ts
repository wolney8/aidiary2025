import { CommonModule } from "@angular/common";
import {
  Component,
  HostListener,
  OnInit,
  inject,
} from "@angular/core";
import { FormsModule } from "@angular/forms";
import { HttpErrorResponse } from "@angular/common/http";
import { MatButtonModule } from "@angular/material/button";
import { MatCardModule } from "@angular/material/card";
import {
  MAT_DATE_FORMATS,
  MAT_DATE_LOCALE,
  MatNativeDateModule,
} from "@angular/material/core";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatIconModule } from "@angular/material/icon";
import { MatInputModule } from "@angular/material/input";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatProgressSpinnerModule } from "@angular/material/progress-spinner";
import { MatStepperModule } from "@angular/material/stepper";
import { MatTooltipModule } from "@angular/material/tooltip";
import { ActivatedRoute, Router } from "@angular/router";
import { firstValueFrom } from "rxjs";
import {
  CbtFeelingRating,
  CbtWorksheet,
  CbtWorksheetPayload,
} from "../core/models/cbt.model";
import { AppDialogService } from "../core/services/app-dialog.service";
import { CbtService } from "../core/services/cbt.service";
import { parseLocalIsoDate } from "../shared/utils/date-display";

const UK_DATE_FORMATS = {
  parse: { dateInput: "dd/MM/yyyy" },
  display: {
    dateInput: "dd/MM/yyyy",
    monthYearLabel: "MMMM yyyy",
    dateA11yLabel: "dd/MM/yyyy",
    monthYearA11yLabel: "MMMM yyyy",
  },
};

@Component({
  selector: "app-cbt-worksheet",
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatNativeDateModule,
    MatProgressBarModule,
    MatProgressSpinnerModule,
    MatStepperModule,
    MatTooltipModule,
  ],
  templateUrl: "./cbt-worksheet.component.html",
  styleUrl: "./cbt-worksheet.component.css",
  providers: [
    { provide: MAT_DATE_LOCALE, useValue: "en-GB" },
    { provide: MAT_DATE_FORMATS, useValue: UK_DATE_FORMATS },
  ],
})
export class CbtWorksheetComponent implements OnInit {
  private readonly cbtService = inject(CbtService);
  private readonly appDialog = inject(AppDialogService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  worksheet?: CbtWorksheet;
  isLoading = true;
  isSaving = false;
  isGeneratingAi = false;
  isEditingCompleted = false;
  errorMessage = "";
  savedMessage = "";
  selectedIndex = 0;
  recordDate: Date | null = null;
  readonly maxDate = new Date();
  aiResponseAwaitingSave = false;
  private savedSnapshot = "";
  private aiResponseSnapshot = "";
  private allowNavigation = false;

  ngOnInit(): void {
    const worksheetId = Number(this.route.snapshot.paramMap.get("id"));
    if (!Number.isInteger(worksheetId) || worksheetId < 1) {
      this.errorMessage = "This thought record could not be found.";
      this.isLoading = false;
      return;
    }

    this.cbtService.getWorksheet(worksheetId).subscribe({
      next: (worksheet) => {
        this.worksheet = worksheet;
        this.recordDate = parseLocalIsoDate(worksheet.record_date);
        this.isEditingCompleted =
          worksheet.status === "completed" &&
          this.route.snapshot.queryParamMap.get("edit") === "true";
        this.selectedIndex = this.isEditingCompleted
          ? 0
          : Math.max(0, Math.min(6, worksheet.current_step - 1));
        this.captureSnapshot();
        this.captureAiResponseSnapshot();
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = "This thought record could not be loaded.";
        this.isLoading = false;
      },
    });
  }

  get isReadOnly(): boolean {
    return (
      this.worksheet?.status === "completed" && !this.isEditingCompleted
    );
  }

  get hasUnsavedChanges(): boolean {
    return !!this.worksheet && this.serialiseDraft() !== this.savedSnapshot;
  }

  get hasChangesToSave(): boolean {
    return this.hasUnsavedChanges || this.aiResponseAwaitingSave;
  }

  get stepForwardLabel(): string {
    return this.worksheet?.status === "draft" ? "Save and continue" : "Next";
  }

  get isBusy(): boolean {
    return this.isSaving || this.isGeneratingAi;
  }

  get isStepForwardDisabled(): boolean {
    return (
      this.isBusy ||
      (this.worksheet?.status === "draft" && !this.hasChangesToSave)
    );
  }

  get aiResponseActionLabel(): string {
    if (this.hasUnsavedChanges) {
      return this.worksheet?.ai_response
        ? "Save and refresh response"
        : "Save and respond with AI";
    }
    return this.worksheet?.ai_response
      ? "Refresh response"
      : "Respond with AI";
  }

  get isAiResponseOutdated(): boolean {
    return !!(
      this.worksheet?.ai_response &&
      (this.worksheet.ai_response_outdated ||
        this.serialiseAnalysisInput() !== this.aiResponseSnapshot)
    );
  }

  addFeeling(target: "before" | "after"): void {
    const collection = this.getFeelings(target);
    if (collection.length >= 8) return;
    collection.push({ label: "", intensity: 50 });
  }

  removeFeeling(target: "before" | "after", index: number): void {
    this.getFeelings(target).splice(index, 1);
  }

  onStepSelected(selectedIndex: number): void {
    this.selectedIndex = selectedIndex;
    if (this.worksheet?.status === "draft") {
      this.worksheet.current_step = selectedIndex + 1;
    }
  }

  async saveDraft(targetStep = this.selectedIndex + 1): Promise<boolean> {
    if (
      !this.worksheet ||
      this.worksheet.status !== "draft" ||
      this.isSaving
    ) {
      return false;
    }
    this.isSaving = true;
    this.errorMessage = "";
    this.savedMessage = "";
    this.worksheet.current_step = targetStep;

    try {
      this.worksheet = await firstValueFrom(
        this.cbtService.updateWorksheet(this.worksheet.id, this.buildPayload()),
      );
      this.selectedIndex = this.worksheet.current_step - 1;
      this.captureSnapshot();
      this.aiResponseAwaitingSave = false;
      this.savedMessage = "Draft saved.";
      return true;
    } catch (error: unknown) {
      this.errorMessage = this.getErrorMessage(
        error,
        "The draft could not be saved. Your changes remain on this page.",
      );
      return false;
    } finally {
      this.isSaving = false;
    }
  }

  async moveStep(direction: -1 | 1): Promise<void> {
    const nextIndex = Math.max(0, Math.min(6, this.selectedIndex + direction));
    if (this.worksheet?.status === "completed") {
      this.selectedIndex = nextIndex;
      return;
    }
    if (await this.saveDraft(nextIndex + 1)) {
      this.selectedIndex = nextIndex;
    }
  }

  async completeWorksheet(): Promise<void> {
    if (!this.worksheet || this.isSaving || this.isReadOnly) return;
    if (!(await this.saveDraft(7))) return;

    this.isSaving = true;
    this.savedMessage = "";
    try {
      this.worksheet = await firstValueFrom(
        this.cbtService.completeWorksheet(this.worksheet.id),
      );
      this.captureSnapshot();
      this.goToThoughtRecords();
    } catch (error: unknown) {
      this.errorMessage = this.getErrorMessage(
        error,
        "Complete each reflection step before finishing.",
      );
    } finally {
      this.isSaving = false;
    }
  }

  async saveAndExit(): Promise<void> {
    if (!this.worksheet || this.isSaving) return;
    if (this.isEditingCompleted) {
      if (await this.saveCompletedRevision()) {
        this.goToThoughtRecords();
      }
      return;
    }
    if (await this.saveDraft()) {
      this.goToThoughtRecords();
    }
  }

  editWorksheet(): void {
    if (!this.worksheet || this.worksheet.status !== "completed") return;
    this.isEditingCompleted = true;
    this.selectedIndex = 0;
    this.savedMessage = "";
  }

  async cancelAndExit(): Promise<void> {
    if (this.hasUnsavedChanges) {
      const confirmed = await this.appDialog.confirm({
        title: "Discard worksheet changes?",
        message: "Changes made since your last save will be lost.",
        variant: "warning",
        confirmText: "Discard changes",
        cancelText: "Keep editing",
      });
      if (!confirmed) return;
    }
    this.allowNavigation = true;
    this.goToThoughtRecords();
  }

  async generateAiResponse(): Promise<void> {
    if (!this.worksheet || this.isBusy) {
      return;
    }
    if (
      this.isEditingCompleted &&
      this.hasUnsavedChanges &&
      !(await this.saveCompletedRevision())
    ) {
      return;
    }
    if (
      this.worksheet.status === "draft" &&
      this.hasUnsavedChanges &&
      !(await this.saveDraft())
    ) {
      return;
    }
    this.isGeneratingAi = true;
    this.errorMessage = "";
    try {
      this.worksheet = await firstValueFrom(
        this.cbtService.analyseWorksheet(this.worksheet.id),
      );
      this.captureSnapshot();
      this.captureAiResponseSnapshot();
      this.aiResponseAwaitingSave = true;
      this.savedMessage = "AI response ready to save.";
    } catch (error: unknown) {
      if (this.isUpgradeRequiredError(error)) {
        await this.showUpgradeRequiredDialog();
        return;
      }
      this.errorMessage = this.getErrorMessage(
        error,
        "The AI response could not be generated.",
      );
    } finally {
      this.isGeneratingAi = false;
    }
  }

  onRecordDateChange(value: Date | null): void {
    this.recordDate = value;
    if (!this.worksheet) return;
    if (!value || Number.isNaN(value.getTime())) {
      this.worksheet.record_date = "";
      return;
    }
    this.worksheet.record_date = [
      value.getFullYear(),
      String(value.getMonth() + 1).padStart(2, "0"),
      String(value.getDate()).padStart(2, "0"),
    ].join("-");
  }

  goBack(): void {
    if (this.route.snapshot.queryParamMap.get("returnTo") === "calendar") {
      const month = Number(this.route.snapshot.queryParamMap.get("month"));
      const year = Number(this.route.snapshot.queryParamMap.get("year"));
      const show = this.route.snapshot.queryParamMap.get("show");
      void this.router.navigate(["/entries"], {
        queryParams: {
          ...(Number.isInteger(month) && month >= 1 && month <= 12
            ? { month }
            : {}),
          ...(Number.isInteger(year) && year > 0 ? { year } : {}),
          ...(show !== null ? { show } : {}),
          display: "calendar",
        },
      });
      return;
    }
    if (this.route.snapshot.queryParamMap.get("returnTo") === "entries") {
      const month = Number(this.route.snapshot.queryParamMap.get("month"));
      const year = Number(this.route.snapshot.queryParamMap.get("year"));
      const type = this.route.snapshot.queryParamMap.get("type");
      const show = this.route.snapshot.queryParamMap.get("show");
      void this.router.navigate(["/entries"], {
        queryParams: {
          display: "cards",
          ...(Number.isInteger(month) && month >= 1 && month <= 12
            ? { month }
            : {}),
          ...(Number.isInteger(year) && year > 0 ? { year } : {}),
          ...(show !== null ? { show } : {}),
          ...(type === "daily" || type === "dreams" ? { type } : {}),
        },
      });
      return;
    }
    const returnEntryId = Number(
      this.route.snapshot.queryParamMap.get("returnEntryId"),
    );
    const returnEntryType = this.route.snapshot.queryParamMap.get(
      "returnEntryType",
    );
    if (
      Number.isInteger(returnEntryId) &&
      returnEntryId > 0 &&
      (returnEntryType === "daily" || returnEntryType === "dream")
    ) {
      void this.router.navigate(["/entries", returnEntryId], {
        queryParams: { entryType: returnEntryType },
      });
      return;
    }
    void this.router.navigate(["/cbt"]);
  }

  private goToThoughtRecords(): void {
    this.allowNavigation = true;
    this.goBack();
  }

  private async showUpgradeRequiredDialog(): Promise<void> {
    const confirmed = await this.appDialog.confirm({
      title: "AI response needs a higher plan",
      message: "Your current plan has reached its AI response allowance for this month.",
      confirmText: "See plans",
      cancelText: "Not now",
      variant: "info",
    });
    if (confirmed) {
      this.allowNavigation = true;
      await this.router.navigate(["/plans"]);
    }
  }

  private isUpgradeRequiredError(error: unknown): boolean {
    return (
      error instanceof HttpErrorResponse &&
      error.status === 402 &&
      error.error?.code === "upgrade_required"
    );
  }

  async canDeactivate(): Promise<boolean> {
    if (this.allowNavigation || !this.hasUnsavedChanges || this.isSaving) {
      return true;
    }
    return this.appDialog.confirm({
      title: "Discard worksheet changes?",
      message: "Changes made since your last save will be lost.",
      variant: "warning",
      confirmText: "Discard changes",
      cancelText: "Keep editing",
    });
  }

  @HostListener("window:beforeunload", ["$event"])
  handleBeforeUnload(event: BeforeUnloadEvent): void {
    if (!this.hasUnsavedChanges) return;
    event.preventDefault();
    event.returnValue = "";
  }

  private getFeelings(target: "before" | "after"): CbtFeelingRating[] {
    if (!this.worksheet) return [];
    return target === "before"
      ? this.worksheet.feelings_before
      : this.worksheet.feelings_after;
  }

  private buildPayload(): CbtWorksheetPayload {
    const worksheet = this.worksheet!;
    return {
      title: worksheet.title,
      current_step: worksheet.current_step,
      record_date: worksheet.record_date,
      situation: worksheet.situation,
      feelings_before: worksheet.feelings_before,
      unhelpful_thoughts: worksheet.unhelpful_thoughts,
      evidence_for: worksheet.evidence_for,
      evidence_against: worksheet.evidence_against,
      balanced_thought: worksheet.balanced_thought,
      feelings_after: worksheet.feelings_after,
      next_step: worksheet.next_step,
    };
  }

  private captureSnapshot(): void {
    this.savedSnapshot = this.serialiseDraft();
  }

  private captureAiResponseSnapshot(): void {
    this.aiResponseSnapshot = this.serialiseAnalysisInput();
  }

  private async saveCompletedRevision(): Promise<boolean> {
    if (!this.worksheet || !this.isEditingCompleted || this.isBusy) {
      return false;
    }
    this.isSaving = true;
    this.errorMessage = "";
    this.savedMessage = "";
    try {
      this.worksheet = await firstValueFrom(
        this.cbtService.reviseWorksheet(
          this.worksheet.id,
          this.buildPayload(),
        ),
      );
      this.captureSnapshot();
      this.aiResponseAwaitingSave = false;
      this.savedMessage = "Changes saved.";
      return true;
    } catch (error: unknown) {
      this.errorMessage = this.getErrorMessage(
        error,
        "The changes could not be saved.",
      );
      return false;
    } finally {
      this.isSaving = false;
    }
  }

  private serialiseDraft(): string {
    return this.worksheet ? JSON.stringify(this.buildPayload()) : "";
  }

  private serialiseAnalysisInput(): string {
    if (!this.worksheet) return "";
    const payload = this.buildPayload();
    const { current_step: _currentStep, ...analysisInput } = payload;
    return JSON.stringify(analysisInput);
  }

  private getErrorMessage(error: unknown, fallback: string): string {
    if (
      typeof error === "object" &&
      error !== null &&
      "error" in error &&
      typeof (error as { error?: { error?: unknown } }).error?.error === "string"
    ) {
      return (error as { error: { error: string } }).error.error;
    }
    return fallback;
  }
}
