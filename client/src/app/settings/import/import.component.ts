import { Component, OnInit } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatCardModule } from "@angular/material/card";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { MatSnackBarModule, MatSnackBar } from "@angular/material/snack-bar";
import { MatTabsModule } from "@angular/material/tabs";
import { MatDividerModule } from "@angular/material/divider";
import {
  ImportService,
  ImportTemplate,
  ImportResult,
} from "../../services/import.service";

@Component({
  selector: "app-import",
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatSnackBarModule,
    MatTabsModule,
    MatDividerModule,
  ],
  templateUrl: "./import.component.html",
  styleUrls: ["./import.component.scss"],
})
export class ImportComponent implements OnInit {
  selectedFile: File | null = null;
  isUploading = false;
  uploadProgress = 0;
  dailyTemplate: ImportTemplate | null = null;
  dreamTemplate: ImportTemplate | null = null;
  selectedEntryType: "daily" | "dream" = "daily";
  selectedTabIndex = 0;
  importHistory: any[] = [];

  constructor(
    private importService: ImportService,
    private snackBar: MatSnackBar,
  ) {}

  ngOnInit(): void {
    this.loadTemplates();
    this.loadImportHistory();
  }

  loadTemplates(): void {
    // Load both templates for download options
    this.importService.getImportTemplate("daily").subscribe({
      next: (template) => {
        console.log("Loaded daily template:", template);
        this.dailyTemplate = template;
      },
      error: (error) => {
        console.error("Failed to load daily template:", error);
      },
    });

    this.importService.getImportTemplate("dream").subscribe({
      next: (template) => {
        console.log("Loaded dream template:", template);
        this.dreamTemplate = template;
      },
      error: (error) => {
        console.error("Failed to load dream template:", error);
      },
    });
  }

  loadImportHistory(): void {
    this.importService.getImportHistory().subscribe({
      next: (history) => (this.importHistory = history),
      error: (error) => console.error("Failed to load import history:", error),
    });
  }

  onTabChange(index: number): void {
    this.selectedTabIndex = index;
    this.selectedEntryType = index === 0 ? "daily" : "dream";
  }

  onFileSelected(event: any): void {
    const file = event.target.files[0];
    if (file) {
      this.selectedFile = file;
      this.validateFile(file);
    }
  }

  validateFile(file: File): void {
    this.importService
      .validateImportFile(file, this.selectedEntryType)
      .subscribe({
        next: (result) => {
          if (!result.valid) {
            this.snackBar.open(result.message, "Close", {
              duration: 5000,
              panelClass: ["error-snackbar"],
            });
            this.selectedFile = null;
          }
        },
        error: (error) => {
          this.snackBar.open(`Validation error: ${error}`, "Close", {
            duration: 5000,
            panelClass: ["error-snackbar"],
          });
          this.selectedFile = null;
        },
      });
  }

  uploadFile(): void {
    if (!this.selectedFile) {
      this.snackBar.open("Please select a file first", "Close", {
        duration: 3000,
      });
      return;
    }

    this.isUploading = true;
    this.uploadProgress = 0;

    // Simulate progress for user feedback
    const progressInterval = setInterval(() => {
      this.uploadProgress += 10;
      if (this.uploadProgress >= 90) {
        clearInterval(progressInterval);
      }
    }, 200);

    this.importService
      .uploadImportFile(this.selectedFile, this.selectedEntryType)
      .subscribe({
        next: (result: ImportResult) => {
          clearInterval(progressInterval);
          this.uploadProgress = 100;
          this.isUploading = false;

          if (result.success) {
            this.snackBar.open(
              `Successfully imported ${result.entries_imported} entries`,
              "Close",
              { duration: 5000, panelClass: ["success-snackbar"] },
            );
          } else {
            this.snackBar.open(
              `Import completed with errors: ${result.errors.join(", ")}`,
              "Close",
              { duration: 7000, panelClass: ["warning-snackbar"] },
            );
          }

          // Reset form
          this.selectedFile = null;
          this.uploadProgress = 0;
          this.loadImportHistory(); // Refresh history after successful import
        },
        error: (error) => {
          clearInterval(progressInterval);
          this.isUploading = false;
          this.uploadProgress = 0;

          this.snackBar.open(`Import failed: ${error}`, "Close", {
            duration: 5000,
            panelClass: ["error-snackbar"],
          });
        },
      });
  }

  downloadTemplate(type: "daily" | "dream"): void {
    const template = type === "daily" ? this.dailyTemplate : this.dreamTemplate;
    if (!template) {
      this.snackBar.open("Template not available", "Close", { duration: 3000 });
      return;
    }

    // Create CSV content
    const csvContent = this.createCsvContent(template);

    // Create and download file
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${type}_entries_template.csv`;
    link.click();
    window.URL.revokeObjectURL(url);
  }

  private createCsvContent(template: ImportTemplate): string {
    const rows = [template.headers, ...template.example_data];
    return rows
      .map((row) =>
        row.map((cell) => `"${cell.toString().replace(/"/g, '""')}"`).join(","),
      )
      .join("\n");
  }

  clearSelection(): void {
    this.selectedFile = null;
    this.uploadProgress = 0;
  }

  formatImportDate(dateString: string): string {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }
}
