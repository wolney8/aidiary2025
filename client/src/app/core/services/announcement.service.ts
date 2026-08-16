import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { BehaviorSubject, Observable, finalize, of, shareReplay, tap } from "rxjs";
import { environment } from "../../../environments/environment";
import { AuthService } from "./auth.service";
import {
  AdminAnnouncementPlacement,
  AdminAnnouncementSeverity,
  AdminAnnouncementTarget,
} from "./admin.service";

export interface PlatformAnnouncement {
  id: number;
  title: string;
  message: string;
  severity: AdminAnnouncementSeverity;
  placement: AdminAnnouncementPlacement;
  dismissible: boolean;
  unread: boolean;
  targets: AdminAnnouncementTarget[];
  starts_at?: string | null;
  ends_at?: string | null;
}

@Injectable({ providedIn: "root" })
export class AnnouncementService {
  private readonly http = inject(HttpClient);
  private readonly authService = inject(AuthService);
  private readonly apiUrl = `${environment.apiBaseUrl}/announcements`;
  private readonly announcementsSubject = new BehaviorSubject<PlatformAnnouncement[]>([]);
  private refreshRequest$?: Observable<{ announcements: PlatformAnnouncement[] }>;
  private refreshUserKey?: string;
  private refreshedAt = 0;
  private readonly refreshCacheMs = 30_000;

  readonly announcements$ = this.announcementsSubject.asObservable();

  refresh(force = false): Observable<{ announcements: PlatformAnnouncement[] }> {
    const now = Date.now();
    const userKey = this.getRefreshUserKey();
    if (this.refreshUserKey !== userKey) {
      this.clear();
      this.refreshUserKey = userKey;
    }
    if (
      !force &&
      this.announcementsSubject.value.length > 0 &&
      now - this.refreshedAt < this.refreshCacheMs
    ) {
      return of({ announcements: this.announcementsSubject.value });
    }
    if (!force && this.refreshRequest$) {
      return this.refreshRequest$;
    }
    this.refreshRequest$ = this.http
      .get<{ announcements: PlatformAnnouncement[] }>(`${this.apiUrl}/active`, {
        headers: this.headers(),
      })
      .pipe(
        tap((response) => {
          this.refreshedAt = Date.now();
          this.announcementsSubject.next(response.announcements || []);
        }),
        finalize(() => {
          this.refreshRequest$ = undefined;
        }),
        shareReplay({ bufferSize: 1, refCount: true }),
      );
    return this.refreshRequest$;
  }

  markRead(announcementId: number): Observable<{ ok: boolean }> {
    this.announcementsSubject.next(
      this.announcementsSubject.value.map((announcement) =>
        announcement.id === announcementId
          ? { ...announcement, unread: false }
          : announcement,
      ),
    );
    return this.http.post<{ ok: boolean }>(
      `${this.apiUrl}/${announcementId}/read`,
      {},
      { headers: this.headers() },
    );
  }

  dismiss(announcementId: number): Observable<{ ok: boolean }> {
    this.announcementsSubject.next(
      this.announcementsSubject.value.filter(
        (announcement) => announcement.id !== announcementId,
      ),
    );
    return this.http.post<{ ok: boolean }>(
      `${this.apiUrl}/${announcementId}/dismiss`,
      {},
      { headers: this.headers() },
    );
  }

  clear(): void {
    this.announcementsSubject.next([]);
    this.refreshedAt = 0;
    this.refreshRequest$ = undefined;
  }

  private getRefreshUserKey(): string {
    const userId = this.authService.getCurrentUser()?.id ?? "anonymous";
    return `${userId}:${this.authService.getToken() ?? "cookie"}`;
  }

  private headers(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }
}
