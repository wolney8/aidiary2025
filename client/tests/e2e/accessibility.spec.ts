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
  onThisDayResponse?: object,
  importantDaysResponse?: object[],
  calendarResponses?: {
    daily?: object[];
    dreams?: object[];
    thoughtRecords?: object[];
  },
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
    localStorage.setItem("ai_diary_theme_mode", selectedTheme);
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

    if (url.includes("/on-this-day")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          onThisDayResponse ?? { enabled: false, date: "2026-07-21", entries: [] },
        ),
      });
      return;
    }

    if (url.includes("/important-days")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(importantDaysResponse ?? []),
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

    const path = new URL(url).pathname;
    if (path.endsWith("/api/daily")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(calendarResponses?.daily ?? []),
      });
      return;
    }
    if (path.endsWith("/api/dreams")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(calendarResponses?.dreams ?? []),
      });
      return;
    }
    if (path.endsWith("/api/cbt/worksheets")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(calendarResponses?.thoughtRecords ?? []),
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

  test("entry display and content filters preserve URL state", async ({ page }) => {
    await seedAuthenticatedSession(page, "dark", undefined, {
      enabled: true,
      date: "2026-07-21",
      entries: [],
    });
    await page.goto("/entries?display=cards&show=daily,dreams");

    await expect(page.getByTestId("entries-display-cards")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(
      page.getByTestId("entries-filter-daily").locator('[role="option"]'),
    ).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await expect(
      page.getByTestId("entries-filter-dreams").locator('[role="option"]'),
    ).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.getByTestId("entries-filter-dreams").click();
    await expect
      .poll(() => new URL(page.url()).searchParams.get("show"))
      .toBe("daily");

    await page.getByTestId("entries-display-calendar").click();
    await expect
      .poll(() => new URL(page.url()).searchParams.get("display"))
      .toBe("calendar");
    await page.reload();
    await expect(page.getByTestId("entries-display-calendar")).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(
      page.getByTestId("entries-filter-daily").locator('[role="option"]'),
    ).toHaveAttribute(
      "aria-selected",
      "true",
    );

    await page.getByTestId("entries-filter-daily").click();
    await expect
      .poll(() => new URL(page.url()).searchParams.get("show"))
      .toBe("");
    await page.getByTestId("entries-display-cards").click();
    await expect(
      page.getByRole("heading", { name: "No content selected" }),
    ).toBeVisible();
    await expectNoWcagViolations(page);
  });

  test("On this day filter is disabled when Customisation has it off", async ({
    page,
  }) => {
    await seedAuthenticatedSession(page);
    await page.goto("/entries");
    await expect(page.getByTestId("entries-filter-on-this-day")).toBeDisabled();
  });

  test("entry creation", async ({ page }) => {
    await seedAuthenticatedSession(page);
    await page.goto("/entries/create");
    await expect(
      page.getByRole("heading", { name: "New Daily Entry" }),
    ).toBeVisible();

    await expectNoWcagViolations(page);

    await page.getByTestId("entry-type-important-day").click();
    await expect(
      page.getByRole("heading", { name: "New Important Day Entry" }),
    ).toBeVisible();
    await expect(page.getByTestId("embedded-important-day-form")).toBeVisible();
    await expectNoWcagViolations(page);

    await page.getByTestId("entry-type-thought-record").click();
    await expect(
      page.getByRole("heading", { name: "New Thought Record Entry" }),
    ).toBeVisible();
    await expect(page.getByTestId("embedded-thought-record-form")).toBeVisible();
    await expectNoWcagViolations(page);
  });

  test("On this day preview in dark theme", async ({ page }) => {
    await seedAuthenticatedSession(
      page,
      "dark",
      undefined,
      {
        enabled: true,
        date: "2026-07-21",
        entries: [
          {
            id: 7,
            type: "daily",
            entry_date: "2025-07-21",
            title: "A calmer afternoon",
            preview: "I noticed that taking a slower route home helped.",
            tags: ["reflection"],
            image_url: null,
            image_source: null,
            attachment_count: 0,
          },
        ],
      },
      [
        {
          id: 4,
          label: "A meaningful date",
          starts_on: "2025-07-21",
          month: 7,
          day: 21,
          original_year: 2025,
          category: "other",
          recurrence: "yearly",
          icon_name: "event",
          accent_color: "amber",
          note: "A short private note.",
          linked_entries: [],
        },
      ],
      {
        daily: [
          {
            id: 1,
            entry_date: "2026-07-21",
            entry_time: "19:00",
            title: "Today in focus",
            message: "A short daily entry.",
            tags: [],
            people_names: [],
            places: [],
          },
        ],
        dreams: [
          {
            id: 2,
            entry_date: "2026-07-21",
            entry_time: "08:00",
            title: "A recent dream",
            plot: "A short dream entry.",
            tags: [],
            people_names: [],
            places: [],
          },
        ],
        thoughtRecords: [
          {
            id: 3,
            worksheet_type: "thought_record",
            title: "A balanced thought",
            status: "completed",
            current_step: 7,
            record_date: "2026-07-21",
            situation: "A short situation.",
            balanced_thought: "A more balanced response.",
            feelings_before: [],
            feelings_after: [],
          },
        ],
      },
    );
    await page.goto(
      "/entries?display=cards&show=daily,dreams,thought-records,important-days,on-this-day",
    );
    await page.getByTestId("calendar-on-this-day-month-summary-trigger").click();
    await expect(page.getByTestId("cards-on-this-day-preview")).toBeVisible();
    await page.getByTestId("calendar-important-days-summary-trigger").click();
    await expect(page.getByTestId("cards-on-this-day-preview")).toBeHidden();
    await expect(page.getByTestId("cards-important-day-preview")).toBeVisible();

    await page.goto("/entries?display=calendar");
    const showMoreButton = page.getByRole("button", {
      name: /Show more items for/,
    });
    await expect(showMoreButton).toBeVisible();
    await showMoreButton.click();
    await page.getByTestId("calendar-on-this-day-marker").click();
    await expect(page.getByTestId("on-this-day-preview")).toBeVisible();

    await page.getByTestId("calendar-important-days-summary-trigger").click();
    await expect(page.getByTestId("on-this-day-preview")).toBeHidden();
    await expect(page.getByTestId("calendar-important-day-preview")).toBeVisible();

    await expectNoWcagViolations(page);

    await page.mouse.wheel(0, 500);
    await expect(page.getByTestId("calendar-important-day-preview")).toBeHidden();
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
