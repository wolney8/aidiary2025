import type { HttpInterceptorFn } from "@angular/common/http";
import { inject } from "@angular/core";
import { finalize } from "rxjs";
import { LoadingService } from "../services/loading.service";
import { environment } from "../../../environments/environment";

export const loadingInterceptor: HttpInterceptorFn = (req, next) => {
  const isApiRequest =
    req.url.startsWith(environment.apiBaseUrl) ||
    req.url.startsWith(environment.apiFallbackBaseUrl) ||
    req.url.startsWith("/api/");

  if (!isApiRequest) {
    return next(req);
  }

  const loadingService = inject(LoadingService);
  loadingService.start();

  return next(req).pipe(finalize(() => loadingService.stop()));
};
