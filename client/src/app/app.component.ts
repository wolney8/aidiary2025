// Root component with shell layout
import { Component, DestroyRef, inject, isDevMode } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { CommonModule } from "@angular/common";
import {
  NavigationCancel,
  NavigationEnd,
  NavigationError,
  NavigationStart,
  Router,
  RouterLink,
  RouterOutlet,
} from "@angular/router";
import { TopBarComponent } from "./core/components/top-bar/top-bar.component";
import { SideNavComponent } from "./core/components/side-nav/side-nav.component";
import { MatSidenavModule } from "@angular/material/sidenav";
import { MatDialog, MatDialogRef } from "@angular/material/dialog";
import { MatProgressBarModule } from "@angular/material/progress-bar";
import { distinctUntilChanged } from "rxjs";
import { AuthService } from "./core/services/auth.service";
import { InactivityService } from "./core/services/inactivity.service";
import { LoadingService } from "./core/services/loading.service";
import { ThemeService } from "./core/services/theme.service";
import {
  InactivityWarningComponent,
  InactivityWarningResult,
} from "./shared/components/inactivity-warning/inactivity-warning.component";
import { environment } from "../environments/environment";
import { environment as environmentProd } from "../environments/environment.prod";
import { ChatCompanionComponent } from "./shared/components/chat-companion/chat-companion.component";
import { CookieConsentComponent } from "./shared/components/cookie-consent/cookie-consent.component";
import { AnnouncementBannerComponent } from "./shared/components/announcement-banner/announcement-banner.component";
import { APP_VERSION } from "./version";
import { User } from "./core/models/user.model";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    TopBarComponent,
    SideNavComponent,
    MatSidenavModule,
    MatProgressBarModule,
    ChatCompanionComponent,
    CookieConsentComponent,
    AnnouncementBannerComponent,
  ],
  template: `
    <a class="skip-link" href="#main-content">Skip to main content</a>
    <div
      *ngIf="showGlobalLoading"
      class="route-loading"
      role="status"
      aria-live="polite"
      data-testid="route-loading-indicator"
    >
      <mat-progress-bar mode="indeterminate"></mat-progress-bar>
      <span class="sr-only">Loading page</span>
    </div>
    <ng-container *ngIf="showAuthenticatedShell; else publicLayout">
      <mat-sidenav-container
        class="authenticated-app-shell"
        data-testid="authenticated-app-shell"
      >
        <mat-sidenav #sidenav mode="over" position="start">
          <app-side-nav
            [onboardingMode]="isOnboardingRoute"
            (closeSidenav)="sidenav.close()"
          ></app-side-nav>
        </mat-sidenav>

        <mat-sidenav-content>
          <app-top-bar
            [onboardingMode]="isOnboardingRoute"
            (toggleSidenav)="sidenav.toggle()"
          ></app-top-bar>
          <app-announcement-banner
            *ngIf="!isOnboardingRoute"
          ></app-announcement-banner>
          <main id="main-content" class="main-content" tabindex="-1">
            <router-outlet></router-outlet>
          </main>
          <footer class="app-footer" aria-label="OpenMynd information">
            <span>OpenMynd {{ versionLabel }}</span>
            <a routerLink="/privacy">Privacy policy</a>
            <a routerLink="/terms">Terms</a>
            <a routerLink="/cookies">Cookie policy</a>
          </footer>
          <app-chat-companion
            *ngIf="showChatCompanion"
            data-testid="chat-companion"
          ></app-chat-companion>
        </mat-sidenav-content>
      </mat-sidenav-container>
    </ng-container>

    <ng-template #publicLayout>
      <main id="main-content" class="main-content public-main-content" tabindex="-1">
        <router-outlet></router-outlet>
      </main>
    </ng-template>
    <app-cookie-consent></app-cookie-consent>
  `,
  styles: [
    `
      .authenticated-app-shell {
        height: 100vh;
      }

      .skip-link {
        position: fixed;
        top: var(--spacing-xs);
        left: var(--spacing-xs);
        z-index: 2000;
        padding: 0.75rem 1rem;
        border-radius: var(--radius-pill);
        background: var(--colour-primary);
        color: var(--colour-on-primary);
        font-weight: 700;
        text-decoration: none;
        transform: translateY(-150%);
        transition: transform 0.15s ease;
      }

      .skip-link:focus {
        transform: translateY(0);
      }

      .route-loading {
        position: fixed;
        inset: 0 0 auto;
        z-index: 2200;
        pointer-events: none;
      }

      .route-loading mat-progress-bar {
        height: 4px;
        --mdc-linear-progress-active-indicator-color: var(--colour-primary);
        --mdc-linear-progress-track-color: color-mix(
          in srgb,
          var(--colour-primary) 18%,
          transparent
        );
      }

      .route-loading::after {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        background:
          radial-gradient(
            circle at 50% 0,
            color-mix(in srgb, var(--colour-primary) 12%, transparent),
            transparent 32rem
          ),
          color-mix(in srgb, var(--colour-background) 10%, transparent);
        opacity: 0.72;
      }

      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      .main-content {
        padding: var(--spacing-md);
        max-width: 1400px;
        margin: 0 auto;
      }

      .app-footer {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--spacing-xs);
        flex-wrap: wrap;
        padding: var(--spacing-sm) var(--spacing-md) var(--spacing-md);
        color: var(--colour-text-secondary);
        font-size: 0.88rem;
      }

      .app-footer a {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 36px;
        padding: 0 0.8rem;
        border: 1px solid var(--colour-border);
        border-radius: var(--radius-pill);
        background: var(--colour-surface-muted);
        color: var(--colour-text-secondary);
        font: inherit;
        font-weight: 700;
        text-decoration: none;
      }

      .app-footer a:hover {
        background: var(--colour-control-hover);
        color: var(--colour-text-primary);
      }

      .app-footer a:focus-visible {
        outline: var(--focus-outline);
        outline-offset: 3px;
      }

      .public-main-content {
        max-width: none;
        padding: 0;
      }
    `,
  ],
})
export class AppComponent {
  private readonly authService = inject(AuthService);
  private readonly inactivityService = inject(InactivityService);
  private readonly loadingService = inject(LoadingService);
  private readonly themeService = inject(ThemeService);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly destroyRef = inject(DestroyRef);
  private readonly inactivityConfig = isDevMode()
    ? environment.inactivity
    : environmentProd.inactivity;

