import { CommonModule } from "@angular/common";
import { Component, HostListener, inject } from "@angular/core";
import {
  MAT_DIALOG_DATA,
  MatDialogModule,
  MatDialogRef,
} from "@angular/material/dialog";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import { EntryAsset } from "../../../core/models/entry.model";

export interface EntryImageGalleryData {
  images: EntryAsset[];
  initialImageId: number;
  title?: string;
  subtitle?: string;
}

@Component({
  selector: "app-entry-image-gallery",
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatDialogModule, MatIconModule],
  template: `
    <section
      class="entry-image-gallery"
      data-testid="entry-image-gallery"
      aria-labelledby="entry-image-gallery-title"
    >
      <header class="entry-image-gallery-header">
        <div>
          <h2 id="entry-image-gallery-title">{{ data.title || "Entry photos" }}</h2>
          <p aria-live="polite">{{ data.subtitle || "Photo " + (currentIndex + 1) + " of " + images.length }}</p>
        </div>
        <button
          mat-icon-button
          type="button"
          [attr.aria-label]="'Close ' + (data.title || 'photo gallery')"
          data-testid="entry-image-gallery-close"
          (click)="close()"
        >
          <mat-icon>close</mat-icon>
        </button>
      </header>

      <div class="entry-image-gallery-stage">
        <button
          *ngIf="images.length > 1"
          mat-icon-button
          type="button"
          class="entry-image-gallery-nav previous"
          aria-label="Show previous photo"
          data-testid="entry-image-gallery-previous"
          (click)="showPrevious()"
        >
          <mat-icon>chevron_left</mat-icon>
        </button>

        <figure>
          <img
            [src]="currentImage.url"
            [alt]="getImageAlt(currentImage)"
            data-testid="entry-image-gallery-image"
          />
          <figcaption>{{ currentImage.original_filename }}</figcaption>
        </figure>

        <button
          *ngIf="images.length > 1"
          mat-icon-button
          type="button"
          class="entry-image-gallery-nav next"
          aria-label="Show next photo"
          data-testid="entry-image-gallery-next"
          (click)="showNext()"
        >
          <mat-icon>chevron_right</mat-icon>
        </button>
      </div>

      <nav
        *ngIf="images.length > 1"
        class="entry-image-gallery-thumbnails"
        aria-label="Choose a photo"
      >
        <button
          *ngFor="let image of images; let index = index"
          type="button"
          class="entry-image-gallery-thumbnail"
          [class.is-selected]="index === currentIndex"
          [attr.aria-label]="'Show ' + getImageAlt(image)"
          [attr.aria-pressed]="index === currentIndex"
          [attr.data-testid]="'entry-image-gallery-thumbnail-' + image.id"
          (click)="selectImage(index)"
        >
          <img [src]="image.url" alt="" />
        </button>
      </nav>

      <p class="entry-image-gallery-help" *ngIf="images.length > 1">
        Use the arrow keys to move between photos.
      </p>
    </section>
  `,
  styles: [
    `
      .entry-image-gallery {
        display: grid;
        width: min(68rem, calc(100vw - 2rem));
        max-height: calc(100vh - 2rem);
        color: var(--colour-text-primary);
        background: var(--colour-surface-elevated);
        overflow-x: hidden;
        overflow-y: auto;
      }

      .entry-image-gallery-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md);
        border-bottom: 1px solid var(--colour-border);
      }

      .entry-image-gallery-header h2,
      .entry-image-gallery-header p,
      .entry-image-gallery-help,
      figure {
        margin: 0;
      }

      .entry-image-gallery-header h2 {
        font-size: 1.25rem;
      }

      .entry-image-gallery-header p,
      .entry-image-gallery-help,
      figcaption {
        color: var(--colour-text-secondary);
      }

      .entry-image-gallery-stage {
        position: relative;
        display: grid;
        min-height: 18rem;
        place-items: center;
        padding: var(--spacing-sm) 4.5rem;
        background: var(--colour-background);
        overflow: hidden;
      }

      figure {
        display: grid;
        width: 100%;
        justify-items: center;
        gap: var(--spacing-xs);
      }

      figure > img {
        display: block;
        max-width: 100%;
        max-height: min(66vh, 44rem);
        border-radius: var(--radius-md);
        object-fit: contain;
      }

      figcaption {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .entry-image-gallery-nav {
        position: absolute;
        top: 50%;
        z-index: 1;
        width: 3rem;
        height: 3rem;
        border: 1px solid var(--colour-border);
        background: var(--colour-surface-elevated);
        color: var(--colour-text-primary);
        transform: translateY(-50%);
      }

      .entry-image-gallery-nav.previous {
        left: var(--spacing-sm);
      }

      .entry-image-gallery-nav.next {
        right: var(--spacing-sm);
      }

      .entry-image-gallery-thumbnails {
        display: flex;
        gap: var(--spacing-xs);
        padding: var(--spacing-sm) var(--spacing-md) var(--spacing-xs);
        overflow-x: auto;
      }

      .entry-image-gallery-thumbnail {
        width: 4.5rem;
        height: 3.5rem;
        flex: 0 0 auto;
        padding: 0.2rem;
        border: 2px solid transparent;
        border-radius: var(--radius-sm);
        background: var(--colour-surface-muted);
        cursor: pointer;
      }

      .entry-image-gallery-thumbnail.is-selected {
        border-color: var(--colour-primary);
      }

      .entry-image-gallery-thumbnail:focus-visible,
      .entry-image-gallery-nav:focus-visible,
      .entry-image-gallery-header button:focus-visible {
        outline: var(--focus-outline);
        outline-offset: 2px;
      }

      .entry-image-gallery-thumbnail img {
        display: block;
        width: 100%;
        height: 100%;
        border-radius: calc(var(--radius-sm) - 2px);
        object-fit: cover;
      }

      .entry-image-gallery-help {
        padding: 0 var(--spacing-md) var(--spacing-sm);
        font-size: 0.88rem;
      }

      @media (max-width: 640px) {
        .entry-image-gallery {
          width: calc(100vw - 1rem);
          max-height: calc(100vh - 1rem);
        }

        .entry-image-gallery-header {
          padding: var(--spacing-sm);
        }

        .entry-image-gallery-stage {
          min-height: 14rem;
          padding: var(--spacing-xs) 3.25rem;
        }

        .entry-image-gallery-nav {
          width: 2.75rem;
          height: 2.75rem;
        }

        .entry-image-gallery-nav.previous {
          left: 0.25rem;
        }

        .entry-image-gallery-nav.next {
          right: 0.25rem;
        }

        figure > img {
          max-height: 58vh;
        }

        .entry-image-gallery-thumbnails {
          padding-inline: var(--spacing-sm);
        }

        .entry-image-gallery-help {
          padding-inline: var(--spacing-sm);
        }
      }
    `,
  ],
})
export class EntryImageGalleryComponent {
  readonly data = inject<EntryImageGalleryData>(MAT_DIALOG_DATA);
  private readonly dialogRef = inject(MatDialogRef<EntryImageGalleryComponent>);

  readonly images = this.data.images.filter((image) => Boolean(image?.url));
  currentIndex = Math.max(
    0,
    this.images.findIndex(
      (image) => Number(image.id) === Number(this.data.initialImageId),
    ),
  );

  get currentImage(): EntryAsset {
    return this.images[this.currentIndex];
  }

  close(): void {
    this.dialogRef.close();
  }

  showPrevious(): void {
    if (this.images.length < 2) return;
    this.currentIndex =
      (this.currentIndex - 1 + this.images.length) % this.images.length;
  }

  showNext(): void {
    if (this.images.length < 2) return;
    this.currentIndex = (this.currentIndex + 1) % this.images.length;
  }

  selectImage(index: number): void {
    if (index >= 0 && index < this.images.length) {
      this.currentIndex = index;
    }
  }

  getImageAlt(image: EntryAsset): string {
    return image.original_filename?.trim() || "Entry photo";
  }

  @HostListener("keydown", ["$event"])
  handleKeydown(event: KeyboardEvent): void {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      this.showPrevious();
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      this.showNext();
    } else if (event.key === "Home") {
      event.preventDefault();
      this.selectImage(0);
    } else if (event.key === "End") {
      event.preventDefault();
      this.selectImage(this.images.length - 1);
    }
  }
}
