// Application routing configuration
import { Routes } from "@angular/router";
import { authGuard } from "./auth/auth.guard";
import { pendingChangesGuard } from "./entries/pending-changes.guard";

export const routes: Routes = [
  { path: "", redirectTo: "/login", pathMatch: "full" },
  {
    path: "login",
    title: "Login | AI Diary",
    loadComponent: () =>
      import("./auth/login/login.component").then((m) => m.LoginComponent),
  },
  {
    path: "register",
    title: "Create account | AI Diary",
    loadComponent: () =>
      import("./auth/register/register.component").then(
        (m) => m.RegisterComponent,
      ),
  },
  {
    path: "entries",
    title: "Entries | AI Diary",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./entries/list/list.component").then((m) => m.ListComponent),
  },
  {
    path: "entries/create",
    title: "New entry | AI Diary",
    canActivate: [authGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./entries/create/create.component").then(
        (m) => m.CreateComponent,
      ),
  },
  {
    path: "entries/:id/edit",
    title: "Edit entry | AI Diary",
    canActivate: [authGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./entries/create/create.component").then(
        (m) => m.CreateComponent,
      ),
  },
  {
    path: "entries/:id",
    title: "View entry | AI Diary",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./entries/detail/detail.component").then(
        (m) => m.DetailComponent,
      ),
  },
  {
    path: "cbt",
    title: "Thought records | AI Diary",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./cbt/cbt-dashboard.component").then(
        (m) => m.CbtDashboardComponent,
      ),
  },
  {
    path: "cbt/:id",
    title: "Thought record | AI Diary",
    canActivate: [authGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./cbt/cbt-worksheet.component").then(
        (m) => m.CbtWorksheetComponent,
      ),
  },
  {
    path: "profile",
    title: "Profile | AI Diary",
    canActivate: [authGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./profile/profile.component").then((m) => m.ProfileComponent),
  },
  {
    path: "settings",
    title: "Settings | AI Diary",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./settings/settings.component").then((m) => m.SettingsComponent),
    children: [
      {
        path: "",
        pathMatch: "full",
        redirectTo: "personalisation",
      },
      {
        path: "personalisation",
        title: "Customisation | AI Diary",
        canDeactivate: [pendingChangesGuard],
        loadComponent: () =>
          import("./settings/personalisation/personalisation.component").then(
            (m) => m.PersonalisationComponent,
          ),
      },
      {
        path: "important-days",
        title: "Important days | AI Diary",
        loadComponent: () =>
          import("./settings/important-days/important-days.component").then(
            (m) => m.ImportantDaysComponent,
          ),
      },
      {
        path: "import",
        title: "Import | AI Diary",
        canDeactivate: [pendingChangesGuard],
        loadComponent: () =>
          import("./settings/import/import.component").then(
            (m) => m.ImportComponent,
          ),
      },
      {
        path: "export",
        title: "Export | AI Diary",
        loadComponent: () =>
          import("./settings/export/export.component").then(
            (m) => m.ExportComponent,
          ),
      },
    ],
  },
  { path: "**", redirectTo: "/login" },
];
