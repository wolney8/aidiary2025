import { CommonModule } from "@angular/common";
import { Component, inject } from "@angular/core";
import { DomSanitizer, SafeResourceUrl } from "@angular/platform-browser";
import { RouterLink } from "@angular/router";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { ProfileMediaAsset } from "../core/services/profile.service";

export interface MediaPreviewDialogData {
  asset: ProfileMediaAsset;
}

@Component({
  selector: "app-media-preview-dialog",
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatDialogModule,
    MatIconModule,
  ],
  template: `
    <section class="media-preview-dialog" data-testid="account-media-preview-dialog">
      <header class="media-preview-header">
        <div>
          <span class="section-eyebrow">{{ mediaTypeLabel }}</span>
          <h2 mat-dialog-title>{{ asset.filename }}</h2>
          <p>{{ entryTypeLabel }} · {{ asset.entry_title }} · {{ formatBytes(asset.file_size_bytes) }}</p>
        </div>
        <button mat-icon-button type="button" (click)="close()" aria-label="Close media preview">
          <mat-icon aria-hidden="true">close</mat-icon>
        </button>
      </header>

      <mat-dialog-content class="media-preview-body">
        <img *ngIf="isImage && asset.url" [src]="asset.url" [alt]="asset.filename" />
        <iframe *ngIf="isPdf && asset.url" [src]="safeUrl" [title]="'PDF preview for ' + asset.filename"></iframe>
        <audio *ngIf="isAudio && asset.url" controls preload="metadata" [attr.aria-label]="'Audio preview for ' + asset.filename">
          <source [src]="asset.url" [type]="asset.mime_type" />
        </audio>
        <div class="media-preview-fallback" *ngIf="!canInlinePreview">
          <mat-icon aria-hidden="true">{{ mediaIcon }}</mat-icon>
          <p>Preview is not available for this file type.</p>
        </div>
      </mat-dialog-content>

      <mat-dialog-actions align="end">
        <a mat-stroked-button [routerLink]="['/entries', asset.entry_id]" [queryParams]="{ entryType: asset.entry_type }" (click)="close()">
          <mat-icon aria-hidden="true">open_in_new</mat-icon>
          <span>Open entry</span>
        </a>
        <button mat-raised-button color="warn" type="button" (click)="delete()">
          <mat-icon aria-hidden="true">delete</mat-icon>
          <span>Delete</span>
        </button>
      </mat-dialog-actions>
    </section>
  `,
  styles: [`
    .media-preview-dialog { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; width: min(72rem, 100%); max-height: min(84vh, 54rem); overflow: hidden; color: var(--colour-text-primary); }
    .media-preview-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--spacing-md); padding: var(--spacing-md); border-bottom: 1px solid var(--colour-border); }
    .media-preview-header h2, .media-preview-header p { margin: 0; }
    .media-preview-header h2 { overflow-wrap: anywhere; }
    .media-preview-header p, .media-preview-fallback { color: var(--colour-text-secondary); font-weight: 750; }
    .section-eyebrow { color: var(--colour-text-secondary); font-size: 0.78rem; font-weight: 900; letter-spacing: 0.08em; text-transform: uppercase; }
    .media-preview-body { display: grid; place-items: center; min-height: 18rem; margin: 0; padding: var(--spacing-md); background: var(--colour-surface-muted); }
    .media-preview-body img { display: block; max-width: 100%; max-height: 68vh; border-radius: var(--radius-lg); object-fit: contain; }
    .media-preview-body iframe { width: 100%; min-height: 68vh; border: 1px solid var(--colour-border); border-radius: var(--radius-lg); background: var(--colour-surface); }
    .media-preview-body audio { width: min(100%, 42rem); }
    .media-preview-fallback { display: grid; place-items: center; gap: var(--spacing-sm); text-align: center; }
    .media-preview-fallback mat-icon { width: 56px; height: 56px; color: var(--colour-primary); font-size: 56px; }
    mat-dialog-actions { gap: var(--spacing-sm); margin: 0; padding: var(--spacing-md); border-top: 1px solid var(--colour-border); }
    mat-dialog-actions a, mat-dialog-actions button { min-height: 44px; border-radius: var(--radius-pill); }
    @media (max-width: 600px) { .media-preview-dialog { max-height: 92vh; } .media-preview-body { padding: var(--spacing-sm); } }
  `],
})
export class MediaPreviewDialogComponent {
  readonly data = inject<MediaPreviewDialogData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<MediaPreviewDialogComponent, "delete" | undefined>);
  private readonly sanitizer = inject(DomSanitizer);
  readonly asset = this.data.asset;

  get isImage(): boolean { return this.asset.mime_type.startsWith("image/"); }
  get isPdf(): boolean { return this.asset.mime_type === "application/pdf"; }
  get isAudio(): boolean { return this.asset.mime_type.startsWith("audio/"); }
  get canInlinePreview(): boolean { return Boolean(this.asset.url) && (this.isImage || this.isPdf || this.isAudio); }
  get safeUrl(): SafeResourceUrl | null { return this.asset.url ? this.sanitizer.bypassSecurityTrustResourceUrl(this.asset.url) : null; }
  get mediaTypeLabel(): string { return this.isImage ? "Image" : this.isPdf ? "PDF" : this.isAudio ? "Audio" : "File"; }
  get entryTypeLabel(): string { return this.asset.entry_type === "daily" ? "Daily entry" : "Dream entry"; }
  get mediaIcon(): string { return this.isImage ? "image" : this.isPdf ? "picture_as_pdf" : this.isAudio ? "graphic_eq" : "attach_file"; }

  close(): void { this.dialogRef.close(); }
  delete(): void { this.dialogRef.close("delete"); }

  formatBytes(value: number): string {
    if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(value >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
    if (value >= 1024) return `${Math.round(value / 1024)} KB`;
    return `${value} B`;
  }
}
