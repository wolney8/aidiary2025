import { expect, Page, test } from "@playwright/test";

async function seedAuthenticatedSession(
  page: Page,
  options: { chatEnabled?: boolean } = {},
) {
  await seedLocalSession(page, {
    id: 1,
    username: "chat-e2e",
    display_name: "Alex",
    chat_enabled: options.chatEnabled ?? true,
  });

  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;

    if (path.endsWith("/api/profile")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          username: "chat-e2e",
          display_name: "Alex",
          chat_enabled: options.chatEnabled ?? true,
          allow_ai_history: true,
        }),
      });
      return;
    }

    if (path.endsWith("/api/chat/context-status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          history_enabled: true,
          sources: [
            { key: "daily", label: "Diary entries", count: 2, enabled: true },
            { key: "dream", label: "Dream entries", count: 1, enabled: true },
            {
              key: "thought_record",
              label: "Thought records",
              count: 1,
              enabled: true,
            },
            {
              key: "important_day",
              label: "Important days",
              count: 1,
              enabled: true,
            },
          ],
        }),
      });
      return;
    }

    if (path.endsWith("/api/chat/history")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ conversation_id: "e2e-chat", messages: [] }),
      });
      return;
    }

    if (path.endsWith("/api/chat/stats")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          conversation_id: "e2e-chat",
          message_count: 0,
          user_message_count: 0,
          assistant_message_count: 0,
          token_count: 0,
          started_at: null,
          last_message_at: null,
          active_seconds: 0,
          conversation_count: 0,
          limits: {
            max_message_length: 2000,
            max_messages_per_conversation: 100,
            model_history_limit: 20,
            history_response_limit: 50,
            daily_token_budget: 8000,
            monthly_chat: {
              used: 0,
              limit: 10,
              remaining: 10,
              unlimited: false,
            },
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

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

async function seedLocalSession(page: Page, userOverrides: Record<string, unknown> = {}) {
  await page.addInitScript(
    ({ token, userOverrides }) => {
      const user = {
        id: 42,
        username: "e2e-user",
        display_name: "E2EUser",
        onboarding_completed: true,
        chat_enabled: true,
        ...userOverrides,
      };

      localStorage.setItem("openmynd_token", token);
      localStorage.setItem("openmynd_user", JSON.stringify(user));
    },
    { token: makeE2eJwt(), userOverrides },
  );
}

async function mockAuthenticatedApi(page: Page, userOverrides: Record<string, unknown> = {}) {
  const user = {
    id: 42,
    username: "oauth-e2e",
    email: "oauth@example.com",
    display_name: "OAuthUser",
    first_name: "OAuth",
    last_name: "User",
    onboarding_completed: false,
    chat_enabled: true,
    allow_ai_history: true,
    ...userOverrides,
  };

  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;

    if (path.endsWith("/api/profile")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(user),
      });
      return;
    }

    if (path.endsWith("/api/profile/account") && route.request().method() === "DELETE") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "Account deleted" }),
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
          checkout_tiers: ["personal", "plus"],
          checkout_periods: {},
          has_billing_customer: false,
          current_subscription: null,
          usage: {
            plan: "free",
            window: "month",
            window_start: "2026-08-01",
            ai_analysis: { used: 0, limit: 10, remaining: 10, unlimited: false },
            ai_image: { used: 0, limit: 0, remaining: 0, unlimited: false },
            ocr_page: { used: 0, limit: 5, remaining: 5, unlimited: false },
            transcription_minute: { used: 0, limit: 0, remaining: 0, unlimited: false },
          },
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

    if (path.endsWith("/api/chat/context-status")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ history_enabled: false, sources: [] }),
      });
      return;
    }

    if (path.endsWith("/api/chat/history")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ conversation_id: "oauth-e2e-chat", messages: [] }),
      });
      return;
    }

    if (path.endsWith("/api/chat/stats")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          conversation_id: "oauth-e2e-chat",
          message_count: 0,
          user_message_count: 0,
          assistant_message_count: 0,
          token_count: 0,
          started_at: null,
          last_message_at: null,
          active_seconds: 0,
          conversation_count: 0,
          limits: {
            max_message_length: 2000,
            max_messages_per_conversation: 100,
            model_history_limit: 20,
            history_response_limit: 50,
            daily_token_budget: 8000,
            monthly_chat: {
              used: 0,
              limit: 10,
              remaining: 10,
              unlimited: false,
            },
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });
}

test("login screen loads with core controls", async ({ page }) => {
  await page.goto("/login");

  await expect(page).toHaveTitle("Login | OpenMynd");
  await expect(
    page.getByRole("heading", { level: 1, name: "Log in to OpenMynd" }),
  ).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Register here" }),
  ).toBeVisible();

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeVisible();
});

test("registration screen exposes labelled account controls", async ({ page }) => {
  await page.goto("/register");

  await expect(page).toHaveTitle("Create account | OpenMynd");
  await expect(
    page.getByRole("heading", { level: 1, name: "Create OpenMynd account" }),
  ).toBeVisible();
  await expect(page.getByLabel("Username")).toHaveAttribute(
    "autocomplete",
    "username",
  );
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "autocomplete",
    "new-password",
  );
});

