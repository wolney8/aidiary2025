// Root component with shell layout
import { Component } from "@angular/core";
import { CommonModule } from "@angular/common";
import { RouterOutlet } from "@angular/router";
import { TopBarComponent } from "./core/components/top-bar/top-bar.component";
import { SideNavComponent } from "./core/components/side-nav/side-nav.component";
import { MatSidenavModule } from "@angular/material/sidenav";

@Component({
  selector: "app-root",
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    TopBarComponent,
    SideNavComponent,
    MatSidenavModule,
  ],
  template: `
    <mat-sidenav-container class="app-container">
      <mat-sidenav #sidenav mode="over" position="start">
        <app-side-nav (closeSidenav)="sidenav.close()"></app-side-nav>
      </mat-sidenav>

      <mat-sidenav-content>
        <app-top-bar (toggleSidenav)="sidenav.toggle()"></app-top-bar>
        <main class="main-content">
          <router-outlet></router-outlet>
        </main>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: [
    `
      .app-container {
        height: 100vh;
      }

      .main-content {
        padding: var(--spacing-md);
        max-width: 1400px;
        margin: 0 auto;
      }
    `,
  ],
})
export class AppComponent {
  title = "AI Diary";
}
