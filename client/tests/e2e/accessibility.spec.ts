import AxeBuilder from "@axe-core/playwright";
import { expect, Page, test } from "@playwright/test";

const WCAG_TAGS = [
  "wcag2a",
  "wcag2aa",
  "wcag21a",
  "wcag21aa",
  "wcag22aa",
];

async function expectNoWcagViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(WCAG_TAGS)
    // Angular CDK manages these hidden focus-trap sentinels programmatically.
    .exclude(".cdk-focus-trap-anchor")
    .analyze();
  const summary = results.violations
    .map(
      (violation) =>
        `${violation.id}: ${violation.help} (${violation.nodes.length} node(s))`,
    )
    .join("\n");

  expect(results.violations, summary).toEqual([]);
}

async function seedAuthenticatedSession(
  page: Page,
  theme: "light" | "dark" = "light",
  searchResponse?: object,
): Promise<void> {
  await page.addInitScript((selectedTheme) => {
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
      JSON.stringify({ id: 1, username: "accessibility-e2e" }),
    );
    localStorage.setItem("ai_diary_theme", selectedTheme);
  }, theme);

  await page.route("**/api/**", async (route) => {
    const url = route.request().url();

    if (url.includes("/search") && searchResponse) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(searchResponse),
      });
      return;
    }

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
}

test.describe("WCAG 2.2 AA automated checks", () => {
  test("login", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: "Login to AI Diary" })).toBeVisible();

    await expectNoWcagViolations(page);
  });

  test("registration", async ({ page }) => {
    await page.goto("/register");
    await expect(page.getByRole("heading", { name: "Create Account" })).toBeVisible();

    await expectNoWcagViolations(page);
  });

  for (const theme of ["light", "dark"] as const) {
    test(`entries in ${theme} theme`, async ({ page }) => {
      await seedAuthenticatedSession(page, theme);
      await page.goto("/entries");
      await expect(page.getByTestId("authenticated-app-shell")).toBeVisible();

      await expectNoWcagViolations(page);
    });
  }

  test("entry creation", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.goto("/entries/create");
    await expect(
      page.getByRole("heading", { name: "New Diary Entry" }),
    ).toBeVisible();

    await expectNoWcagViolations(page);
  });

  test("populated search results", async ({ page }) => {
    await seedAuthenticatedSession(page, "dark", {
      query: "focus",
      filters: [],
      filters_display: "All Entries",
      results: [
        {
          id: 42,
          type: "daily",
          title: "A focused afternoon",
          title_highlight: "A <mark>focused</mark> afternoon",
          entry_date: "2026-07-20",
          entry_date_display: "Monday, 20th July 2026",
          tags: "focus, work",
          matches: { body: "I found a quiet way to focus." },
        },
      ],
    });
    await page.goto("/entries?search=focus");
    await expect(
      page.getByRole("heading", { name: /1 result/i }),
    ).toBeVisible();

    await expectNoWcagViolations(page);
  });

  for (const route of ["/settings/import", "/settings/important-days"] as const) {
    test(`${route} in dark theme`, async ({ page }) => {
      await seedAuthenticatedSession(page, "dark");
      await page.goto(route);
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

      await expectNoWcagViolations(page);
    });
  }
});
