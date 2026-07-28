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

async function applyWcagTextSpacing(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      * {
        line-height: 1.5 !important;
        letter-spacing: 0.12em !important;
        word-spacing: 0.16em !important;
      }

      p {
        margin-bottom: 2em !important;
      }
    `,
  });
}

async function expectNoDocumentHorizontalOverflow(page: Page): Promise<void> {
  const metrics = await page.evaluate(() => {
    const documentElement = document.documentElement;
    const body = document.body;
    return {
      bodyClientWidth: body.clientWidth,
      bodyScrollWidth: body.scrollWidth,
      documentClientWidth: documentElement.clientWidth,
      documentScrollWidth: documentElement.scrollWidth,
    };
  });

  expect(metrics.documentScrollWidth, JSON.stringify(metrics)).toBeLessThanOrEqual(
    metrics.documentClientWidth + 1,
  );
  expect(metrics.bodyScrollWidth, JSON.stringify(metrics)).toBeLessThanOrEqual(
    metrics.bodyClientWidth + 1,
  );
}

async function expectNoElementHorizontalOverflow(
  page: Page,
  testId: string,
): Promise<void> {
  const metrics = await page.getByTestId(testId).evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }));

  expect(metrics.scrollWidth, `${testId}: ${JSON.stringify(metrics)}`).toBeLessThanOrEqual(
    metrics.clientWidth + 1,
  );
}

async function expectElementWithinViewport(
  page: Page,
  testId: string,
): Promise<void> {
  const metrics = await page.getByTestId(testId).evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return {
      bottom: rect.bottom,
      right: rect.right,
      viewportHeight: window.innerHeight,
      viewportWidth: window.innerWidth,
    };
  });

  expect(metrics.bottom, `${testId}: ${JSON.stringify(metrics)}`).toBeLessThanOrEqual(
    metrics.viewportHeight + 1,
  );
  expect(metrics.right, `${testId}: ${JSON.stringify(metrics)}`).toBeLessThanOrEqual(
    metrics.viewportWidth + 1,
  );
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
  entryDetailResponses?: {
    daily?: Record<number, object>;
    dreams?: Record<number, object>;
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
    const dailyDetailMatch = path.match(/\/api\/daily\/(\d+)$/);
    if (dailyDetailMatch) {
      const response =
        entryDetailResponses?.daily?.[Number(dailyDetailMatch[1])] ?? null;

      if (response) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(response),
        });
        return;
      }
    }

    const dreamDetailMatch = path.match(/\/api\/dreams\/(\d+)$/);
    if (dreamDetailMatch) {
      const response =
        entryDetailResponses?.dreams?.[Number(dreamDetailMatch[1])] ?? null;

      if (response) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(response),
        });
        return;
      }
    }

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

async function seedNotifications(page: Page, notifications: object[]): Promise<void> {
  await page.addInitScript((seededNotifications) => {
    localStorage.setItem(
      "ai_diary_notifications",
      JSON.stringify(seededNotifications),
    );
  }, notifications);
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

  test("entry create form reflows with AI and pending attachments", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 720, height: 520 });
    await seedAuthenticatedSession(page, "dark");
    await page.goto("/entries/create");
    await expect(page.getByTestId("entry-create-form")).toBeVisible();

    await page.getByTestId("entry-pending-attachment-input").setInputFiles([
      {
        name: "context-note.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("PDF-like accessibility fixture"),
      },
      {
        name: "voice-note.m4a",
        mimeType: "audio/mp4",
        buffer: Buffer.from("audio accessibility fixture"),
      },
    ]);
    await page.getByTestId("create-respond-ai-toggle").click();
    await expect(page.getByText("context-note.pdf")).toBeVisible();
    await expect(page.getByText("voice-note.m4a")).toBeVisible();

    await applyWcagTextSpacing(page);
    await expectNoDocumentHorizontalOverflow(page);
    await expectNoElementHorizontalOverflow(page, "entry-create-form");
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

  test("notification menu in compact dark theme", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 640 });
    await seedAuthenticatedSession(page, "dark");
    await seedNotifications(page, [
      {
        id: "import-completed-e2e",
        kind: "import",
        status: "completed",
        title: "Import completed",
        message: "Import complete: 680 entries imported.",
        processed: 680,
        total: 680,
        percent: 100,
        unread: true,
        isDelayed: false,
        createdAt: "2026-07-21T10:00:00Z",
        destination: "/settings/import",
        actionLabel: "Go to import",
      },
      {
        id: "writing-reminder-e2e",
        kind: "writing_reminder",
        status: "completed",
        title: "Writing reminder",
        message: "Your chosen writing rhythm is due today.",
        processed: 0,
        total: 0,
        percent: 0,
        unread: false,
        isDelayed: false,
        createdAt: "2026-07-21T09:00:00Z",
        destination: "/entries/create",
        actionLabel: "Start entry",
      },
    ]);

    await page.goto("/entries");
    await page.getByLabel("Open notifications").click();
    const panel = page.locator(".notification-panel");
    await expect(panel).toBeVisible();
    await expect(page.getByText("Import completed")).toBeVisible();
    await expect(page.getByText("Writing reminder")).toBeVisible();
    await expect
      .poll(() =>
        panel.evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
      )
      .toBe(true);

    await expectNoWcagViolations(page);
  });

  test("overlay surfaces reflow with WCAG text spacing", async ({ page }) => {
    await page.setViewportSize({ width: 720, height: 520 });

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
    const previewImage =
      "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'%3E%3Crect width='320' height='180' rx='20' fill='%239bb8ff'/%3E%3Cpath d='M0 130C70 100 105 152 168 116C228 82 254 58 320 88V180H0Z' fill='%23182742' opacity='.52'/%3E%3C/svg%3E";

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
          label: "A meaningful date with a longer label",
          starts_on: todayKey,
          month: today.getMonth() + 1,
          day: today.getDate(),
          original_year: today.getFullYear(),
          category: "other",
          recurrence: "yearly",
          icon_name: "event",
          accent_color: "amber",
          note: "A short private note with enough copy to exercise wrapping.",
          image_url: previewImage,
          linked_entries: [],
        },
      ],
      {
        thoughtRecords: [
          {
            id: 14,
            worksheet_type: "thought_record",
            title: "Reframing a difficult meeting",
            status: "completed",
            current_step: 7,
            record_date: todayKey,
            situation: "A tense meeting left me second guessing myself.",
            balanced_thought: "One awkward answer does not mean the whole meeting failed.",
            feelings_before: [],
            feelings_after: [],
          },
        ],
      },
    );
    await seedNotifications(page, [
      {
        id: "import-completed-text-spacing",
        kind: "import",
        status: "completed",
        title: "Import completed",
        message:
          "Import complete: 680 entries imported with a longer status message for wrapping.",
        processed: 680,
        total: 680,
        percent: 100,
        unread: true,
        isDelayed: false,
        createdAt: "2026-07-21T10:00:00Z",
        destination: "/settings/import",
        actionLabel: "Go to import",
      },
    ]);

    await page.goto(
      "/entries?display=cards&show=daily,dreams,thought-records,important-days,on-this-day",
    );
    await applyWcagTextSpacing(page);
    await expectNoDocumentHorizontalOverflow(page);

    await page.getByLabel("Open notifications").click();
    await expect(page.getByTestId("notifications-panel")).toBeVisible();
    await expectNoElementHorizontalOverflow(page, "notifications-panel");
    await page.getByLabel("Close notifications").click();

    await page.getByTestId("calendar-important-days-summary-trigger").click();
    await expect(page.getByTestId("cards-important-day-preview")).toBeVisible();
    await expectNoElementHorizontalOverflow(page, "cards-important-day-preview");
    await page.getByLabel("View image for A meaningful date with a longer label").click();
    await expect(page.getByTestId("important-day-image-modal")).toBeVisible();
    await expect(page.getByLabel("Close important day image")).toBeVisible();
    await page.getByLabel("Close important day image").click();

    await page.getByTestId("calendar-thought-records-summary-trigger").click();
    await expect(page.getByTestId("cards-important-day-preview")).toBeHidden();
    await expect(page.getByTestId("cards-thought-record-preview")).toBeVisible();
    await expectNoElementHorizontalOverflow(page, "cards-thought-record-preview");

    await page.getByTestId("calendar-on-this-day-month-summary-trigger").click();
    await expect(page.getByTestId("cards-thought-record-preview")).toBeHidden();
    await expect(page.getByTestId("cards-on-this-day-preview")).toBeVisible();
    await expectNoElementHorizontalOverflow(page, "cards-on-this-day-preview");

    await expectNoDocumentHorizontalOverflow(page);
    await expectNoWcagViolations(page);
  });

  test("import review modal reflows with WCAG text spacing", async ({ page }) => {
    await page.setViewportSize({ width: 720, height: 520 });
    await seedAuthenticatedSession(page, "dark");
    await page.route("**/api/import/upload", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "review",
          message: "Review entries before import.",
          imported_count: 0,
          skipped_count: 0,
          error_count: 0,
          import_session_id: "review-session-e2e",
          summary: {
            ready_daily: 2,
            ready_dreams: 0,
            duplicate_daily: 1,
            duplicate_dreams: 0,
          },
          review_entries: [
            {
              row_id: "row-1",
              entry_type: "daily",
              entry_date: "2026-07-21",
              title: "A longer imported entry title",
              content_preview:
                "A longer imported entry preview that needs to wrap without pushing the modal outside the viewport.",
              mood: "good",
              is_duplicate: false,
              attachment_count: 0,
              source_record_kind: "authored",
            },
            {
              row_id: "row-2",
              entry_type: "daily",
              entry_date: "2026-07-22",
              title: "Potential duplicate",
              content_preview: "A duplicate candidate preview.",
              mood: "meh",
              is_duplicate: true,
              attachment_count: 0,
              source_record_kind: "authored",
            },
          ],
        }),
      });
    });

    await page.goto("/settings/import");
    await page.locator('input[type="file"]').setInputFiles({
      name: "accessibility-import.xlsx",
      mimeType:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      buffer: Buffer.from("mock workbook"),
    });
    await page.getByLabel("Upload selected file and import entries").click();
    await expect(page.getByTestId("import-review-open")).toBeVisible();

    await applyWcagTextSpacing(page);
    await page.getByTestId("import-review-open").click();
    await expect(page.getByTestId("import-review-modal")).toBeVisible();
    await expectNoDocumentHorizontalOverflow(page);
    await expectNoElementHorizontalOverflow(page, "import-review-modal");
    await expectNoWcagViolations(page);
  });

  test("attachment derived text dialog reflows at short viewport", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 720, height: 520 });
    await seedAuthenticatedSession(
      page,
      "dark",
      undefined,
      undefined,
      undefined,
      undefined,
      undefined,
      {
        daily: {
          91: {
            id: 91,
            entry_date: "2026-07-21",
            entry_time: "19:00",
            title: "Entry with a long attachment transcript",
            user_message: "This entry has a saved PDF-derived text attachment.",
            ai_response: "A short response.",
            tags: "accessibility",
            daily_people_names: "",
            daily_places: "",
            attachments: [
              {
                id: 33,
                asset_role: "attachment",
                original_filename: "long-derived-text.pdf",
                mime_type: "application/pdf",
                file_size_bytes: 12000,
                sort_order: 0,
                created_at: "2026-07-21T10:00:00Z",
                derived_text: Array.from({ length: 24 }, (_, index) =>
                  `Derived paragraph ${index + 1} with enough words to exercise wrapping and the scrollable app dialog content area.`,
                ).join("\n\n"),
                derived_text_source: "pdf-openai",
                derived_text_updated_at: "2026-07-21T10:05:00Z",
                has_derived_text: true,
                url: "https://example.test/long-derived-text.pdf",
                is_image: false,
                is_audio: false,
                is_pdf: true,
              },
            ],
          },
        },
      },
    );

    await page.goto("/entries/91?entryType=daily&showAttachments=1");
    await expect(
      page.getByText("Entry with a long attachment transcript"),
    ).toBeVisible();

    await applyWcagTextSpacing(page);
    await page.getByTestId("entry-attachment-derived-text-toggle-33").click();
    await expect(page.getByTestId("app-dialog")).toBeVisible();
    await expectElementWithinViewport(page, "app-dialog");
    await expectNoElementHorizontalOverflow(page, "app-dialog");
    await expectNoDocumentHorizontalOverflow(page);
    await expectNoWcagViolations(page);
  });

  test("compact shell and monthly preview controls work from keyboard", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 700 });

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
      {
        query: "focus",
        filters: [],
        filters_display: "All Entries",
        results: [],
      },
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
          starts_on: todayKey,
          month: today.getMonth() + 1,
          day: today.getDate(),
          original_year: today.getFullYear(),
          category: "other",
          recurrence: "yearly",
          icon_name: "event",
          accent_color: "amber",
          note: "A short private note.",
          linked_entries: [],
        },
      ],
      {
        thoughtRecords: [
          {
            id: 14,
            worksheet_type: "thought_record",
            title: "Reframing a difficult meeting",
            status: "completed",
            current_step: 7,
            record_date: todayKey,
            situation: "A tense meeting left me second guessing myself.",
            balanced_thought: "One awkward answer does not mean the whole meeting failed.",
            feelings_before: [],
            feelings_after: [],
          },
        ],
      },
    );
    await seedNotifications(page, [
      {
        id: "import-completed-keyboard",
        kind: "import",
        status: "completed",
        title: "Import completed",
        message: "Import complete: 680 entries imported.",
        processed: 680,
        total: 680,
        percent: 100,
        unread: true,
        isDelayed: false,
        createdAt: "2026-07-21T10:00:00Z",
        destination: "/settings/import",
        actionLabel: "Go to import",
      },
    ]);

    await page.goto(
      "/entries?display=cards&show=daily,dreams,thought-records,important-days,on-this-day",
    );

    await page.getByLabel("Open search").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByLabel("Search entries, tags, people, and dates")).toBeFocused();
    await page.keyboard.type("focus");
    await page.keyboard.press("Enter");
    await expect
      .poll(() => new URL(page.url()).searchParams.get("search"))
      .toBe("focus");

    await page.goto(
      "/entries?display=cards&show=daily,dreams,thought-records,important-days,on-this-day",
    );

    await page.getByLabel("Open notifications").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("notifications-panel")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("notifications-panel")).toBeHidden();

    await page.getByTestId("calendar-important-days-summary-trigger").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("cards-important-day-preview")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("cards-important-day-preview")).toBeHidden();

    await page.getByTestId("calendar-thought-records-summary-trigger").focus();
    await page.keyboard.press(" ");
    await expect(page.getByTestId("cards-thought-record-preview")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("cards-thought-record-preview")).toBeHidden();

    await page.getByTestId("calendar-on-this-day-month-summary-trigger").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("cards-on-this-day-preview")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("cards-on-this-day-preview")).toBeHidden();

    await expectNoWcagViolations(page);
  });
});
