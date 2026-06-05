import { Component, Input } from "@angular/core";
import { CommonModule } from "@angular/common";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";

@Component({
  selector: "app-back-to-top",
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule],
  template: `
    <div class="back-to-top-row">
      <button
        mat-stroked-button
        type="button"
        class="back-to-top-button"
        (click)="scrollToTop()"
        [attr.aria-label]="label"
      >
        <mat-icon>north</mat-icon>
        {{ label }}
      </button>
    </div>
  `,
  styles: [
    `
      .back-to-top-row {
        display: flex;
        justify-content: center;
        margin-top: var(--spacing-md);
      }

      .back-to-top-button {
        border-color: var(--colour-border);
        color: var(--colour-text-secondary);
        border-radius: var(--radius-pill);
      }

      .back-to-top-button mat-icon {
        margin-right: var(--spacing-xs);
      }
    `,
  ],
})
export class BackToTopComponent {
  @Input() label = "Back to top";

  scrollToTop(): void {
    const scrollTargets = new Set<HTMLElement>();
    const scrollingElement = document.scrollingElement;

    if (scrollingElement instanceof HTMLElement) {
      scrollTargets.add(scrollingElement);
    }

    document
      .querySelectorAll<HTMLElement>(".mat-drawer-content, .mat-sidenav-content")
      .forEach((element) => scrollTargets.add(element));

    scrollTargets.forEach((target) => {
      target.scrollTo({ top: 0, behavior: "smooth" });
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}
