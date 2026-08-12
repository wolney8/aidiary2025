import { expect, Page, test } from "@playwright/test";

function encodeBase64Url(value: object): string {
  return btoa(JSON.stringify(value))
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

function makeE2eJwt(): string {
  const expiresAt = Math.floor(Date.now() / 1000) + 60 * 60;
  return `${encodeBase64Url({ alg: "none", typ: "JWT" })}.${encodeBase64Url({ exp: expiresAt })}.e2e`;
}

function emptyDashboardOverview(range = "1m") {
  return {
    range,
    theme_filter: null,
    generated_at: "2026-08-12T12:00:00Z",
    available_seasons: [],
    streak: {
      current_days: 0,
      best_days: 0,
      weekly_goal: 5,
      week_count: 0,
      month_count: 0,
      weekly_progress: 0,
      included_entry_types: ["daily", "dream", "thought_record"],
    },
    series: [],
    themes: [],
    cbt: {
      total_records: 0,
      common_patterns: [],
      average_before: null,
      average_after: null,
      average_change: null,
      recent_reflections: [],
    },
    recent_activity: [],
    recent_activity_by_type: {
      daily: [],
      dream: [],
      thought_record: [],
      important_day: [],
    },
    dream_insights: {
      total_dreams: 0,
      top_symbols: [],
      top_people: [],
      top_places: [],
      recent: [],
      recent_repeating_patterns: [],
      latest: null,
    },
    focus_sections: {
      memory_echo: { label: "This time before", count: 0, items: [] },
      theme_drift: [],
      mood_anchors: [],
      important_day_cues: [],
    },
    quick_actions: [
      { type: "daily", label: "Diary", icon: "bookmark", route: "/entries/create?type=daily" },
      { type: "dream", label: "Dream", icon: "bedtime", route: "/entries/create?type=dream" },
      { type: "thought_record", label: "Thought record", icon: "psychology", route: "/cbt/new" },
      { type: "important_day", label: "Important day", icon: "event", route: "/entries/create?type=important-day" },
    ],
  };
}

async function mockCookieOnlyApi(page: Page) {
  const user = {
    id: 501,
    username: "cookie-user",
    email: "cookie@example.com",
    display_name: "CookieUser",
    first_name: "Cookie",
    last_name: "User",
    onboarding_completed: true,
    chat_enabled: false,
    allow_ai_history: true,
  };

  const dashboardRequests: Array<Record<string, string>> = [];

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path.endsWith("/api/oauth/providers")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          providers: [{ id: "google", label: "Google", enabled: true, start_url: "/api/oauth/google/start" }],
        }),
      });
      return;
    }

    if (path.endsWith("/api/login")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: {
          "Set-Cookie":
            "access_token_cookie=e2e-cookie; Path=/; HttpOnly; SameSite=Lax",
        },
        body: JSON.stringify({
          token: makeE2eJwt(),
          user,
        }),
      });
      return;
    }

    if (path.endsWith("/api/profile")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(user),
      });
      return;
    }

    if (path.endsWith("/api/dashboard/overview")) {
      dashboardRequests.push(request.headers());
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(emptyDashboardOverview(url.searchParams.get("range") || "1m")),
      });
      return;
    }

    if (path.endsWith("/api/billing/status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          entitlement: {
            tier: "free",
            source: "system",
            status: "active",
            is_default: true,
            is_active: true,
          },
          provider: "stripe",
          stripe_configured: false,
          checkout_tiers: [],
          checkout_periods: {},
          has_billing_customer: false,
          current_subscription: null,
          usage: {},
          plans: [],
          is_admin: false,
        }),
      });
      return;
    }

    if (path.endsWith("/api/plans")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          stripe_configured: false,
          checkout_periods: {},
          plans: [],
        }),
      });
      return;
    }

    if (path.endsWith("/api/announcements/active")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ announcements: [] }),
      });
      return;
    }

    if (
      path.endsWith("/api/chat/context-status") ||
      path.endsWith("/api/chat/history") ||
      path.endsWith("/api/chat/stats")
    ) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ history_enabled: false, sources: [], messages: [] }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  return { dashboardRequests };
}

test("cookie-only frontend login does not persist bearer tokens", async ({ page }) => {
  const { dashboardRequests } = await mockCookieOnlyApi(page);

  await page.goto("/login");
  await page.getByLabel("Username").fill("cookie-user");
  await page.getByLabel("Password").fill("Password123");
  await page.getByTestId("login-submit").click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByTestId("dashboard-page")).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("openmynd_token")))
    .toBeNull();
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("ai_diary_token")))
    .toBeNull();
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("openmynd_user")))
    .toContain("CookieUser");
  expect(dashboardRequests.length).toBeGreaterThan(0);
  expect(dashboardRequests.some((headers) => "authorization" in headers)).toBe(false);
});
