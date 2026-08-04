// Application routing configuration
import { Routes } from "@angular/router";
import { authGuard, authMatchGuard } from "./auth/auth.guard";
import { pendingChangesGuard } from "./entries/pending-changes.guard";

export const routes: Routes = [
  { path: "", redirectTo: "/login", pathMatch: "full" },
  {
    path: "login",
    title: "Login | OpenMynd",
    loadComponent: () =>
      import("./auth/login/login.component").then((m) => m.LoginComponent),
  },
  {
    path: "register",
    title: "Create account | OpenMynd",
    loadComponent: () =>
      import("./auth/register/register.component").then(
        (m) => m.RegisterComponent,
      ),
  },
  {
    path: "privacy",
    title: "Privacy policy | OpenMynd",
    data: { legalPage: "privacy" },
    loadComponent: () =>
      import("./legal/legal-page.component").then((m) => m.LegalPageComponent),
  },
  {
    path: "terms",
    title: "Terms | OpenMynd",
    data: { legalPage: "terms" },
    loadComponent: () =>
      import("./legal/legal-page.component").then((m) => m.LegalPageComponent),
  },
  {
    path: "cookies",
    title: "Cookie policy | OpenMynd",
    data: { legalPage: "cookies" },
    loadComponent: () =>
      import("./legal/legal-page.component").then((m) => m.LegalPageComponent),
  },
  {
    path: "entries",
    title: "Entries | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    loadComponent: () =>
      import("./entries/list/list.component").then((m) => m.ListComponent),
  },
  {
    path: "entries/create",
    title: "New entry | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./entries/create/create.component").then(
        (m) => m.CreateComponent,
      ),
  },
  {
    path: "entries/:id/edit",
    title: "Edit entry | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./entries/create/create.component").then(
        (m) => m.CreateComponent,
      ),
  },
  {
    path: "entries/:id",
    title: "View entry | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    loadComponent: () =>
      import("./entries/detail/detail.component").then(
        (m) => m.DetailComponent,
      ),
  },
  {
    path: "cbt",
    title: "Thought records | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    loadComponent: () =>
      import("./cbt/cbt-dashboard.component").then(
        (m) => m.CbtDashboardComponent,
      ),
  },
  {
    path: "cbt/:id",
    title: "Thought record | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./cbt/cbt-worksheet.component").then(
        (m) => m.CbtWorksheetComponent,
      ),
  },
  {
    path: "important-days",
    title: "Important days | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    loadComponent: () =>
      import("./settings/important-days/important-days.component").then(
        (m) => m.ImportantDaysComponent,
      ),
  },
  {
    path: "reflections",
    title: "Reflection summaries | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    loadComponent: () =>
      import("./reflections/reflection-summaries.component").then(
        (m) => m.ReflectionSummariesComponent,
      ),
  },
  {
    path: "profile",
    title: "Profile | OpenMynd",
    canActivate: [authGuard],
    canMatch: [authMatchGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./profile/profile.component").then((m) => m.ProfileComponent),
  },
  {
    path: "settings",
    title: "Settings | OpenMynd",
    canActivate: [authGuard],
    canActivateChild: [authGuard],
    canMatch: [authMatchGuard],
    loadComponent: () =>
      import("./settings/settings.component").then((m) => m.SettingsComponent),
    children: [
      {
        path: "",
        pathMatch: "full",
        redirectTo: "personalisation",
      },
      {
        path: "appearance",
        title: "Appearance | OpenMynd",
        loadComponent: () =>
          import("./settings/appearance/appearance.component").then(
            (m) => m.AppearanceComponent,
          ),
      },
      {
        path: "personalisation",
        title: "Customisation | OpenMynd",
        canDeactivate: [pendingChangesGuard],
        loadComponent: () =>
          import("./settings/personalisation/personalisation.component").then(
            (m) => m.PersonalisationComponent,
          ),
      },
      {
        path: "important-days",
        pathMatch: "full",
        redirectTo: "/important-days",
      },
      {
        path: "import",
        title: "Import | OpenMynd",
        canDeactivate: [pendingChangesGuard],
        loadComponent: () =>
          import("./settings/import/import.component").then(
            (m) => m.ImportComponent,
          ),
      },
      {
        path: "export",
        title: "Export | OpenMynd",
        loadComponent: () =>
          import("./settings/export/export.component").then(
            (m) => m.ExportComponent,
          ),
      },
    ],
  },
  { path: "**", redirectTo: "/login" },
];
