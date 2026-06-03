// Application routing configuration
import { Routes } from "@angular/router";
import { authGuard } from "./auth/auth.guard";
import { pendingChangesGuard } from "./entries/pending-changes.guard";

export const routes: Routes = [
  { path: "", redirectTo: "/login", pathMatch: "full" },
  {
    path: "login",
    loadComponent: () =>
      import("./auth/login/login.component").then((m) => m.LoginComponent),
  },
  {
    path: "register",
    loadComponent: () =>
      import("./auth/register/register.component").then(
        (m) => m.RegisterComponent,
      ),
  },
  {
    path: "entries",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./entries/list/list.component").then((m) => m.ListComponent),
  },
  {
    path: "entries/create",
    canActivate: [authGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./entries/create/create.component").then(
        (m) => m.CreateComponent,
      ),
  },
  {
    path: "entries/:id/edit",
    canActivate: [authGuard],
    canDeactivate: [pendingChangesGuard],
    loadComponent: () =>
      import("./entries/create/create.component").then(
        (m) => m.CreateComponent,
      ),
  },
  {
    path: "entries/:id",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./entries/detail/detail.component").then(
        (m) => m.DetailComponent,
      ),
  },
  {
    path: "profile",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./profile/profile.component").then((m) => m.ProfileComponent),
  },
  {
    path: "settings",
    canActivate: [authGuard],
    loadComponent: () =>
      import("./settings/settings.component").then((m) => m.SettingsComponent),
    children: [
      {
        path: "",
        pathMatch: "full",
        redirectTo: "import",
      },
      {
        path: "import",
        loadComponent: () =>
          import("./settings/import/import.component").then(
            (m) => m.ImportComponent,
          ),
      },
      {
        path: "export",
        loadComponent: () =>
          import("./settings/export/export.component").then(
            (m) => m.ExportComponent,
          ),
      },
    ],
  },
  { path: "**", redirectTo: "/login" },
];
