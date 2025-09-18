import { CanDeactivateFn } from '@angular/router';
import { CreateComponent } from './create/create.component';

export const pendingChangesGuard: CanDeactivateFn<CreateComponent> = (component) => {
  return component.canDeactivate();
};