  private warningDialogRef?: MatDialogRef<
    InactivityWarningComponent,
    InactivityWarningResult
  >;

  title = "OpenMynd";
  readonly versionLabel = APP_VERSION;
  isAuthenticated = this.authService.isAuthenticated();
  showAuthenticatedShell = this.shouldShowAuthenticatedShell(this.router.url);
  currentUser = this.authService.getCurrentUser();
  isOnboardingRoute = this.isOnboardingUrl(this.router.url);
  showChatCompanion = this.shouldShowChatCompanion(this.router.url);
  isRouteLoading = false;
  readonly isApiLoading = this.loadingService.isLoading;

  get showGlobalLoading(): boolean {
    return this.isRouteLoading || this.isApiLoading();
  }

  constructor() {
    this.themeService.mode();

    this.router.events
      .pipe(
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((event) => {
        if (event instanceof NavigationStart) {
          this.isRouteLoading = true;
          return;
        }

        if (
          event instanceof NavigationEnd ||
          event instanceof NavigationCancel ||
          event instanceof NavigationError
        ) {
          this.isRouteLoading = false;
        }

        if (event instanceof NavigationEnd) {
          this.isOnboardingRoute = this.isOnboardingUrl(event.urlAfterRedirects);
          this.showAuthenticatedShell = this.shouldShowAuthenticatedShell(
            event.urlAfterRedirects,
          );
          this.showChatCompanion = this.shouldShowChatCompanion(
            event.urlAfterRedirects,
          );
        }
      });

    this.authService.currentUser$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((user) => {
        this.currentUser = user;
        this.isAuthenticated = !!user && this.authService.isAuthenticated();
        this.showAuthenticatedShell = this.shouldShowAuthenticatedShell(
          this.router.url,
        );
        this.isOnboardingRoute = this.isOnboardingUrl(this.router.url);
        this.showChatCompanion = this.shouldShowChatCompanion(this.router.url);

        if (user && this.inactivityConfig.enabled) {
          this.inactivityService.startTracking(
            this.inactivityConfig.timeoutSeconds,
            this.inactivityConfig.warningSeconds,
          );
          return;
        }

        this.inactivityService.stopTracking();
        this.closeWarningDialog();
      });

    this.inactivityService.warningState$
      .pipe(distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((isWarningVisible) => {
        if (isWarningVisible) {
          this.openWarningDialog();
          return;
        }

        this.closeWarningDialog();
      });

    this.inactivityService.countdownSeconds$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((countdownSeconds) => {
        if (this.warningDialogRef?.componentInstance) {
          this.warningDialogRef.componentInstance.countdownSeconds =
            countdownSeconds;
        }
      });

    this.inactivityService.expired$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        this.logoutForInactivity();
      });
  }

