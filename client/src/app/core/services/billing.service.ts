import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { Observable } from "rxjs";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";

export type BillingTier = "free" | "personal" | "plus" | "therapeutic" | "lifetime" | "complimentary" | "administrator";
export type CheckoutTier = "personal" | "plus";

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
  has_billing_customer: boolean;
}

export interface BillingSessionResponse {
  url: string;
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

  startCheckout(tier: CheckoutTier): Observable<BillingSessionResponse> {
    this.ensureAuthenticated();
    return this.http.post<BillingSessionResponse>(
      `${this.apiUrl}/checkout-session`,
      { tier },
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
