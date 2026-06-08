import { CanDeactivateFn } from '@angular/router';

type PendingChangesComponent = {
  canDeactivate: () => boolean;
};

export const pendingChangesGuard: CanDeactivateFn<PendingChangesComponent> = (component) => {
  return component.canDeactivate();
};
