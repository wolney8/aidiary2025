import { pendingChangesGuard } from "./pending-changes.guard";

describe("pendingChangesGuard", () => {
  it("returns async results from the component canDeactivate contract", async () => {
    const component = {
      canDeactivate: jasmine.createSpy("canDeactivate").and.resolveTo(false),
    };

    const result = await pendingChangesGuard(component as any, {} as any, {} as any, {} as any);

    expect(result).toBeFalse();
    expect(component.canDeactivate).toHaveBeenCalled();
  });
});
