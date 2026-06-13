import { CanDeactivateFn } from "@angular/router";
import { Observable } from "rxjs";

type PendingChangesComponent = {
  canDeactivate: () => boolean | Promise<boolean> | Observable<boolean>;
};

export const pendingChangesGuard: CanDeactivateFn<PendingChangesComponent> = (component) => {
  return component.canDeactivate();
};
