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

export type AdminReadinessStatus = "ok" | "warning" | "blocked";

export interface AdminOperationsReadiness {
  app: {
    environment: string;
    production: boolean;
    database_provider: string;
    runtime_migrations_enabled: boolean;
  };
  database: {
    provider: string;
    ok: boolean;
    read_ok: boolean;
    write_ok?: boolean | null;
    latency_ms?: number | null;
    error_type?: string;
    message?: string;
  };
  auth: {
    cookie_mode: boolean;
    csrf_protect: boolean;
    frontend_cookie_only: boolean | null;
  };
  rate_limits: {
    storage: "shared" | "memory" | string;
    configured: boolean;
  };
  stripe: {
    configured: boolean;
    checkout_tiers: string[];
    checkout_periods: Record<string, string[]>;
  };
  email: {
    provider: string;
    from_configured: boolean;
    smtp_host_configured: boolean;
    registration_email_required: boolean;
    ready: boolean;
  };
  oauth: {
    google: {
      client_id_configured: boolean;
      client_secret_configured: boolean;
      redirect_uri_configured: boolean;
      redirect_uri_local: boolean;
      ready: boolean;
    };
  };
  process: Record<string, boolean>;
  checks: Array<{
    key: string;
    label: string;
    status: AdminReadinessStatus;
    detail: string;
  }>;
}

export interface AdminPreflightGate {
  gate: string;
  severity: "blocker" | "warning" | string;
  message: string;
}

export interface AdminProductionPreflight {
  ready_for_production: boolean;
  require_postgres: boolean;
  blockers: AdminPreflightGate[];
  warnings: AdminPreflightGate[];
  summary: Record<string, unknown>;
}

export interface AdminMaintenanceGate {
  gate: string;
  severity: "blocker" | "warning" | string;
  message: string;
  [key: string]: unknown;
}

export interface AdminDatabaseMaintenanceReport {
  checked_at: string;
  ready_for_database_maintenance: boolean;
  max_age_hours: number;
  require_full: boolean;
  blockers: AdminMaintenanceGate[];
  warnings: AdminMaintenanceGate[];
  evidence: Record<string, Record<string, unknown>>;
  summary: {
    blocker_count: number;
    warning_count: number;
    required: Record<string, boolean>;
  };
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

export interface AdminAuditEvent {
  id: number;
  actor_user_id?: number | null;
  actor_name: string;
  target_user_id?: number | null;
  target_name?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  outcome: "success" | "failure" | string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AdminSecurityAuditReport {
  generated_at: string;
  available: boolean;
  message?: string;
  filters: {
    days: number;
    limit: number;
    event_type?: string | null;
    outcome?: string | null;
    user_id?: number | null;
  };
  total_events: number;
  events_by_type: Array<{
    event_type: string;
    outcome: string;
    count: number;
  }>;
  events_by_outcome: Array<{
    outcome: string;
    count: number;
  }>;
  recent_events: Array<{
    id: number;
    user_id?: number | null;
    event_type: string;
    outcome: string;
    created_at: string;
    metadata: Record<string, unknown>;
  }>;
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

  getOperations(): Observable<AdminOperationsReadiness> {
    return this.http.get<AdminOperationsReadiness>(`${this.apiUrl}/operations`, {
      headers: this.headers(),
    });
  }

  sendTestEmail(
    toAddress?: string,
  ): Observable<{ ok: boolean; message: string; to_address: string; provider: string }> {
    return this.http.post<{ ok: boolean; message: string; to_address: string; provider: string }>(
      `${this.apiUrl}/operations/test-email`,
      { to_address: toAddress || null },
      { headers: this.headers() },
    );
  }

  getProductionPreflight(requirePostgres = false): Observable<AdminProductionPreflight> {
    const query = requirePostgres ? "?require_postgres=true" : "";
    return this.http.get<AdminProductionPreflight>(`${this.apiUrl}/preflight${query}`, {
      headers: this.headers(),
    });
  }

  getDatabaseMaintenance(requireFull = false): Observable<AdminDatabaseMaintenanceReport> {
    const query = requireFull ? "?require_full=true" : "";
    return this.http.get<AdminDatabaseMaintenanceReport>(`${this.apiUrl}/maintenance${query}`, {
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

  getAuditEvents(): Observable<{ events: AdminAuditEvent[] }> {
    return this.http.get<{ events: AdminAuditEvent[] }>(`${this.apiUrl}/audit`, {
      headers: this.headers(),
    });
  }

  getSecurityAuditReport(options: {
    days?: number;
    limit?: number;
    event_type?: string;
    outcome?: string;
    user_id?: number;
  } = {}): Observable<AdminSecurityAuditReport> {
    const params = new URLSearchParams();
    if (options.days) params.set("days", String(options.days));
    if (options.limit) params.set("limit", String(options.limit));
    if (options.event_type?.trim()) params.set("event_type", options.event_type.trim());
    if (options.outcome?.trim()) params.set("outcome", options.outcome.trim());
    if (options.user_id) params.set("user_id", String(options.user_id));
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.http.get<AdminSecurityAuditReport>(`${this.apiUrl}/security${query}`, {
      headers: this.headers(),
    });
  }

  private headers(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }
}
