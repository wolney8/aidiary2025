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
  reflectionSummariesResponse?: object[],
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
    if (path.endsWith("/api/reflection-summaries")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(reflectionSummariesResponse ?? []),
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
    const toDateKey = (date: Date) => {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    };
    const today = new Date();
    const todayKey = toDateKey(today);
    const previousYearKey = toDateKey(
      new Date(today.getFullYear() - 1, today.getMonth(), today.getDate()),
    );

    await seedAuthenticatedSession(
      page,
      "dark",
      undefined,
      {
        enabled: true,
        date: todayKey,
        entries: [
          {
            id: 7,
            type: "daily",
            entry_date: previousYearKey,
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
          starts_on: previousYearKey,
          month: today.getMonth() + 1,
          day: today.getDate(),
          original_year: today.getFullYear() - 1,
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
            entry_date: todayKey,
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
            entry_date: todayKey,
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
            record_date: todayKey,
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
    const onThisDayFilter = page
      .getByTestId("entries-filter-on-this-day")
      .locator('[role="option"]');
    if ((await onThisDayFilter.getAttribute("aria-selected")) !== "true") {
      await page.getByTestId("entries-filter-on-this-day").click();
    }
    await expect(onThisDayFilter).toHaveAttribute("aria-selected", "true");
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

  for (const route of ["/settings/import", "/settings/personalisation"] as const) {
    test(`${route} in dark theme`, async ({ page }) => {
      await seedAuthenticatedSession(page, "dark");
      await page.goto(route);
      await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();

      await expectNoWcagViolations(page);
    });
  }

  test("important days in dark theme", async ({ page }) => {
    await seedAuthenticatedSession(page, "dark");
    await page.goto("/important-days");
    await expect(
      page.getByRole("heading", { name: "Important days" }),
    ).toBeVisible();

    await expectNoWcagViolations(page);
  });

  test("thought records dashboard in dark theme", async ({ page }) => {
    await seedAuthenticatedSession(
      page,
      "dark",
      undefined,
      undefined,
      undefined,
      {
        thoughtRecords: [
          {
            id: 14,
            worksheet_type: "thought_record",
            title: "Reframing a difficult meeting",
            status: "completed",
            current_step: 7,
            record_date: "2026-07-18",
            linked_entry_type: null,
            linked_entry_id: null,
            situation: "A tense meeting left me second guessing myself.",
            feelings_before: [{ label: "anxious", intensity: 75 }],
            unhelpful_thoughts: "I probably handled everything badly.",
            evidence_for: "I stumbled on one answer.",
            evidence_against: "I stayed calm and followed up clearly.",
            balanced_thought: "One awkward answer does not mean the whole meeting failed.",
            feelings_after: [{ label: "anxious", intensity: 38 }],
            next_step: "Send a short follow-up note.",
            ai_response: "This is a more balanced reading of the situation.",
            ai_responded_at: "2026-07-18T10:00:00Z",
            ai_response_outdated: false,
            before_peak_intensity: 75,
            after_peak_intensity: 38,
            intensity_change: -37,
            created_at: "2026-07-18T09:00:00Z",
            updated_at: "2026-07-18T10:00:00Z",
            completed_at: "2026-07-18T10:00:00Z",
          },
          {
            id: 15,
            worksheet_type: "thought_record",
            title: "Draft reflection",
            status: "draft",
            current_step: 3,
            record_date: "2026-07-21",
            linked_entry_type: null,
            linked_entry_id: null,
            situation: "I noticed a familiar worry starting again.",
            feelings_before: [{ label: "worried", intensity: 62 }],
            unhelpful_thoughts: "This will spiral.",
            evidence_for: "",
            evidence_against: "",
            balanced_thought: "",
            feelings_after: [],
            next_step: "",
            ai_response: "",
            ai_responded_at: null,
            ai_response_outdated: false,
            before_peak_intensity: null,
            after_peak_intensity: null,
            intensity_change: null,
            created_at: "2026-07-21T08:00:00Z",
            updated_at: "2026-07-21T08:30:00Z",
            completed_at: null,
          },
        ],
      },
    );
    await page.goto("/cbt");
    await expect(page.getByTestId("cbt-dashboard")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Reflection overview" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Completed reflections" }),
    ).toBeVisible();

    await expectNoWcagViolations(page);
  });

  test("reflection summaries in dark theme", async ({ page }) => {
    await seedAuthenticatedSession(
      page,
      "dark",
      undefined,
      undefined,
      undefined,
      undefined,
      [
        {
          id: 5,
          period_type: "monthly",
          period_start: "2026-07-01",
          period_end: "2026-07-31",
          title: "July reflection",
          summary_text:
            "This month shows a repeated pattern of pausing before responding and using structured reflection to recover perspective.",
          themes: ["reflection", "boundaries", "recovery"],
          source_refs: [
            {
              type: "daily",
              id: 12,
              date: "2026-07-11",
              theme: "a calmer evening",
            },
            {
              type: "thought_record",
              id: 14,
              date: "2026-07-18",
              theme: "reframing a difficult meeting",
            },
          ],
          model: "gpt-4o-mini",
          created_at: "2026-07-21T10:00:00Z",
          updated_at: "2026-07-21T10:00:00Z",
        },
      ],
    );
    await page.goto("/reflections");
    await expect(page.getByTestId("reflection-summaries")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Generated reflections" }),
    ).toBeVisible();
    await expect(page.getByText("July reflection")).toBeVisible();

    await expectNoWcagViolations(page);
  });
});