test("public legal pages and cookie consent are reachable", async ({ page }) => {
  await page.goto("/login");

  const banner = page.getByTestId("cookie-consent-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("Cookies");
  await page.getByRole("button", { name: "Manage" }).click();
  await expect(page.getByLabel("Essential cookies")).toBeChecked();
  await page.getByRole("button", { name: "Save choices" }).click();
  await expect(banner).toHaveCount(0);

  await page.goto("/privacy");
  await expect(page.getByTestId("legal-privacy")).toContainText("Privacy policy");
  await expect(page.getByTestId("legal-privacy")).toContainText("How AI features use your data");

  await page.goto("/terms");
  await expect(page.getByTestId("legal-terms")).toContainText("Terms and conditions");
  await expect(page.getByTestId("legal-terms")).toContainText("AI limitations");

  await page.goto("/cookies");
  await expect(page.getByTestId("legal-cookies")).toContainText("Cookie policy");
  await expect(page.getByTestId("legal-cookies")).toContainText("Optional cookies");
  await page.getByTestId("manage-cookie-preferences").click();
  await expect(page.getByTestId("cookie-consent-banner")).toBeVisible();
  await expect(page.getByLabel("Optional analytics")).toBeVisible();
});

test("OAuth callback sends first-run users to onboarding", async ({ page }) => {
  await mockAuthenticatedApi(page, {
    onboarding_completed: false,
    password_auth_enabled: false,
  });
  const user = encodeBase64Url({
    id: 42,
    username: "oauth-e2e",
    email: "oauth@example.com",
    display_name: "OAuthUser",
    first_name: "OAuth",
    last_name: "User",
    onboarding_completed: false,
  });
  const fragment = new URLSearchParams({
    token: makeE2eJwt(),
    user,
    returnUrl: "/settings/account",
    onboardingRequired: "true",
  });

  await page.goto(`/oauth/callback#${fragment.toString()}`);

  await expect(page).toHaveURL(/\/onboarding\?returnUrl=%2Fdashboard$/);
  await expect(page.getByTestId("oauth-onboarding-page")).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 1, name: "Finish setting up your account" }),
  ).toBeVisible();
});

test("OAuth callback returns completed users to a safe app URL", async ({ page }) => {
  await mockAuthenticatedApi(page, { onboarding_completed: true });
  const user = encodeBase64Url({
    id: 42,
    username: "oauth-e2e",
    onboarding_completed: true,
  });
  const fragment = new URLSearchParams({
    token: makeE2eJwt(),
    user,
    returnUrl: "/entries?display=calendar",
    onboardingRequired: "false",
  });

  await page.goto(`/oauth/callback#${fragment.toString()}`);

  await expect(page).toHaveURL(/\/entries\?display=calendar$/);
});

test("restricted accounts can export or delete from the limited access page", async ({ page }) => {
  await seedLocalSession(page, {
    account_status: "restricted",
    onboarding_completed: true,
    password_auth_enabled: false,
  });
  await mockAuthenticatedApi(page, {
    account_status: "restricted",
    onboarding_completed: true,
    password_auth_enabled: false,
  });

  await page.goto("/account-restricted");

  await expect(page.getByTestId("account-restricted-page")).toBeVisible();
  await expect(page.getByTestId("account-restricted-page")).toContainText("Account restricted");
  await expect(page.getByTestId("restricted-export-button")).toBeVisible();
  await expect(page.getByTestId("restricted-delete-account-button")).toBeDisabled();

  await page.getByLabel("Type DELETE MY ACCOUNT").fill("DELETE MY ACCOUNT");
  await expect(page.getByTestId("restricted-delete-account-button")).toBeEnabled();
});

test("account deletion uses the app dialog and clears the session", async ({ page }) => {
  await seedLocalSession(page, {
    auth_provider: "google",
    onboarding_completed: true,
    password_auth_enabled: false,
  });
  await mockAuthenticatedApi(page, {
    auth_provider: "google",
    onboarding_completed: true,
    password_auth_enabled: false,
    registered_at: "2026-08-11T10:00:00Z",
  });

  await page.goto("/account");

  await expect(page.getByTestId("account-page")).toBeVisible();
  await page.getByLabel("Type DELETE MY ACCOUNT").fill("DELETE MY ACCOUNT");
  await page.getByTestId("account-delete-account-button").click();

  await expect(page.getByTestId("app-dialog")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Permanently delete account?" })).toBeVisible();
  await page.getByTestId("app-dialog-confirm").click();

  await expect(page).toHaveURL(/\/login\?reason=account-deleted$/);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("openmynd_token"))).toBeNull();
  await expect.poll(() => page.evaluate(() => localStorage.getItem("openmynd_user"))).toBeNull();
});

test("chat companion is limited to diary content routes", async ({ page }) => {
  await seedAuthenticatedSession(page);

  await page.goto("/settings");
  await expect(page.getByTestId("chat-open-button")).toHaveCount(0);

  await page.goto("/account");
  await expect(page.getByTestId("chat-open-button")).toHaveCount(0);

  await page.goto("/entries");
  await expect(page.getByTestId("chat-open-button")).toBeVisible();

  await page.goto("/cbt");
  await expect(page.getByTestId("chat-open-button")).toBeVisible();

  await page.goto("/important-days");
  await expect(page.getByTestId("chat-open-button")).toBeVisible();

  await page.goto("/dashboard");
  await expect(page.getByTestId("chat-open-button")).toHaveCount(0);
});

test("chat companion shows route-aware starter chips", async ({ page }) => {
  await seedAuthenticatedSession(page);

  await page.goto("/cbt");
  await page.getByTestId("chat-open-button").click();
  await expect(page.getByTestId("chat-starter-chips")).toContainText(
    "What's a Thought Record?",
  );

  await page.goto("/important-days");
  await page.getByTestId("chat-open-button").click();
  await expect(page.getByTestId("chat-starter-chips")).toContainText(
    "Reflect on important dates",
  );
});
