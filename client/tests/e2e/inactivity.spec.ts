import { expect, Page, test } from "@playwright/test";

const FIXED_NOW = new Date("2026-07-21T12:00:00.000Z");
const WARNING_DELAY_MS = 14 * 60 * 1000;
const WARNING_COUNTDOWN_MS = 61 * 1000;

async function openAuthenticatedEntries(page: Page): Promise<void> {
  await page.clock.install({ time: FIXED_NOW });

  await page.addInitScript(() => {
    const encode = (value: object) =>
      btoa(JSON.stringify(value))
        .replace(/=/g, "")
        .replace(/\+/g, "-")
        .replace(/\//g, "_");
    const expiresAt = Math.floor(Date.now() / 1000) + 60 * 60;
    const token = `${encode({ alg: "none", typ: "JWT" })}.${encode({ exp: expiresAt })}.e2e`;

    localStorage.setItem("ai_diary_token", token);
    localStorage.setItem(
      "ai_diary_user",
      JSON.stringify({ id: 1, username: "inactivity-e2e" }),
    );
  });

  await page.route("**/api/**", async (route) => {
    const url = route.request().url();

    if (url.includes("/public-holidays")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: false, holidays: [] }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "[]",
    });
  });

  await page.goto("/entries");
  await expect(page.getByTestId("authenticated-app-shell")).toBeVisible();
}

test("an authenticated user can remain signed in from the inactivity warning", async ({
  page,
}) => {
  await openAuthenticatedEntries(page);

  await page.clock.fastForward(WARNING_DELAY_MS);

  const warning = page.getByRole("dialog");
  await expect(
    warning.getByRole("heading", { name: "Still there?" }),
  ).toBeVisible();
  await warning.getByRole("button", { name: "Stay logged in" }).click();

  await expect(warning).toBeHidden();
  await expect(page).toHaveURL(/\/entries$/);
  await expect(page.getByTestId("authenticated-app-shell")).toBeVisible();
});

test("an authenticated user is logged out when the warning expires", async ({
  page,
}) => {
  await openAuthenticatedEntries(page);

  await page.clock.fastForward(WARNING_DELAY_MS);
  await expect(
    page.getByRole("heading", { name: "Still there?" }),
  ).toBeVisible();

  await page.clock.runFor(WARNING_COUNTDOWN_MS);

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByTestId("authenticated-app-shell")).toHaveCount(0);
  await expect(
    page.evaluate(() => localStorage.getItem("ai_diary_token")),
  ).resolves.toBeNull();
});
