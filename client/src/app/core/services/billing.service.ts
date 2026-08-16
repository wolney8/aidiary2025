import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable, shareReplay, tap } from "rxjs";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";

export type BillingTier = "free" | "personal" | "plus" | "therapeutic" | "lifetime" | "complimentary" | "administrator";
export type CheckoutTier = "personal" | "plus";
export type BillingPeriod = "monthly" | "annual";

export interface BillingPlan {
  tier: BillingTier;
  public_name: string;
  strapline: string;
  description: string;
  monthly_price_gbp_pence: number;
  annual_price_gbp_pence: number;
  annual_discount_percent: number;
  quotas: Record<string, number | null>;
  features: string[];
  gated_features: string[];
  is_paid: boolean;
  is_public: boolean;
  sort_order: number;
  catalogue_version: number;
  updated_at?: string | null;
}

export interface BillingEntitlement {
  tier: BillingTier;
  source: string;
  status: string;
  valid_until?: string | null;
  is_default?: boolean;
  is_active?: boolean;
  stored_tier?: BillingTier;
  stored_status?: string;
  stored_source?: string;
}

export interface BillingStatus {
  entitlement: BillingEntitlement;
  provider: "stripe";
  stripe_configured: boolean;
  checkout_tiers: CheckoutTier[];
  checkout_periods?: Partial<Record<CheckoutTier, BillingPeriod[]>>;
  has_billing_customer: boolean;
  current_subscription?: {
    provider: "stripe";
    provider_subscription_id?: string | null;
    tier: BillingTier;
    status: string;
    billing_period?: BillingPeriod | null;
    current_period_start?: string | null;
    current_period_end?: string | null;
    cancel_at_period_end?: boolean;
  } | null;
  usage?: {
    plan: BillingTier;
    window: "month";
    window_start: string;
    ai_analysis: BillingUsageMetric;
    ai_image?: BillingUsageMetric;
    ocr_page?: BillingUsageMetric;
    transcription_minute?: BillingUsageMetric;
  };
  plans: BillingPlan[];
  is_admin?: boolean;
}

export interface BillingUsageMetric {
  used: number;
  limit: number | null;
  remaining: number | null;
  unlimited: boolean;
}

export interface BillingSessionResponse {
  url: string;
}

export interface BillingPlansResponse {
  plans: BillingPlan[];
  is_admin?: boolean;
  stripe_configured?: boolean;
  checkout_tiers?: CheckoutTier[];
  checkout_periods?: Partial<Record<CheckoutTier, BillingPeriod[]>>;
}

export interface AdminBillingPlansResponse {
  plans: BillingPlan[];
}

export interface AdminBillingUser {
  id: number;
  username: string;
  email?: string;
  display_name?: string;
  first_name?: string;
  last_name?: string;
  registered_at?: string | null;
  entitlement: BillingEntitlement;
}

export interface AdminBillingUsersResponse {
  users: AdminBillingUser[];
}

@Injectable({ providedIn: "root" })
export class BillingService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/billing`;
  private statusRequest$?: Observable<BillingStatus>;
  private statusRequestKey?: string;

  getStatus(): Observable<BillingStatus> {
    this.ensureAuthenticated();
    const cacheKey = this.getStatusCacheKey();
    if (this.statusRequest$ && this.statusRequestKey === cacheKey) {
      return this.statusRequest$;
    }
    this.statusRequestKey = cacheKey;
    this.statusRequest$ = this.http
      .get<BillingStatus>(`${this.apiUrl}/status`, {
        headers: this.buildHeaders(),
      })
      .pipe(
        shareReplay({ bufferSize: 1, refCount: true }),
      );
    return this.statusRequest$;
  }

  startCheckout(
    tier: CheckoutTier,
    billingPeriod: BillingPeriod = "monthly",
  ): Observable<BillingSessionResponse> {
    this.ensureAuthenticated();
    return this.http.post<BillingSessionResponse>(
      `${this.apiUrl}/checkout-session`,
      { tier, billing_period: billingPeriod },
      { headers: this.buildHeaders() },
    );
  }

  openCustomerPortal(): Observable<BillingSessionResponse> {
    this.ensureAuthenticated();
    return this.http.post<BillingSessionResponse>(
      `${this.apiUrl}/customer-portal-session`,
      {},
      { headers: this.buildHeaders() },
    );
  }

  getPlans(includeInternal = false): Observable<BillingPlansResponse> {
    this.ensureAuthenticated();
    return this.http.get<BillingPlansResponse>(
      `${this.apiUrl}/plans${includeInternal ? "?include_internal=1" : ""}`,
      { headers: this.buildHeaders() },
    );
  }

  getAdminPlans(): Observable<AdminBillingPlansResponse> {
    this.ensureAuthenticated();
    return this.http.get<AdminBillingPlansResponse>(
      `${this.apiUrl}/admin/plans`,
      { headers: this.buildHeaders() },
    );
  }

  updateAdminPlan(
    tier: BillingTier,
    payload: Partial<BillingPlan>,
  ): Observable<{ plan: BillingPlan }> {
    this.ensureAuthenticated();
    return this.http.put<{ plan: BillingPlan }>(
      `${this.apiUrl}/admin/plans/${tier}`,
      payload,
      { headers: this.buildHeaders() },
    ).pipe(tap(() => this.clearStatusCache()));
  }

  getAdminUsers(search = ""): Observable<AdminBillingUsersResponse> {
    this.ensureAuthenticated();
    const query = search.trim()
      ? `?search=${encodeURIComponent(search.trim())}`
      : "";
    return this.http.get<AdminBillingUsersResponse>(
      `${this.apiUrl}/admin/users${query}`,
      { headers: this.buildHeaders() },
    );
  }

  updateAdminUserEntitlement(
    userId: number,
    payload: {
      tier: BillingTier;
      status: string;
      valid_until?: string | null;
    },
  ): Observable<{ user: AdminBillingUser }> {
    this.ensureAuthenticated();
    return this.http.put<{ user: AdminBillingUser }>(
      `${this.apiUrl}/admin/users/${userId}/entitlement`,
      payload,
      { headers: this.buildHeaders() },
    ).pipe(tap(() => this.clearStatusCache()));
  }

  clearStatusCache(): void {
    this.statusRequest$ = undefined;
    this.statusRequestKey = undefined;
  }

  private ensureAuthenticated(): void {
    if (!this.authService.isAuthenticated()) {
      throw new Error("User not authenticated");
    }
  }

  private getStatusCacheKey(): string {
    const userId = this.authService.getCurrentUser()?.id ?? "anonymous";
    return `${userId}:${this.authService.getToken() ?? "cookie"}`;
  }

  private buildHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }
}
