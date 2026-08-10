import { CommonModule } from "@angular/common";
import { Component, OnInit, computed, inject, signal } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatIconModule } from "@angular/material/icon";
import {
  AnnouncementService,
  PlatformAnnouncement,
} from "../../../core/services/announcement.service";

@Component({
  selector: "app-announcement-banner",
  standalone: true,
  imports: [CommonModule, MatButtonModule, MatIconModule],
  template: `
    <section
      *ngIf="banner() as announcement"
      class="platform-announcement-banner"
      [class.platform-announcement-banner--success]="announcement.severity === 'success'"
      [class.platform-announcement-banner--warning]="announcement.severity === 'warning'"
      [class.platform-announcement-banner--critical]="announcement.severity === 'critical'"
      role="status"
      aria-live="polite"
      data-testid="platform-announcement-banner"
    >
      <div class="platform-announcement-banner__content">
        <mat-icon aria-hidden="true">{{ iconFor(announcement) }}</mat-icon>
        <div>
          <strong>{{ announcement.title }}</strong>
          <p>{{ announcement.message }}</p>
        </div>
      </div>
      <button
        *ngIf="announcement.dismissible"
        mat-icon-button
        type="button"
        class="platform-announcement-banner__dismiss"
        (click)="dismiss(announcement)"
        [attr.aria-label]="'Dismiss ' + announcement.title"
        data-testid="platform-announcement-dismiss"
      >
        <mat-icon aria-hidden="true">close</mat-icon>
      </button>
    </section>
  `,
  styles: [`
    .platform-announcement-banner {
      box-sizing: border-box;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--spacing-sm);
      max-width: 1400px;
      margin: var(--spacing-sm) auto 0;
      padding: var(--spacing-sm) var(--spacing-md);
      border: 1px solid var(--colour-border);
      border-radius: var(--radius-lg);
      background: var(--colour-info-bg);
      color: var(--colour-text-primary);
      box-shadow: 0 12px 30px var(--colour-shadow-soft);
    }

    .platform-announcement-banner--success {
      border-color: color-mix(in srgb, var(--colour-success-text) 72%, var(--colour-border));
      background: var(--colour-success-bg);
    }

    .platform-announcement-banner--warning {
      border-color: color-mix(in srgb, var(--colour-warning-text) 72%, var(--colour-border));
      background: var(--colour-warning-bg);
    }

    .platform-announcement-banner--critical {
      border-color: color-mix(in srgb, var(--colour-danger-text) 76%, var(--colour-border));
      background: var(--colour-danger-bg);
    }

    .platform-announcement-banner__content {
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
      min-width: 0;
    }

    .platform-announcement-banner__content mat-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      flex: 0 0 44px;
      width: 44px;
      height: 44px;
      border-radius: var(--radius-pill);
      background: var(--colour-control-selected);
      color: var(--colour-control-selected-text);
      font-size: 22px;
    }

    .platform-announcement-banner strong,
    .platform-announcement-banner p {
      margin: 0;
    }

    .platform-announcement-banner p {
      color: var(--colour-text-secondary);
      font-weight: 700;
    }

    .platform-announcement-banner__dismiss {
      flex: 0 0 auto;
    }

    @media (max-width: 720px) {
      .platform-announcement-banner {
        align-items: flex-start;
        margin-inline: var(--spacing-xs);
      }
    }
  `],
})
export class AnnouncementBannerComponent implements OnInit {
  private readonly announcementService = inject(AnnouncementService);
  private readonly announcements = signal<PlatformAnnouncement[]>([]);

  readonly banner = computed(() =>
    this.announcements().find(
      (announcement) =>
        announcement.placement === "banner" || announcement.placement === "both",
    ),
  );

  ngOnInit(): void {
    this.announcementService.announcements$.subscribe((announcements) => {
      this.announcements.set(announcements);
    });
    this.announcementService.refresh().subscribe({ error: () => undefined });
  }

  dismiss(announcement: PlatformAnnouncement): void {
    this.announcementService.dismiss(announcement.id).subscribe({
      error: () => this.announcementService.refresh().subscribe({ error: () => undefined }),
    });
  }

  iconFor(announcement: PlatformAnnouncement): string {
    if (announcement.severity === "critical") return "priority_high";
    if (announcement.severity === "warning") return "warning";
    if (announcement.severity === "success") return "check_circle";
    return "campaign";
  }
}
