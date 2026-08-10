import { HttpClient, HttpHeaders } from "@angular/common/http";
import { Injectable, inject } from "@angular/core";
import { BehaviorSubject, Observable, tap } from "rxjs";
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

  readonly announcements$ = this.announcementsSubject.asObservable();

  refresh(): Observable<{ announcements: PlatformAnnouncement[] }> {
    return this.http
      .get<{ announcements: PlatformAnnouncement[] }>(`${this.apiUrl}/active`, {
        headers: this.headers(),
      })
      .pipe(
        tap((response) => {
          this.announcementsSubject.next(response.announcements || []);
        }),
      );
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
  }

  private headers(): HttpHeaders {
    const token = this.authService.getToken();
    return new HttpHeaders({
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    });
  }
}