  private openWarningDialog(): void {
    if (this.warningDialogRef) {
      return;
    }

    this.warningDialogRef = this.dialog.open(InactivityWarningComponent, {
      disableClose: true,
      width: "420px",
      data: { countdownSeconds: this.inactivityService.getCountdownSeconds() },
    });

    this.warningDialogRef
      .afterClosed()
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((result) => {
        this.warningDialogRef = undefined;

        if (result === "stay") {
          this.inactivityService.resetTimer(true);
          return;
        }

        if (result === "logout") {
          this.logoutForInactivity();
        }
      });
  }

  private closeWarningDialog(): void {
    if (!this.warningDialogRef) {
      return;
    }

    this.warningDialogRef.close();
    this.warningDialogRef = undefined;
  }

  private logoutForInactivity(): void {
    this.closeWarningDialog();
    this.inactivityService.stopTracking();
    this.authService.logout();
  }

  private shouldShowChatCompanion(url: string): boolean {
    return (
      this.isAuthenticated &&
      this.isChatEnabled(this.currentUser) &&
      this.isDiaryChatRoute(url)
    );
  }

  private shouldShowAuthenticatedShell(url: string): boolean {
    return this.isAuthenticated && !this.isPublicShellUrl(url);
  }

  private isPublicShellUrl(url: string): boolean {
    return (
      /^\/login(?:\/|\?|#|$)/.test(url) ||
      /^\/register(?:\/|\?|#|$)/.test(url) ||
      /^\/forgot-password(?:\/|\?|#|$)/.test(url) ||
      /^\/reset-password(?:\/|\?|#|$)/.test(url) ||
      /^\/verify-email(?:\/|\?|#|$)/.test(url) ||
      /^\/oauth\/callback(?:\/|\?|#|$)/.test(url) ||
      /^\/privacy(?:\/|\?|#|$)/.test(url) ||
      /^\/terms(?:\/|\?|#|$)/.test(url) ||
      /^\/cookies(?:\/|\?|#|$)/.test(url)
    );
  }

  private isDiaryChatRoute(url: string): boolean {
    return (
      /^\/entries(?:\/|\?|#|$)/.test(url) ||
      /^\/cbt(?:\/|\?|#|$)/.test(url) ||
      /^\/important-days(?:\/|\?|#|$)/.test(url) ||
      /^\/reflections(?:\/|\?|#|$)/.test(url)
    );
  }

  private isOnboardingUrl(url: string): boolean {
    return /^\/onboarding(?:\/|\?|#|$)/.test(url);
  }

  private isChatEnabled(user: User | null): boolean {
    return Number(user?.chat_enabled ?? 1) !== 0;
  }
}
