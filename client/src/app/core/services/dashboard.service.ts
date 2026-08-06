import { HttpClient, HttpHeaders, HttpParams } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable, throwError } from "rxjs";
import { environment } from "../../../environments/environment";
import {
  DashboardOverview,
  DashboardRange,
  DashboardTheme,
} from "../models/dashboard.model";
import { AuthService } from "./auth.service";

@Injectable({ providedIn: "root" })
export class DashboardService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/dashboard/overview`;

  getOverview(
    range: DashboardRange,
    theme?: Pick<DashboardTheme, "label" | "kind"> | null,
  ): Observable<DashboardOverview> {
    if (!this.authService.isAuthenticated()) {
      return throwError(() => new Error("User not authenticated"));
    }

    const token = this.authService.getToken();
    const headers = new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
    let params = new HttpParams().set("range", range);
    if (theme?.label && theme.kind) {
      params = params
        .set("theme_label", theme.label)
        .set("theme_kind", theme.kind);
    }

    return this.http.get<DashboardOverview>(this.apiUrl, { headers, params });
  }
}
