import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable } from "rxjs";
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
    ai_analysis: {
      used: number;
      limit: number | null;
      remaining: number | null;
      unlimited: boolean;
    };
  };
  plans: BillingPlan[];
  is_admin?: boolean;
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

@Injectable({ providedIn: "root" })
export class BillingService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/billing`;

  getStatus(): Observable<BillingStatus> {
    this.ensureAuthenticated();
    return this.http.get<BillingStatus>(`${this.apiUrl}/status`, {
      headers: this.buildHeaders(),
    });
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
    );
  }

  private ensureAuthenticated(): void {
    if (!this.authService.isAuthenticated()) {
      throw new Error("User not authenticated");
    }
  }

  private buildHeaders(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }
}
