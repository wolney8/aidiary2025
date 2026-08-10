import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable } from "rxjs";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";
import {
  BillingEntitlement,
  BillingPlan,
  BillingTier,
  BillingUsageMetric,
} from "./billing.service";

export type AdminAnnouncementSeverity = "info" | "success" | "warning" | "critical";
export type AdminAnnouncementPlacement = "banner" | "bell" | "both";
export type AdminAnnouncementStatus = "draft" | "published" | "archived";
export type AdminAnnouncementTargetType = "all" | "tier" | "user";

export interface AdminOverview {
  total_users: number;
  manual_overrides: number;
  paid_subscriptions: number;
  published_announcements: number;
  stripe: {
    configured: boolean;
    checkout_tiers: string[];
    checkout_periods: Record<string, string[]>;
  };
  recent_billing_events: Array<{
    provider_event_id: string;
    event_type: string;
    user_id?: number | null;
    processed_at: string;
    metadata?: Record<string, unknown>;
  }>;
}

export interface AdminBillingUser {
  id: number;
  username: string;
  email?: string;
  display_name?: string;
  first_name?: string;
  last_name?: string;
  registered_at?: string | null;
  account_status?: "active" | "restricted" | string;
  auth_methods: string[];
  entitlement: BillingEntitlement;
  usage?: {
    ai_analysis?: BillingUsageMetric;
    ai_image?: BillingUsageMetric;
    ocr_page?: BillingUsageMetric;
    transcription_minute?: BillingUsageMetric;
  };
  subscription?: {
    provider?: string;
    provider_subscription_id?: string | null;
    tier?: BillingTier;
    status?: string;
    billing_period?: string | null;
    current_period_end?: string | null;
    cancel_at_period_end?: boolean;
  } | null;
}

export interface AdminUsersResponse {
  users: AdminBillingUser[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface AdminAnnouncementTarget {
  type: AdminAnnouncementTargetType;
  value?: string | null;
}

export interface AdminAnnouncement {
  id: number;
  title: string;
  message: string;
  severity: AdminAnnouncementSeverity;
  placement: AdminAnnouncementPlacement;
  status: AdminAnnouncementStatus;
  starts_at?: string | null;
  ends_at?: string | null;
  timezone?: string | null;
  dismissible: boolean;
  created_by?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
  read_count?: number;
  dismissed_count?: number;
  targets: AdminAnnouncementTarget[];
}

export interface AdminAnnouncementPayload {
  title: string;
  message: string;
  severity: AdminAnnouncementSeverity;
  placement: AdminAnnouncementPlacement;
  status: AdminAnnouncementStatus;
  starts_at?: string | null;
  ends_at?: string | null;
  timezone?: string | null;
  dismissible: boolean;
  targets: AdminAnnouncementTarget[];
}

@Injectable({ providedIn: "root" })
export class AdminService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/admin`;

  getOverview(): Observable<AdminOverview> {
    return this.http.get<AdminOverview>(`${this.apiUrl}/overview`, {
      headers: this.headers(),
    });
  }

  getUsers(options: {
    search?: string;
    tier?: string;
    status?: string;
    page?: number;
  } = {}): Observable<AdminUsersResponse> {
    const params = new URLSearchParams();
    if (options.search?.trim()) params.set("search", options.search.trim());
    if (options.tier?.trim()) params.set("tier", options.tier.trim());
    if (options.status?.trim()) params.set("status", options.status.trim());
    if (options.page) params.set("page", String(options.page));
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.http.get<AdminUsersResponse>(`${this.apiUrl}/users${query}`, {
      headers: this.headers(),
    });
  }

  updateUserEntitlement(
    userId: number,
    payload: { tier: BillingTier; status: string; valid_until?: string | null },
  ): Observable<{ user: AdminBillingUser }> {
    return this.http.put<{ user: AdminBillingUser }>(
      `${this.apiUrl}/users/${userId}/entitlement`,
      payload,
      { headers: this.headers() },
    );
  }

  updateUserAccess(
    userId: number,
    payload: { account_status: "active" | "restricted" },
  ): Observable<{ user: AdminBillingUser }> {
    return this.http.put<{ user: AdminBillingUser }>(
      `${this.apiUrl}/users/${userId}/access`,
      payload,
      { headers: this.headers() },
    );
  }

  getPlans(): Observable<{ plans: BillingPlan[] }> {
    return this.http.get<{ plans: BillingPlan[] }>(`${this.apiUrl}/billing/plans`, {
      headers: this.headers(),
    });
  }

  updatePlan(
    tier: BillingTier,
    payload: Partial<BillingPlan>,
  ): Observable<{ plan: BillingPlan }> {
    return this.http.put<{ plan: BillingPlan }>(
      `${this.apiUrl}/billing/plans/${tier}`,
      payload,
      { headers: this.headers() },
    );
  }

  getAnnouncements(): Observable<{ announcements: AdminAnnouncement[] }> {
    return this.http.get<{ announcements: AdminAnnouncement[] }>(
      `${this.apiUrl}/announcements`,
      { headers: this.headers() },
    );
  }

  createAnnouncement(
    payload: AdminAnnouncementPayload,
  ): Observable<{ announcement: AdminAnnouncement }> {
    return this.http.post<{ announcement: AdminAnnouncement }>(
      `${this.apiUrl}/announcements`,
      payload,
      { headers: this.headers() },
    );
  }

  updateAnnouncement(
    id: number,
    payload: AdminAnnouncementPayload,
  ): Observable<{ announcement: AdminAnnouncement }> {
    return this.http.put<{ announcement: AdminAnnouncement }>(
      `${this.apiUrl}/announcements/${id}`,
      payload,
      { headers: this.headers() },
    );
  }

  archiveAnnouncement(id: number): Observable<{ announcement: AdminAnnouncement }> {
    return this.http.post<{ announcement: AdminAnnouncement }>(
      `${this.apiUrl}/announcements/${id}/archive`,
      {},
      { headers: this.headers() },
    );
  }

  private headers(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }
}
